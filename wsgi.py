import logging
import os

# load parameters of Webex Integration to be used
# The Dockerfile makes sure that the webexintegration.env from the project root is copied to the webexintegration
# directory
# For the test environment you want to make sure to create a webexintegration directory with the config file
from dotenv import load_dotenv

load_dotenv('webexintegration/webexintegration.env')

assert all((os.getenv('CLIENT_ID'), os.getenv('CLIENT_SECRET'), os.getenv('REDIRECT_URI'), os.getenv('SCOPE'))), \
    'CLIENT_ID, CLIENT_SECRET, REDIRECT_URI and SCOPE need to be defined as environment variables'

from app import create_app, socketio
from redis import Redis

from app.interactive import Token

# logging.basicConfig(level=logging.DEBUG)

# this guys is a little "chatty" at level INFO
logging.getLogger('engineio.server').setLevel(logging.WARNING)

redis_session = Redis(host='redis')
Token.set_redis(redis_session)

config = dict(
    SESSION_REDIS=redis_session
)

app = create_app(config)

# server does NOT listen on localhost b/c the server is deployed in a container behind an Nginx proxy
socketio.run(app, host='0.0.0.0', log_output=True)
