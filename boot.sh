#!/bin/sh
# entrypoint for flask docker image
source venv/bin/activate
python wsgi.py