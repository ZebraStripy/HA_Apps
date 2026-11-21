# Dashboard Screenshot

This app logs in to Home Assistant dashboards with a long-lived access token,
screenshots them with headless Chromium, and saves the images to the `www`
folder of your Home Assistant configuration
(`/config/www/Screenshots/`). Home Assistant serves everything in that folder
at `/local/`, so each image is available at:

```
http://<your-ha>:8123/local/Screenshots/<filename>
```

You can configure as many snapshots as you like. Each one has its own URL,
size, crop, filename and refresh interval. Each image is replaced atomically,
so you never get a half-written file.

## Getting a long-lived access token

1. In Home Assistant, click your user name at the bottom of the sidebar (or go
   to `/profile/security`).
2. Open the **Security** tab and scroll to **Long-lived access tokens**.
3. Click **Create token**, name it (for example "screenshots") and copy it
   straight away. It is only shown once.

The token has the same permissions as the user that created it. Consider
creating it from a dedicated user that can only see the dashboards you want to
capture. You can revoke it from the same page.

## Configuration

`token` is set once. Everything else is set per snapshot, inside the
`snapshots` list: use **Add** on the Configuration tab for another entry, or
edit the YAML directly:

```yaml
token: eyJ...
snapshots:
  - url: http://homeassistant:8123/dashboard-home/0
    filename: home.png
    width: 1280
    height: 800
    x: 0
    y: 0
    wait: 5
    interval: 60
  - url: http://homeassistant:8123/dashboard-energy/0
    filename: energy.png
    width: 1280
    height: 800
    x: 100
    y: 50
    wait: 8
    interval: 300
```

### Top-level option

| Option | Description |
| --- | --- |
| `token` | *(required)* Long-lived access token, used for every snapshot. |

### Options for each snapshot

| Option | Default | Description |
| --- | --- | --- |
| `url` | `http://homeassistant:8123/lovelace/0` | Full URL of the dashboard view to capture. |
| `filename` | `screenshot.png` | Name of the PNG saved in `/config/www/Screenshots/`. Letters, digits, `_` and `-` only, ending in `.png`. Must be different for every snapshot. |
| `width` | `1280` | Browser viewport width in pixels. |
| `height` | `800` | Browser viewport height in pixels. |
| `x` | `0` | Left edge, in pixels, of the crop square, measured from the left of the captured page. |
| `y` | `0` | Top edge, in pixels, of the crop square, measured from the top of the captured page. |
| `wait` | `5` | Seconds to wait after the page loads, so cards can finish rendering. |
| `interval` | `60` | Seconds between screenshots of this snapshot. |

### Which URL should I use?

From inside the app container, Home Assistant is reachable at
`http://homeassistant:8123`. Use that host rather than `homeassistant.local`,
which usually doesn't resolve inside containers. Append the path of the
dashboard view you want, for example `/lovelace/0` or `/dashboard-home/0`.

If your Home Assistant uses HTTPS, use an `https://` URL whose hostname matches
the certificate.

### The crop

Each capture is cropped to a 480×480 square. The square starts at `x`, `y` (its
top-left corner) and extends 480 pixels right and down. Set `width` and
`height` so the viewport covers it (at least `x` + 480 wide and `y` + 480
high); if the square runs past the edge, it is clipped and the image won't be
square. With `x` and `y` at 0 you get the top-left 480×480 of the page.

## How snapshots are scheduled

Snapshots are captured **one at a time** by a single scheduler, so only one
Chromium runs at once and memory use stays predictable however many snapshots
you add. At startup every snapshot is captured once, in list order. After
that, each snapshot is repeated `interval` seconds after its previous capture
started, and whichever is due soonest goes next.

A capture takes the page load time plus `wait`, so the capture times of all
your snapshots add up. If they add up to more than the shortest interval,
snapshots start late, and the log shows a warning. Use longer intervals or
fewer snapshots if that happens. A page that hangs can hold up the others for
up to a minute until it times out.

## Fixed behaviour (constants)

These are set at the top of `screenshot.py`, not in the app configuration:

| Constant | Value | Meaning |
| --- | --- | --- |
| `OUTPUT_DIR` | `/homeassistant/www/Screenshots` | Output folder (`/config/www/Screenshots` in Home Assistant). |
| `CROP_SIZE` | `480` | Size of the square cropped from each capture, starting at that snapshot's `x`, `y`. `0` disables cropping, and then `x` and `y` are ignored. |
| `HIDE_SIDEBAR` | `True` | Hides the Home Assistant sidebar before capturing. |
| `FULL_PAGE` | `False` | Capture the whole scrollable page instead of just the viewport. |
| `INSECURE` | `False` | Ignore HTTPS certificate errors (self-signed certificates). |
| `LATE_WARNING_SECONDS` | `10` | How late a snapshot may start before the log warns about it. |

Changing a constant means editing `screenshot.py` and rebuilding the app.

## Using the images

For example, in a dashboard picture card:

```yaml
type: picture
image: /local/Screenshots/home.png
```

Browsers may cache the images. If a card looks stale, force-refresh the page.

## Things to know

- **The images are public.** Files in `/config/www` are served at `/local/`
  **without authentication**. Anyone who can reach your Home Assistant URL
  (including from outside, if you expose it) can download the screenshots.
  Don't capture dashboards that show anything sensitive.
- **Folder name.** The `Screenshots` folder is created automatically. The path
  is case-sensitive, so use `/local/Screenshots/<filename>` exactly.
- **First start.** If the `www` folder didn't exist when Home Assistant
  started, restart Home Assistant once after the first screenshot is saved so
  it starts serving `/local/`.
- **Changing settings.** The app reads its configuration when it starts, so
  restart the app after saving changes.
- **Resources.** Each capture starts a fresh headless Chromium. On low-powered
  hardware use longer intervals.
- **Upgrading from 1.0.x.** The per-snapshot options moved into the
  `snapshots` list, so re-enter them inside a snapshot entry after updating.

## Troubleshooting

- **The image shows the Home Assistant login page.** The token is wrong or
  revoked, or the URL's host doesn't match what you use to reach Home
  Assistant. Check the app log.
- **The image is blank or cards are missing.** Increase that snapshot's `wait`.
- **Text or icons show as empty boxes.** The container may be missing a font
  for the characters on your dashboard.
- **"Screenshot failed" in the log.** The traceback below it says why. The
  previous image stays in place until a capture succeeds. The log line starts
  with the snapshot's filename, so you can tell which one it was.
- **The app exits at startup with "Invalid app configuration".** Check that
  there is at least one snapshot and that no two snapshots share a filename.
