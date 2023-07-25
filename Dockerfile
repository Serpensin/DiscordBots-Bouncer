FROM python:3.9.17-alpine

WORKDIR /app

COPY *.py .
COPY requirements.txt .

ENV TERM xterm
ENV PYTHONUNBUFFERED 1

ARG TARGETPLATFORM
ARG BUILD_DATE
ARG COMMIT

RUN apk update && \
    apk add --no-cache --virtual .build-deps gcc musl-dev python3-dev jpeg-dev zlib-dev libjpeg rust cargo && \
    python -m pip install --upgrade pip setuptools && \
    pip install Pillow==9.5.0 && \
    pip install -r requirements.txt && \
    apk del .build-deps && \
    find /usr/local \
      \( -type d -a \( -name test -o -name tests \) \) \
      -o \( -type f -a \( -name '*.pyc' -o -name '*.pyo' \) \) \
      -exec rm -rf '{}' \; && \
    rm -rf /root/.cache/pip

LABEL maintainer="Discord: the_devil_of_the_rhine (863687441809801246)" \
      commit=$COMMIT \
      description="Discord Bot for automatically assigning users a role after they complete a captcha." \
      release=$BUILD_DATE \
      version="1.2.1" \
      url="https://gitlab.bloodygang.com/Serpensin/DiscordBots-Bouncer"

CMD ["python3", "main.py"]
