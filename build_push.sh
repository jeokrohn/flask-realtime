#!/bin/sh
docker-compose -f docker-compose-dev.yml build && \
  docker tag app-flask jeokrohn/app-flask && \
  docker tag app-nginx jeokrohn/app-nginx && \
  docker tag app-redis jeokrohn/app-redis && \
  docker push jeokrohn/app-flask && \
  docker push jeokrohn/app-nginx && \
  docker push jeokrohn/app-redis # && \
  #docker rmi $(docker images -f "dangling=true" -q)
