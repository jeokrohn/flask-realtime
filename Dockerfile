FROM python:3.10-alpine as base

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1

FROM base as python-deps

# install pipenv and gcc
RUN pip install pipenv
RUN apk update && apk --no-cache add build-base

# Install python dependencies in /.venv
COPY Pipfile .
COPY Pipfile.lock .
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy

FROM base as runtime

# Copy virtual env from python-deps stage
COPY --from=python-deps /.venv /.venv
ENV PATH="/.venv/bin:$PATH"

# creae new user
RUN adduser -D flaskdemo
WORKDIR /home/flaskdemo
USER flaskdemo

COPY wsgi.py ./

RUN mkdir webexintegration
COPY webexintegration.env webexintegration/

COPY app app
RUN chown flaskdemo:flaskdemo ./

EXPOSE 5000
ENTRYPOINT ["python", "wsgi.py"]
