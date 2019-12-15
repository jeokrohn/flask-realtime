from . import socketio
from flask import session, request
from functools import wraps
from flask_socketio import disconnect
from time import sleep
import logging
from . flaskthread import FlaskThread
from . interactive import Token
import functools

log = logging.getLogger(__name__)


def count_thread(user_id, sid, running):
    log.debug(f'count started for sid={sid}')

    token = Token.get_token(user_id)
    log.debug(f'count thread: refresh token before refresh valid until {token.refresh_token_exprires_at}')
    log.debug(f'count thread:  access token before refresh valid until {token.access_token_exprires_at}')
    token.refresh()
    log.debug(f'count thread:  refresh token after refresh valid until {token.refresh_token_exprires_at}')
    log.debug(f'count thread:   access token after refresh valid until {token.access_token_exprires_at}')

    c = 0
    while running():
        # writer(f'latest count={c}')
        print(f'latest count={c}')
        c += 1
        sleep(0.1)
    log.debug(f'count stopped for sid={sid}')


def need_user(f):
    @wraps(f)
    def check_user(*args, **kwargs):
        if session.get('user') is None:
            log.debug('No user context -> disconnect')
            disconnect()
        else:
            return f(*args, **kwargs)

    return check_user


@socketio.on('connect')
def connect():
    log.debug(f'connect for session {request.sid}')


@socketio.on('start_request')
def start_request():
    log.debug(f'start_request {request.sid}')
    thread = FlaskThread.get(request.sid)
    if thread is None:
        thread = FlaskThread.for_session(sid=request.sid, target=functools.partial(count_thread, session['user_id']), name=f'count-{request.sid}')
        thread.start()
        log.debug(f'started counting thread for {request.sid}')
    else:
        log.warning(f'thread already running for {request.sid}')


@socketio.on('stop_request')
def stop_request():
    log.debug(f'stop_request {request.sid}')
    thread = FlaskThread.get(request.sid)
    if thread:
        # request thread to stop
        thread.set_stop_event()


@socketio.on('disconnect')
def disconnect():
    log.debug(f'disconnect {request.sid} ')
    thread = FlaskThread.get(request.sid)
    if thread is not None:
        log.debug(f'disconnect {request.sid}, stopping thread')
        thread.set_stop_event()
