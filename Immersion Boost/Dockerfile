FROM python:3.13-alpine

# Put App version into the environment so we can log it...
ARG BUILD_VERSION
ENV ADDON_VERSION=$BUILD_VERSION

COPY app.py /

CMD [ "python3", "/app.py" ]
