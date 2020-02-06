"""
Handling of websocket events
"""
import functools
import logging

from flask import session, request
from functools import partial

from . import socketio
from .flaskthread import FlaskThread
from .list_spaces import list_spaces
from .create_spaces import create_spaces

log = logging.getLogger(__name__)


@socketio.on('connect')
def connect():
    log.debug(f'connect for session {request.sid}')


@socketio.on('start_space_stats')
def start_space_stats() -> None:
    """
    Start button has been pressed
    :return: None
    """
    log.debug(f'start_space_stats {request.sid}')
    thread = FlaskThread.get(request.sid)
    if thread is None:
        # create FlaskThread; pass user id as additional parameter to list_paces()
        thread = FlaskThread.for_session(sid=request.sid, target=list_spaces, name=f'task-{request.sid}',
                                         user_id=session['user_id'])
        log.debug(f'start_space_stats, starting thread for {request.sid}')
        thread.start()
    else:
        log.warning(f'start_space_stats, thread already running for {request.sid}')

@socketio.on('start_create_spaces')
def start_create_spaces() -> None:
    """
    Start button has been pressed
    :return: None
    """
    log.debug(f'start_create_spaces {request.sid}')
    thread = FlaskThread.get(request.sid)
    if thread is None:
        # create FlaskThread; pass user id as additional parameter to list_paces()
        thread = FlaskThread.for_session(sid=request.sid, target=create_spaces, name=f'task-{request.sid}',
                                         user_id=session['user_id'])
        log.debug(f'start_create_spaces, starting thread for {request.sid}')
        thread.start()
    else:
        log.warning(f'start_create_spaces, thread already running for {request.sid}')


@socketio.on('start_delete_spaces')
def start_delete_spaces() -> None:
    """
    Start button has been pressed
    :return: None
    """
    log.debug(f'start_delete_spaces {request.sid}')
    thread = FlaskThread.get(request.sid)
    if thread is None:
        # create FlaskThread; pass user id as additional parameter to list_paces()
        thread = FlaskThread.for_session(sid=request.sid, target=partial(create_spaces, clean_up=True),
                                         name=f'task-{request.sid}', user_id=session['user_id'])
        log.debug(f'start_delete_spaces, starting thread for {request.sid}')
        thread.start()
    else:
        log.warning(f'start_delete_spaces, thread already running for {request.sid}')


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
