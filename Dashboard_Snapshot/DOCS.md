# Dashboard Screenshot

This app logs in to a Home Assistant dashboard with a long-lived access token,
screenshots it with headless Chromium, and saves the image to the `www` folder
of your Home Assistant configuration (`/config/www/Screenshots/screenshot.png`). Home
Assistant serves everything in that folder at `/local/`, so the image is
available at:

```
http://<your-ha>:8123/local/Screenshots/screenshot.png
```

A new screenshot is taken every **Refresh interval** seconds. The file is
replaced atomically, so you never get a half-written image.

## Getting a long-lived access token

1. In Home Assistant, click your user name at the bottom of the sidebar (or go
   to `/profile/security`).
2. Open the **Security** tab and scroll to **Long-lived access tokens**.
3. Click **Create token**, name it (for example "screenshots") and copy it
   straight away. It is only shown once.

The token has the same permissions as the user that created it. Consider
creating it from a dedicated user that can only see the dashboard you want to
capture. You can revoke it from the same page.

## Configuration

| Option | Default | Description |
| --- | --- | --- |
| `url` | `http://homeassistant:8123/lovelace/0` | Full URL of the dashboard view to capture. |
| `token` | *(required)* | Long-lived access token. |
| `width` | `1280` | Browser viewport width in pixels. |
| `height` | `800` | Browser viewport height in pixels. |
| `wait` | `5` | Seconds to wait after the page loads, so cards can finish rendering. |
| `interval` | `60` | Seconds between screenshots. |
| `x` | `0` | Left edge, in pixels, of the crop square, measured from the left of the captured page. |
| `y` | `0` | Top edge, in pixels, of the crop square, measured from the top of the captured page. |

### Which URL should I use?

From inside the app container, Home Assistant is reachable at
`http://homeassistant:8123`. Use that host rather than `homeassistant.local`,
which usually doesn't resolve inside containers. Append the path of the
dashboard view you want, for example `/lovelace/0` or `/dashboard-home/0`.

If your Home Assistant uses HTTPS, use an `https://` URL whose hostname matches
the certificate.

## Fixed behaviour (constants)

These are set at the top of `screenshot.py`, not in the app configuration:

| Constant | Value | Meaning |
| --- | --- | --- |
| `OUTPUT_DIR` / `OUTPUT_FILE` | `/homeassistant/www/Screenshots` / `screenshot.png` | Output location (`/config/www/Screenshots/screenshot.png` in Home Assistant). |
| `CROP_SIZE` | `480` | Size of the square cropped from the capture, starting at the configured `x`, `y` (its top-left corner). `0` disables cropping, and then `x` and `y` are ignored. |
| `HIDE_SIDEBAR` | `True` | Hides the Home Assistant sidebar before capturing. |
| `FULL_PAGE` | `False` | Capture the whole scrollable page instead of just the viewport. |
| `INSECURE` | `False` | Ignore HTTPS certificate errors (self-signed certificates). |

Changing a constant means editing `screenshot.py` and rebuilding the app.

The crop square starts at `x`, `y` (its top-left corner) and extends 480 pixels
right and down. Set `width` and `height` so the viewport covers it (at least
`x` + 480 wide and `y` + 480 high); if the square runs past the edge, it is
clipped and the image won't be square. With `x` and `y` at 0 you get the
top-left 480×480 of the page.

## Using the image

For example, in a dashboard picture card:

```yaml
type: picture
image: /local/Screenshots/screenshot.png
```

Browsers may cache the image. If a card looks stale, force-refresh the page.

## Things to know

- **The image is public.** Files in `/config/www` are served at `/local/`
  **without authentication**. Anyone who can reach your Home Assistant URL
  (including from outside, if you expose it) can download the screenshot. Don't
  capture dashboards that show anything sensitive.
- **Folder name.** The `Screenshots` folder is created automatically. The path is case-sensitive, so use
  `/local/Screenshots/screenshot.png` exactly.
- **First start.** If the `www` folder didn't exist when Home Assistant started,
  restart Home Assistant once after the first screenshot is saved so it starts
  serving `/local/`.
- **Resources.** Each capture starts a fresh headless Chromium. On low-powered
  hardware use a longer interval.

## Troubleshooting

- **The image shows the Home Assistant login page.** The token is wrong or
  revoked, or the URL's host doesn't match what you use to reach Home
  Assistant. Check the app log.
- **The image is blank or cards are missing.** Increase `wait`.
- **Text or icons show as empty boxes.** The container may be missing a font
  for the characters on your dashboard.
- **"Screenshot failed" in the log.** The traceback below it says why. The
  previous image stays in place until a capture succeeds.
