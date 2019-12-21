# Flask-Realtime

This is a playground to try to build a simple demonstrator for a website which allows to 
run Python code in a thread and show the stdout output of that thread
on a webpage in real-time. The general idea is to open a websocket and then
send all output to the browser acting as websocket client. Minimal client side
Javascript tben is used to append all messages received over the websocket to 
a `div` in the webpage.

Components involved:
* Flask: web server
* Nginx: web proxy
* Redis: persistend storage of sessio data including user id and token

Pressing the "Start" or "Stop" button sends an event to the server over
the websocket which is handled in `app/events.py`. To startsome code a `FlaskThread`
is created and started. A stop request is signalled to the `FlaskThread` by setting
a stop event. The code executed with the `FlaskThread` has to honor the
stop event and quit as soon as possible when the stop request is set. 
For this a `running` method is passed to the code executed within the
`FlaskThread` and the code has to periodically call this method to check
whether the could should continue to run. 

As an example `app/list_spaces.py`
contains sample code to get all spaces of the authenticated user and then
for each space read all messages to determine the oldest and latest message
in each space. This code uses `asyncio` to optimize the performance. A
minimal asynchronous Webex Teams API framework is included in 
`app/webexteamsasyncapi.py`. This minimal framework can easily be expanded.

## Building the docker images

All docker images can be build using this command:
`docker-compose -f docker-compose-dev.yml build`

This creates three images:
* app-flask: the web server hosting the application
* app-redis: a Redis server used for persistent data
* app-nginx: the web proxy serving static data and forwarding everything else to the app server

## Running the development environment

The development environment can be started using this command:
`docker-compose -f docker-compose-dev.yml up -d --build`

The `--build` is optional. With this option given all three images are built before starting the environment.

The `docker-compose-dev.yml` file maps some host directories to the container file systems 
(see the file for details).

The mappings make sure that all application data is picked up from the local file system and
not from the container file system. After changing any app data there is no need to rebuild the images; 
you only need to restart the containers.

The `app-flask` container expects to find a file `webexintegration.env` (see the main
directory for a template) containing the details of the Webex Teams integration to use.

When browsing to the main page (`http:localhost:5000`) the app initiates
a SAML 2.0 OAuth authorization code authorization flow to obtain refresh 
and access token for the current user. These tokens are then used to run
the example code against the Webex Teams APIs when the "Start" button is
pressed on the main web page.

## Running the Flask server from your IDE (for debug purposes)

Before running `test.py` from your IDE you need to make sure that the
Redis server is runnnig locally. This can be done by executing 
`run_redis.sh` from the shell:  
```#!/bin/sh
docker build -t app-redis -f Dockerfile-redis .
docker rm -f redis
docker run --name redis -p 6379:6379 -d -v $(pwd)/redis_data:/data app-redis
```

The script (re-)builds the Redis image, removes any running Redis 
instance, and finally runs the Redis image.