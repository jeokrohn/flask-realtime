#!/usr/bin/env python
import logging

from dotenv import load_dotenv

load_dotenv('webexintegration/webexintegration.env')

from app import create_app, socketio
from redis import Redis

from app.interactive import Token

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    redis_session = Redis()
    Token.set_redis(redis_session)
    config = dict(
        SESSION_REDIS=redis_session
    )
    logging.getLogger('app.flaskthread').setLevel(logging.DEBUG)
    logging.getLogger('app.flaskthread.io').setLevel(logging.INFO)
    logging.getLogger('engineio.server').setLevel(logging.WARNING)
    logging.getLogger('socketio.server').setLevel(logging.WARNING)
    app = create_app(config)
    socketio.run(app, log_output=True)
