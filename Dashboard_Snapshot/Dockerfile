FROM ghcr.io/home-assistant/base:latest

ARG BUILD_VERSION
ARG BUILD_ARCH

LABEL \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="app" \
  io.hass.arch="${BUILD_ARCH}"

ENV PYTHONUNBUFFERED=1

# Chromium + matching chromedriver from Alpine, Pillow from apk (avoids
# compiling it), Selenium (pure Python) from PyPI.
RUN \
  apk add --no-cache \
    python3 \
    py3-pip \
    py3-pillow \
    chromium \
    chromium-chromedriver \
  && pip3 install --no-cache-dir --break-system-packages "selenium>=4.20,<5"

COPY screenshot.py /app/screenshot.py
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
