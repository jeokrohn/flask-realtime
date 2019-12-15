from dotenv import load_dotenv

load_dotenv('webexintegration/webexintegration.env')

from app import create_app, socketio
import logging

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    config=dict(
        SESSION_TYPE='filesystem'
    )
    logging.getLogger('app.flaskthread').setLevel(logging.DEBUG)
    logging.getLogger('app.flaskthread.io').setLevel(logging.INFO)
    logging.getLogger('engineio.server').setLevel(logging.WARNING)
    logging.getLogger('socketio.server').setLevel(logging.WARNING)
    app = create_app(config)
    socketio.run(app, log_output=True)
