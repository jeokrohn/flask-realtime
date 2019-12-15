import logging
from threading import Lock, Thread, Event
import base64
import io
import eventlet
import eventlet.greenio
import socket
from typing import Dict, Optional
from . import stdoutproxy
from . import socketio

log = logging.getLogger(__name__)
io_log = logging.getLogger(f'{__name__}.io')

END_OF_PIPE_MAGIC = '\x00\x01\x05'


class PipeIO(io.TextIOBase):
    """
    Text IO sending each line as message over a pipe terminated by a zero string.
    """

    def __init__(self, pipe):
        self.pipe = pipe
        self.buffer = ''

    def write(self, s: str) -> int:
        """
        Write a string. Each line is sent to the pipe individually.
        :param s: string to write
        :return: return number of characters written
        """
        io_log.debug(f'{self}.write: s={s.encode()}')
        self.buffer = f'{self.buffer}{s}'
        lines = self.buffer.split('\n')
        if lines[-1]:
            # if the last line is not empty then we are missing the \n at the end and thus we should not send the
            # last line and instead buffer it for the future
            self.buffer = lines[-1]
        else:
            self.buffer = ''
        # last line never needs to be sent. It's either
        # * empty if string ended with \n -> no need to send an empty line
        # * not empty -> don't send line. Instead buffer it and wait or continuation (or \n)
        lines = lines[:-1]

        # now send all lines
        for line in lines:
            self._send_to_pipe(line)
        return len(s)

    def shutdown(self) -> None:
        """
        Ask other end to terminate
        :return: None
        """
        self._send_to_pipe(END_OF_PIPE_MAGIC)

    def _send_to_pipe(self, line: str) -> None:
        """
        Send a line to the pipe as base64 encoded and zero terminated string
        """
        io_log.debug(f'{self}.send_to_pipe: line="{line}"')
        # each line should be sent as base64 string terminated by a zero string
        data = base64.b64encode(line.encode()) + b'\x00'
        io_log.debug(f'{self}.send_to_pipe: base64="{data}"')
        self.pipe.sendall(data)


class FlaskThread(Thread):
    """
    Thread with stdout redirected to a a socket linked to a eventlet sending all data received from the socket as
    messages to a webesocket so that it can then be displayed on a web page
    https://stackoverflow.com/questions/14890997/redirect-stdout-to-a-file-only-for-a-specific-thread
    https://docs.python.org/3/library/socket.html#socket.socket.makefile
    """

    def __init__(self, sid: str, target=None, name: Optional[str] = None, *args, **kwargs):
        """

        :param sid: session id
        :param target: target for thread. First two parameters to target when called are session id and a method to
        determine whether the thread should continue to run
        :param name: name of thread
        :param args: arguments for target
        :param kwargs: arguments for target
        """
        self.sid = sid
        self.stop_event = Event()
        self.flask_target = target
        log.debug(f'FlaskThread.__init__: {self}')

        # need to spawn an eventlet worker reading from a socket and sending to websocket
        s1, s2 = socket.socketpair()
        s2 = eventlet.greenio.GreenSocket(s2)
        self.pipe: socket.SocketType = s1
        self.green_pipe = s2
        self.green_thread = eventlet.spawn(self._pipe_processor)
        super(FlaskThread, self).__init__(target=self._wrapped_target, name=name, args=args, kwargs=kwargs)

    # registry mapping from sid to FlaskThread
    _registry: Dict[str, 'FlaskThread'] = {}
    _lock = Lock()

    @staticmethod
    def get(sid: str) -> Optional['FlaskThread']:
        """
        Get Thread registered for given session id
        :param sid: session id
        :return: registered FlaskThread or None
        """
        return FlaskThread._registry.get(sid)

    @staticmethod
    def for_session(sid: str, target=None, name: Optional[str] = None, *args, **kwargs) -> 'FlaskThread':
        """
        Factory function to create a FlaskThread for a given session id. The thread also gets registered for the
        given session id
        :param sid: session id
        :param target: target for thread. First two parameters to target when called are session id and a method to
        determine whether the thread should continue to run
        :param name: name for the thread
        :param args: arguments for target
        :param kwargs: arguments for target
        :return: FlaskThread
        """
        with FlaskThread._lock:
            assert FlaskThread.get(sid) is None
            thread = FlaskThread(sid=sid, target=target, name=name, *args, **kwargs)
            FlaskThread._registry[sid] = thread
        return thread

    def set_stop_event(self) -> None:
        """
        Ask thread to stop
        :return: None
        """
        log.debug(f'{self}.stop()')
        self.stop_event.set()

    def running(self) -> bool:
        """
        Check if thread should continue to run. A reference to this method is passed to the target code.
        :return: result of check
        """
        return not self.stop_event.is_set()

    def _wrapped_target(self, *args, **kwargs) -> None:
        """
        Target for the thread. Creates the environment for the actual target, executes the target, and handles
        cleanup
        :param args: args for target
        :param kwargs: kwargs for target
        :return: None
        """
        log.debug(f'{self}.wrapped_target: starting target code')

        # redirect stdout of thread to pipe to communicate with eventlet pushing output to the web page via websocket
        pipe_io = PipeIO(self.pipe)
        stdoutproxy.redirect(pipe_io)

        # call the target. First two parameters are:
        # * sid
        # * a method to check whether the thread should terminate
        self.flask_target(self.sid, self.running, *args, **kwargs)
        log.debug(f'{self}.wrapped_target: target code terminated')

        # remove thread from registry
        with FlaskThread._lock:
            t = FlaskThread._registry.pop(self.sid)
            assert t is not None
        log.debug(f'{self}.wrapped_target: removed thread from registry')

        stdoutproxy.end_redirect()

        # ask processor to terminate
        pipe_io.shutdown()
        self.pipe.close()

    def _pipe_processor(self) -> None:
        """
        Eventlet based pipe processor. Read data from the pipe and send to web page via websocket
        :return: None
        """
        # read from socket and emit data to websocket
        # records on the pipe are base64 encoded strings which are separated by zero (\x00)
        log.debug(f'pipe_processor {self.sid}: starting')
        while True:
            buffer = b''
            # read until some data has been received and the received data end with zero termination
            while not (buffer and buffer[-1] == 0):
                buffer += self.green_pipe.recv(1024)
            # now send each line separately to web page
            for data in buffer.split(b'\x00')[:-1]:
                io_log.debug(f'pipe_processor {self.sid}: base64="{data}"')
                data = base64.b64decode(data).decode()
                io_log.debug(f'pipe_processor {self.sid}: str="{data}"')
                if data == END_OF_PIPE_MAGIC:
                    break
                socketio.emit('output', {'data': data}, room=self.sid)
            if data == END_OF_PIPE_MAGIC:
                break
        self.green_pipe.close()
        log.debug(f'pipe_processor {self.sid}: done')

    def __repr__(self):
        return f'FlaskThread(sid={self.sid})'
