import os
from flask import Flask
from flask_session import Session
from flask_bootstrap import Bootstrap
from flask_socketio import SocketIO
from . import interactive

bootstrap = Bootstrap()
session = Session()
socketio = SocketIO(manage_sessions=False, engineio_logger=True)


class DefaultConfig:
    SESSION_TYPE = 'redis'


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(DefaultConfig)

    if test_config:
        app.config.from_mapping(test_config)
    app.config['SECRET_KEY'] = b'\xd5\xfbz\xbbVX\xf9\xfe\xaa\x053\xedg\x8e\xa2;'

    app.register_blueprint(interactive.bp)
    session.init_app(app)
    bootstrap.init_app(app)
    socketio.init_app(app, cors_allowed_origins='*')

    return app


from . import events
