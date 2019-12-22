#!/bin/sh
docker build -t flask-realtime-redis -f Dockerfile-redis .
docker rm -f redis
docker run --name redis -p 6379:6379 -d -v $(pwd)/redis_data:/data app-redis