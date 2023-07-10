FROM python:3.9.17-alpine

WORKDIR /app

COPY *.py .
COPY requirements.txt .

ENV TERM xterm
ENV PYTHONUNBUFFERED 1

ARG TARGETPLATFORM
ARG BUILD_DATE
ARG COMMIT

RUN python -m pip install --upgrade pip \
RUN pip install --upgrade setuptools \
RUN apk add --no-cache jpeg-dev zlib-dev libjpeg \
RUN apk add --no-cache --virtual .build-deps gcc musl-dev python3-dev \
RUN pip install Pillow==9.5.0 \
RUN pip install -r requirements.txt \
RUN apk del .build-deps \
RUN find /usr/local \
     \( -type d -a -name test -o -name tests \) \
     -o \( -type f -a -name '*.pyc' -o -name '*.pyo' \) \
     -exec rm -rf '{}' + \
RUN rm -rf /root/.cache/pip

LABEL maintainer="Discord: the_devil_of_the_rhine (863687441809801246)" \
      commit=$COMMIT \
      description="Discord Bot for automatically assigning users a role after they complete a captcha." \
      release=$BUILD_DATE \
      version="1.1.1" \
      url="https://gitlab.bloodygang.com/Serpensin/DiscordBots-Bouncer"

CMD ["python3", "main.py"]
