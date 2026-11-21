#!/usr/bin/env python3
"""
Dashboard Screenshot - Home Assistant app.

Periodically screenshots a (Home Assistant) dashboard with headless Chromium,
crops it, and saves it to the "www/Screenshots" folder of the Home Assistant
config, where Home Assistant serves it at /local/Screenshots/<OUTPUT_FILE>.

Settings come from the app's Configuration tab (/data/options.json).
The constants below are fixed behaviour; edit them here if you need to change them.
"""

import json
import os
import shutil
import sys
import time
import traceback
from urllib.parse import urlparse

# Stop Selenium Manager sending anonymous usage stats to plausible.io
os.environ.setdefault("SE_AVOID_STATS", "true")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from PIL import Image

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OPTIONS_FILE = "/data/options.json"   # written by the Supervisor from the app config
OUTPUT_DIR = "/homeassistant/www/Screenshots"  # = config/www/Screenshots, served by HA at /local/Screenshots/
OUTPUT_FILE = "screenshot.png"        # -> /local/Screenshots/screenshot.png
FULL_PAGE = False                     # capture the entire scrollable page, not just the viewport
CROP_SIZE = 480                       # crop a square this size, starting at the configured x,y (0 = no crop)
HIDE_SIDEBAR = True                   # hide the Home Assistant sidebar (only applies when a token is used)
INSECURE = False                      # ignore HTTPS certificate errors (self-signed certs)
# ---------------------------------------------------------------------------


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def inject_ha_token(driver, url, token):
    """Make the Home Assistant frontend treat this browser as logged in.

    HA keeps its login in localStorage under "hassTokens". A script registered
    with Chrome runs before the page's own scripts on every new document, and
    writes the long-lived token there (only when the origin matches the HA
    server, so the token isn't planted on other sites).
    """
    parts = urlparse(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    tokens = {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": 1800,
        "hassUrl": origin,
        "clientId": origin + "/",
        "expires": 9999999999999,  # far future, so the frontend never tries to refresh
        "refresh_token": "",
    }
    sidebar_js = ""
    if HIDE_SIDEBAR:
        sidebar_js = "localStorage.setItem('dockedSidebar', '\"always_hidden\"');"
    script = (
        f"if (location.origin === {json.dumps(origin)}) {{"
        f"localStorage.setItem('hassTokens', {json.dumps(json.dumps(tokens))});"
        f"{sidebar_js}"
        f"}}"
    )
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})


def set_viewport(driver, width, height):
    """Force an exact viewport size (bypasses Chrome's minimum window width)
    and a 1:1 pixel ratio, so a 480x480 request gives a 480x480 PNG."""
    driver.execute_cdp_cmd(
        "Emulation.setDeviceMetricsOverride",
        {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False},
    )


def crop_square(path, x, y, size):
    """Crop the image at `path` in place to a size x size square whose top-left
    corner is at (x, y). The square is clipped if it runs past the image edge."""
    with Image.open(path) as img:
        w, h = img.size
        if x >= w or y >= h:
            raise ValueError(f"Crop origin ({x}, {y}) is outside the {w}x{h} capture.")
        cropped = img.crop((x, y, min(x + size, w), min(y + size, h)))
    cropped.save(path)


def take_screenshot(url, width, height, wait, token, x, y):
    chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    chromedriver = shutil.which("chromedriver")
    if not chromium or not chromedriver:
        raise RuntimeError("Chromium or chromedriver not found in the container.")

    final_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    # Write to a temp file first, then rename, so HA never serves a half-written image.
    tmp_path = os.path.join(OUTPUT_DIR, "." + OUTPUT_FILE)

    options = Options()
    options.binary_location = chromium
    options.add_argument("--headless=new")
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")             # required when running as root in a container
    options.add_argument("--disable-dev-shm-usage")  # containers have a tiny /dev/shm
    if INSECURE:
        options.add_argument("--ignore-certificate-errors")  # self-signed HTTPS

    driver = webdriver.Chrome(service=Service(executable_path=chromedriver), options=options)
    try:
        driver.set_page_load_timeout(60)
        set_viewport(driver, width, height)
        if token:
            inject_ha_token(driver, url, token)
        driver.get(url)

        if wait > 0:
            time.sleep(wait)  # let the dashboard cards finish rendering

        if FULL_PAGE:
            total_height = driver.execute_script(
                "return Math.max(document.body.scrollHeight,"
                " document.documentElement.scrollHeight);"
            )
            set_viewport(driver, width, total_height)
            time.sleep(0.5)

        if not driver.save_screenshot(tmp_path):
            raise RuntimeError("Failed to write screenshot file.")

        if CROP_SIZE > 0:
            crop_square(tmp_path, x, y, CROP_SIZE)

        os.replace(tmp_path, final_path)
    finally:
        driver.quit()
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main():
    try:
        with open(OPTIONS_FILE) as f:
            opts = json.load(f)
        url = opts["url"]
        token = opts.get("token") or None
        width = int(opts["width"])
        height = int(opts["height"])
        wait = float(opts["wait"])
        interval = float(opts["interval"])
        x = int(opts["x"])
        y = int(opts["y"])
    except (OSError, KeyError, ValueError) as e:
        sys.exit(f"Invalid app configuration: {e!r}")

    if not token:
        log("WARNING: no access token configured - Home Assistant will show its login page.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    served_at = "/local/" + os.path.relpath(os.path.join(OUTPUT_DIR, OUTPUT_FILE), "/homeassistant/www")
    log(f"Capturing {url} every {interval:g}s -> {OUTPUT_DIR}/{OUTPUT_FILE} (served at {served_at})")

    first_success = True
    while True:
        started = time.monotonic()
        try:
            take_screenshot(url, width, height, wait, token, x, y)
            if first_success:
                log("First screenshot saved; further captures are only logged on errors.")
                first_success = False
        except Exception:
            # Keep running; the previous image stays in place until a capture succeeds.
            log("Screenshot failed:")
            traceback.print_exc()
        time.sleep(max(1.0, interval - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
