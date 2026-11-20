#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Dashboard Screenshot..."
exec python3 -u /app/screenshot.py
