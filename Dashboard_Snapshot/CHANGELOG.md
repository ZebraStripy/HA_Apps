# Changelog

## 1.1.0

- **Breaking:** the app can now take several snapshots. `url`, `filename`, `width`, `height`, `x`, `y`, `wait` and `interval` are set per entry in a new `snapshots` list; only `token` stays at the top level. Re-enter your settings inside a snapshot entry after updating.
- New per-snapshot `filename` option (saved in `/config/www/Screenshots/`).
- Snapshots are captured one at a time by a single scheduler, each on its own interval. A warning is logged if captures can't keep up.

## 1.0.2

- New `x` and `y` options set the top-left corner of the crop square. The crop now starts at `x`, `y` instead of always using the lower-right corner.

## 1.0.1

- Output folder changed to `/config/www/Screenshots/` (image now served at `/local/Screenshots/screenshot.png`).

## 1.0.0

- Initial release.
