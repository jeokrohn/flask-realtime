from dotenv import load_dotenv

load_dotenv('webexintegration/webexintegration.env')
import os

assert all((os.getenv('CLIENT_ID'), os.getenv('CLIENT_SECRET'), os.getenv('REDIRECT_URI'), os.getenv('SCOPE'))), \
    'CLIENT_ID, CLIENT_SECRET, REDIRECT_URI and SCOPE need to be defined as environment variables'

from app import create_app, socketio

app=create_app()
socketio.run(app, host='0.0.0.0', log_output=True)