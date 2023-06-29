FROM python:3.9.16-alpine

WORKDIR /app

COPY *.py .
COPY requirements.txt .

ENV TERM xterm
ENV PYTHONUNBUFFERED 1

ARG TARGETPLATFORM
ARG BUILD_DATE
ARG COMMIT

RUN python -m pip install --upgrade pip && \
    pip install --upgrade setuptools && \
    apk add --no-cache jpeg-dev zlib-dev libjpeg && \
    if [ "$TARGETPLATFORM" = "linux/arm/v6" ] || [ "$TARGETPLATFORM" = "linux/arm/v7" ]; then \
        apk add --no-cache --virtual .build-deps; \
    fi && \
    apk add --no-cache gcc musl-dev python3-dev && \
    pip install -r requirements.txt && \
    apk del gcc musl-dev python3-dev

LABEL maintainer="Discord: the_devil_of_the_rhine (863687441809801246)"
LABEL commit=$COMMIT
LABEL description="Discord Bot for automatically assigning users a role after they complete a captcha."
LABEL release=$BUILD_DATE
LABEL version="1.1.0"
LABEL url="https://gitlab.bloodygang.com/Serpensin/DiscordBots-Bouncer"

CMD ["python3", "main.py"]