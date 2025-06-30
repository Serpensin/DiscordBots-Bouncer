FROM python:3.12-alpine

WORKDIR /app

COPY CustomModules ./CustomModules
COPY main.py .
COPY __init__.py .
COPY requirements.txt .

ENV TERM=xterm
ENV PYTHONUNBUFFERED=1

ARG TARGETPLATFORM
ARG BUILD_DATE
ARG COMMIT

RUN apk update && \
    apk add --no-cache --virtual .build-deps gcc musl-dev python3-dev linux-headers jpeg-dev zlib-dev libjpeg rust cargo && \
    apk add --no-cache curl && \
    python -m pip install --root-user-action ignore --upgrade pip setuptools && \
    pip install --root-user-action ignore -r requirements.txt && \
    apk del .build-deps && \
    find /usr/local \
      \( -type d -a \( -name test -o -name tests \) \) \
      -o \( -type f -a \( -name '*.pyc' -o -name '*.pyo' \) \) \
      -exec rm -rf '{}' \; && \
    rm -rf /root/.cache/pip

LABEL maintainer="Discord: piko.piko.no.mi (970119359840284743)" \
      description="Discord Bot for automatically assigning users a role after they complete a captcha." \
      release=$BUILD_DATE \
      version="1.5.4" \
      url="https://github.com/Serpensin/DiscordBots-Bouncer"

CMD ["python3", "main.py"]
