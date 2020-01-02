#!/bin/sh
# build redis image, remove (and stop) existing redis container, an start redis container
docker build -t flask-realtime-redis -f Dockerfile-redis .
docker rm -f redis
docker run --name redis -p 6379:6379 -d -v $(pwd)/redis_data:/data flask-realtime-redis