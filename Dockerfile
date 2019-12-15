FROM python:3.7-alpine

RUN adduser -D flaskdemo

WORKDIR /home/flaskdemo

COPY requirements.txt ./

RUN python -m venv venv && \
    venv/bin/pip install -U pip && \
    apk add --no-cache build-base && \
    venv/bin/pip install -r requirements.txt && \
    apk del build-base

COPY wsgi.py boot.sh ./
RUN mkdir webexintegration
COPY webexintegration.env webexintegration/

COPY app app
RUN chmod +x boot.sh && \
    chown flaskdemo:flaskdemo ./

USER flaskdemo
EXPOSE 5000
ENTRYPOINT ["./boot.sh"]
