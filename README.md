My HA Apps.

Neil
Sept 26

---------------------
# ha-apps

Home Assistant apps (add-ons) repository. Contains one or more apps, each in
its own subfolder.

## Add this repository

Settings → Apps → App Store → ⋮ (top right) → Repositories → add this repo's URL.

## Adding a new app

1. Copy `example-app/` to `<your-app-slug>/`.
2. Edit `config.yaml` (change `name`, `slug`, `description`, `ports`, etc).
3. Edit `Dockerfile` / `run.sh` for what the app actually does.
4. Commit + push. It shows up in the store automatically — no new repo needed.
