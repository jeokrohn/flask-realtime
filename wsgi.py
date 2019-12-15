from dotenv import load_dotenv
import os

# load parameters of Webex Integration to be used
# The Dockerfile makes sure that the webexintegration.env from the project root is copied to the webexintegration
# directory
# For the test environment you want to make sure to create a webexintegration directory with the config file
load_dotenv('webexintegration/webexintegration.env')

assert all((os.getenv('CLIENT_ID'), os.getenv('CLIENT_SECRET'), os.getenv('REDIRECT_URI'), os.getenv('SCOPE'))), \
    'CLIENT_ID, CLIENT_SECRET, REDIRECT_URI and SCOPE need to be defined as environment variables'

from app import create_app, socketio

app = create_app()

# server does NOT listen on localhost b/c the server is deployed in a container behind an Nginx proxy
socketio.run(app, host='0.0.0.0', log_output=True)
