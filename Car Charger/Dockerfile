FROM python:3.13-alpine

# Put App version into the environment so we can log it...
ARG BUILD_VERSION
ENV ADDON_VERSION=$BUILD_VERSION

COPY Car_Charger.py   /
copy HomeAssistant.py /

CMD [ "python3", "/Car_Charger.py" ]
