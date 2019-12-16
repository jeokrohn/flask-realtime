from . import socketio
from flask import session, request
from time import sleep
import logging
from .flaskthread import FlaskThread
from .interactive import Token
import functools

log = logging.getLogger(__name__)


def count_thread(user_id, sid, running):
    log.debug(f'count started for sid={sid}')

    token = Token.get_token(user_id)
    log.debug(f'count thread: refresh token before refresh valid until {token.refresh_token_expires_at}')
    log.debug(f'count thread:  access token before refresh valid until {token.access_token_expires_at}')
    token.refresh()
    log.debug(f'count thread:  refresh token after refresh valid until {token.refresh_token_expires_at}')
    log.debug(f'count thread:   access token after refresh valid until {token.access_token_expires_at}')

    c = 0
    while running():
        print(f'latest count={c}')
        c += 1
        sleep(0.1)
    log.debug(f'count stopped for sid={sid}')


@socketio.on('connect')
def connect():
    log.debug(f'connect for session {request.sid}')


@socketio.on('start_request')
def start_request() -> None:
    """
    Start button has been pressed
    :return: None
    """
    log.debug(f'start_request {request.sid}')
    thread = FlaskThread.get(request.sid)
    if thread is None:
        thread = FlaskThread.for_session(sid=request.sid, target=functools.partial(count_thread, session['user_id']),
                                         name=f'count-{request.sid}')
        thread.start()
        log.debug(f'started counting thread for {request.sid}')
    else:
        log.warning(f'thread already running for {request.sid}')


def stop_thread() -> None:
    """
    Stop thread based on current request context
    :return: None
    """
    thread = FlaskThread.get(request.sid)
    if thread:
        # request thread to stop
        log.debug(f'stopping thread for {request.sid}')
        thread.set_stop_event()


@socketio.on('stop_request')
def stop_request() -> None:
    """
    Stop button has been pressed
    Need to make sure that running thread is stopped
    :return: None
    """
    log.debug(f'stop_request {request.sid}')
    stop_thread()


@socketio.on('disconnect')
def disconnect():
    """
    Websocket connection disconnected (browser tab closed)
    :return:
    """
    log.debug(f'disconnect {request.sid} ')
    stop_thread()
