#!/bin/sh
docker-compose -f docker-compose.yml build && \
  docker tag app-flask jeokrohn/app-flask && \
  docker tag app-nginx jeokrohn/app-nginx && \
  docker push jeokrohn/app-flask && \
  docker push jeokrohn/app-nginx && \
  docker rmi $(docker images -f "dangling=true" -q)
