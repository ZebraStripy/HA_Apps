# Dashboard Screenshot

Periodically takes a screenshot of a Home Assistant dashboard with headless
Chromium (via Selenium), crops it, and saves it to `/config/www/Screenshots/screenshot.png`
so Home Assistant serves it at `/local/Screenshots/screenshot.png`.

See the **Documentation** tab for setup, options and troubleshooting.

## Quick start

1. Create a long-lived access token (profile page → Security tab).
2. Set **Dashboard URL** and **Long-lived access token** in the app configuration.
3. Start the app and open `http://<your-ha>:8123/local/Screenshots/screenshot.png`.

Supported architectures: `amd64`, `aarch64`.
