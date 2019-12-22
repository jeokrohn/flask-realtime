#!/bin/sh
docker-compose -f docker-compose-dev.yml build && \
  docker tag flask-realtime-flask jeokrohn/flask-realtime-flask && \
  docker tag flask-realtime-nginx jeokrohn/flask-realtime-nginx && \
  docker tag flask-realtime-redis jeokrohn/flask-realtime-redis && \
  docker push jeokrohn/flask-realtime-flask && \
  docker push jeokrohn/flask-realtime-nginx && \
  docker push jeokrohn/flask-realtime-redis # && \
  #docker rmi $(docker images -f "dangling=true" -q)
