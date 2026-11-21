#!/usr/bin/env python3
"""
Dashboard Screenshot - Home Assistant app.

Takes screenshots of one or more (Home Assistant) dashboards with headless
Chromium, crops each one, and saves them to the "www/Screenshots" folder of the
Home Assistant config, where Home Assistant serves them at
/local/Screenshots/<filename>.

A single scheduler runs the snapshots one at a time, each on its own interval.

Settings come from the app's Configuration tab (/data/options.json).
The constants below are fixed behaviour; edit them here if you need to change them.
"""

import json
import os
import shutil
import sys
import time
import traceback
from dataclasses import dataclass
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
OPTIONS_FILE = "/data/options.json"             # written by the Supervisor from the app config
OUTPUT_DIR = "/homeassistant/www/Screenshots"   # = config/www/Screenshots, served by HA at /local/Screenshots/
FULL_PAGE = False                               # capture the entire scrollable page, not just the viewport
CROP_SIZE = 480                                 # crop a square this size, starting at each snapshot's x,y (0 = no crop)
HIDE_SIDEBAR = True                             # hide the Home Assistant sidebar (only applies when a token is used)
INSECURE = False                                # ignore HTTPS certificate errors (self-signed certs)
LATE_WARNING_SECONDS = 10                       # warn when a snapshot starts this much later than scheduled
# ---------------------------------------------------------------------------


@dataclass
class Snapshot:
    url: str
    filename: str
    width: int
    height: int
    x: int
    y: int
    wait: float
    interval: float
    # scheduler state
    next_due: float = 0.0
    runs: int = 0
    warned_late: bool = False


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def served_url(snap):
    rel = os.path.relpath(os.path.join(OUTPUT_DIR, snap.filename), "/homeassistant/www")
    return "/local/" + rel


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


def take_screenshot(snap, token):
    chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    chromedriver = shutil.which("chromedriver")
    if not chromium or not chromedriver:
        raise RuntimeError("Chromium or chromedriver not found in the container.")

    final_path = os.path.join(OUTPUT_DIR, snap.filename)
    # Write to a temp file first, then rename, so HA never serves a half-written image.
    tmp_path = os.path.join(OUTPUT_DIR, "." + snap.filename)

    options = Options()
    options.binary_location = chromium
    options.add_argument("--headless=new")
    options.add_argument(f"--window-size={snap.width},{snap.height}")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")             # required when running as root in a container
    options.add_argument("--disable-dev-shm-usage")  # containers have a tiny /dev/shm
    if INSECURE:
        options.add_argument("--ignore-certificate-errors")  # self-signed HTTPS

    driver = webdriver.Chrome(service=Service(executable_path=chromedriver), options=options)
    try:
        driver.set_page_load_timeout(60)
        set_viewport(driver, snap.width, snap.height)
        if token:
            inject_ha_token(driver, snap.url, token)
        driver.get(snap.url)

        if snap.wait > 0:
            time.sleep(snap.wait)  # let the dashboard cards finish rendering

        if FULL_PAGE:
            total_height = driver.execute_script(
                "return Math.max(document.body.scrollHeight,"
                " document.documentElement.scrollHeight);"
            )
            set_viewport(driver, snap.width, total_height)
            time.sleep(0.5)

        if not driver.save_screenshot(tmp_path):
            raise RuntimeError("Failed to write screenshot file.")

        if CROP_SIZE > 0:
            crop_square(tmp_path, snap.x, snap.y, CROP_SIZE)

        os.replace(tmp_path, final_path)
    finally:
        driver.quit()
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def load_snapshots(opts):
    entries = opts["snapshots"]
    if not entries:
        raise ValueError("no snapshots configured")

    snapshots, seen = [], set()
    for i, e in enumerate(entries, 1):
        snap = Snapshot(
            url=e["url"],
            filename=e["filename"],
            width=int(e["width"]),
            height=int(e["height"]),
            x=int(e["x"]),
            y=int(e["y"]),
            wait=float(e["wait"]),
            interval=float(e["interval"]),
        )
        # The schema already enforces this; checked again so a bad name can never leave OUTPUT_DIR.
        if os.path.basename(snap.filename) != snap.filename or snap.filename.startswith("."):
            raise ValueError(f"snapshot {i}: invalid filename {snap.filename!r}")
        if snap.filename.lower() in seen:
            raise ValueError(f"snapshot {i}: filename {snap.filename!r} is used more than once")
        seen.add(snap.filename.lower())
        snapshots.append(snap)
    return snapshots


def run_scheduler(snapshots, token):
    """Run the snapshots one at a time, forever. The snapshot that is due
    soonest goes next; each one is rescheduled `interval` seconds after its
    own start (or straight away if the capture took longer than that)."""
    now = time.monotonic()
    for snap in snapshots:
        snap.next_due = now  # all due at startup; they simply run in list order

    while True:
        snap = min(snapshots, key=lambda s: s.next_due)
        delay = snap.next_due - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        elif snap.runs > 0 and -delay > LATE_WARNING_SECONDS and not snap.warned_late:
            log(f"[{snap.filename}] WARNING: starting {-delay:.0f}s late. Captures run one at a time, "
                f"so the snapshots' capture times add up to more than their intervals. "
                f"Use longer intervals or fewer snapshots.")
            snap.warned_late = True

        started = time.monotonic()
        try:
            take_screenshot(snap, token)
            if snap.runs == 0:
                log(f"[{snap.filename}] First screenshot saved; further captures are only logged on errors.")
        except Exception:
            # Keep running; the previous image stays in place until a capture succeeds.
            log(f"[{snap.filename}] Screenshot failed:")
            traceback.print_exc()
        snap.runs += 1
        snap.next_due = max(started + snap.interval, time.monotonic())


def main():
    try:
        with open(OPTIONS_FILE) as f:
            opts = json.load(f)
        token = opts.get("token") or None
        snapshots = load_snapshots(opts)
    except (OSError, KeyError, ValueError, TypeError) as e:
        sys.exit(f"Invalid app configuration: {e!r}")

    if not token:
        log("WARNING: no access token configured - Home Assistant will show its login page.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for snap in snapshots:
        log(f"[{snap.filename}] {snap.url} every {snap.interval:g}s -> {OUTPUT_DIR}/{snap.filename} "
            f"(served at {served_url(snap)})")

    run_scheduler(snapshots, token)


if __name__ == "__main__":
    main()
