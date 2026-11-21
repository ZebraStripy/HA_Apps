# Dashboard Screenshot

Periodically takes screenshots of Home Assistant dashboards with headless
Chromium (via Selenium), crops them, and saves them to
`/config/www/Screenshots/` so Home Assistant serves them at
`/local/Screenshots/<filename>`.

See the **Documentation** tab for setup, options and troubleshooting.

## Quick start

1. Create a long-lived access token (profile page → Security tab).
2. Set the **Long-lived access token** in the app configuration, and fill in
   the **Dashboard URL** and **Filename** of the first snapshot. Add more
   snapshot entries if you want more images.
3. Start the app and open `http://<your-ha>:8123/local/Screenshots/screenshot.png`
   (or whichever filename you chose).

Supported architectures: `amd64`, `aarch64`.
