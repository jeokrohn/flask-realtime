import logging
from threading import Lock, Thread, Event
import base64
import io
import eventlet
import eventlet.greenio
import socket
from typing import Dict
from . import stdoutproxy
from . import socketio

log = logging.getLogger(__name__)
io_log = logging.getLogger(f'{__name__}.io')

END_OF_PIPE_MAGIC = '\x00\x01\x05'


class PipeIO(io.TextIOBase):
    """
    Text IO sending each line as message over a socket terminated by a zero string
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
            # last line
            self.buffer = lines[-1]
        else:
            self.buffer = ''
        lines = lines[:-1]

        # now send all lines
        for line in lines:
            self.send_to_pipe(line)
        return len(s)

    def shutdown(self):
        self.send_to_pipe(END_OF_PIPE_MAGIC)

    def send_to_pipe(self, line: str) -> None:
        """
        Send a line to the pipe
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

    def __init__(self, sid, target=None, name=None, *args, **kwargs):
        self.sid = sid
        self.stop_event = Event()
        self.flask_target = target
        log.debug(f'FlaskThread.__init__: {self}')

        # need to spawn an eventlet worker reading from a socket and sending to websocket
        s1, s2 = socket.socketpair()
        s2 = eventlet.greenio.GreenSocket(s2)
        self.pipe: socket.SocketType = s1
        self.green_pipe = s2
        self.green_thread = eventlet.spawn(self.pipe_processor)
        super(FlaskThread, self).__init__(target=self.wrapped_target, name=name, args=args, kwargs=kwargs)

    _registry: Dict[str, "FlaskThread"] = {}
    _lock = Lock()

    @staticmethod
    def get(sid):
        return FlaskThread._registry.get(sid)

    @staticmethod
    def for_session(sid, target=None, name=None, *args, **kwargs):
        with FlaskThread._lock:
            assert FlaskThread.get(sid) is None
            thread = FlaskThread(sid=sid, target=target, name=name, *args, **kwargs)
            FlaskThread._registry[sid] = thread
        return thread

    def set_stop_event(self):
        log.debug(f'{self}.stop()')
        self.stop_event.set()

    def running(self):
        return not self.stop_event.is_set()

    def wrapped_target(self, *args, **kwargs) -> None:
        """
        Target for the thread. Creates the environment for the actual target, executes the target, and handles
        cleanup
        :param args: args for target
        :param kwargs: kwars for target
        :return:
        """
        log.debug(f'{self}.wrapped_target: starting target code')
        pipe_io = PipeIO(self.pipe)

        stdoutproxy.redirect(pipe_io)

        # call the target. First three parameters are:
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

    def pipe_processor(self) -> None:
        # read from socket and emit data to websocket
        # records on the pipe are base64 encoded strings which are separated by zero (\x00)
        log.debug(f'pipe_processor {self.sid}: starting')
        while True:
            buffer = b''
            while not (buffer and buffer[-1] == 0):
                buffer += self.green_pipe.recv(1024)
            for data in buffer.split(b'\x00')[:-1]:
                io_log.debug(f'pipe_processor {self.sid}: base64="{data}"')
                data = base64.b64decode(data).decode()
                io_log.debug(f'pipe_processor {self.sid}: str="{data}"')
            if data == END_OF_PIPE_MAGIC:
                break
            socketio.emit('output', {'data': data}, room=self.sid)
        self.green_pipe.close()
        log.debug(f'pipe_processor {self.sid}: done')

    def __repr__(self):
        return f'FlaskThread(sid={self.sid})'
