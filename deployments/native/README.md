# Native (no Docker) deployment under a path prefix

Runs the whole Plane stack as local processes and serves it under **`https://<host>/plane`** behind
an existing HTTPS front proxy. Built for a macOS (Apple Silicon) host on a tailnet, where Docker was
not available and the host's port 443 already serves another app.

```
browser ──► front proxy :443 ──/plane/*, /plane-uploads/*──► Caddy 127.0.0.1:58080
                                                              ├─ /plane/api, /plane/auth ─► gunicorn :58000 (Django)
                                                              ├─ /plane/live/*           ─► live (node) :53100
                                                              ├─ /plane/spaces/*         ─► space (react-router-serve) :53002
                                                              ├─ /plane/god-mode/*       ─► admin static build
                                                              ├─ /plane-uploads/*        ─► MinIO :59000
                                                              └─ /plane/*                ─► web static build
Postgres :55432 · Redis :56379 (cache + Celery broker; no RabbitMQ) · Celery worker + beat
```

All services bind to 127.0.0.1; only the front proxy is reachable.

## Files

| File                       | Purpose                                                                         |
| -------------------------- | ------------------------------------------------------------------------------- |
| `plane.sh`                 | `start` / `stop` / `restart` / `status` (tmux session per service)              |
| `run-api.sh`               | Django `manage.py`, `gunicorn`, Celery `worker` / `beat` with `api.env`         |
| `build.sh`                 | builds web / admin / space / live with `build.env` baked in                     |
| `Caddyfile`                | internal proxy (prefix routing, SPA fallback, gzip/zstd, immutable asset cache) |
| `*.env.example`            | templates for `$PLANE_RUNTIME/{native,api,live,build}.env`                      |
| `planecli`, `cli_guide.md` | work items from the terminal via the stock REST API v1                          |

`$PLANE_RUNTIME` (default `~/plane-runtime`) holds binaries, data, logs and secrets — never commit it.

## Code changes for the path prefix

- `apps/web`: router `basename` and Vite `base` from `VITE_WEB_BASE_PATH` (admin and space already did this)
- `apps/web/services/api.service.ts`: the 401 redirect keeps the base path, via
  `unauthorizedRedirectURL()` in `packages/services/src/helpers/url.ts` (unit-tested)
- Backend needs no change: `APP_BASE_URL`, `*_BASE_PATH` in `api.env` drive its redirects

## Setup

1. **Binaries** in `$PLANE_RUNTIME` (arm64; Intel Homebrew under Rosetta builds from source — avoid):
   - Postgres 15: `io.zonky.test.postgres:embedded-postgres-binaries-darwin-arm64v8` (Maven Central) → `pg/`
   - Redis: build from source (`make`), copy `redis-server`, `redis-cli` → `bin/`
   - MinIO: no longer published as a binary → `GOBIN=$PLANE_RUNTIME/bin go install github.com/minio/minio@latest`
   - Caddy: GitHub release `caddy_*_mac_arm64.tar.gz` → `bin/`
   - pnpm (version from root `package.json`) → `bin/`; Python 3.12 venv → `venv/`
     (`uv pip install -r apps/api/requirements/production.txt`, drop `psycopg-c` if no `pg_config`)
2. **Config**: copy the templates to `$PLANE_RUNTIME`, fill secrets (`openssl rand -hex 32`), `chmod 600`.
   MinIO root password goes in `$PLANE_RUNTIME/.minio_pw`.
3. **Database**: `pg/bin/initdb -D data/pg -U postgres --auth=trust`, start Postgres, create role/db `plane`.
4. **Backend init**:
   ```sh
   ./run-api.sh migrate --noinput
   MACHINE_SIGNATURE=$(hostname | shasum -a 256 | cut -d' ' -f1) ./run-api.sh register_instance "$MACHINE_SIGNATURE"
   ./run-api.sh configure_instance && ./run-api.sh create_bucket && ./run-api.sh collectstatic --noinput
   ```
5. **Frontends**: `pnpm install --frozen-lockfile`, then `./build.sh`.
6. `./plane.sh start`, then open `https://<host>/plane/god-mode/` to create the instance admin
   (untick telemetry if you want none).

## Single-user mode (no login screen)

Set `AUTO_LOGIN_EMAIL` in `api.env` and restart the API: every browser request without a session
is signed in as that active user (god-mode too, if the user is an instance admin). API-key
requests (`/api/v1/`) are unaffected. Signing out just signs you back in. Anyone who can reach
the instance acts as that user, so only use it behind a trusted boundary (e.g. tailnet-only).
Implemented in `apps/api/plane/authentication/middleware/auto_login.py` (off unless the variable is set).

## Front proxy requirements

The proxy in front of Caddy must:

- forward `/plane`, `/plane/*`, `/plane-uploads/*` with the path unchanged
- **keep the original `Host`** — MinIO presigned upload URLs are signed for the public host
- set `X-Forwarded-Proto: https`
- support WebSocket upgrade and streaming (live collaboration)
- **not** send `Referrer-Policy: no-referrer` for these paths — browsers then send `Origin: null`
  on form posts and Django's CSRF check rejects sign-in. `strict-origin-when-cross-origin` works.

## Gotchas found on macOS

- Celery's default prefork pool: tasks are "received" but never run (forked children die).
  `run-api.sh` uses `-P threads -c 4`.
- Caddy binds with `SO_REUSEPORT`: an orphaned old Caddy keeps answering on the same port with an
  old config. `plane.sh` runs services with `exec` inside tmux so `stop` kills them; check
  `lsof -iTCP:58080 -sTCP:LISTEN` if responses look stale.
- `tmux kill-session` only sends SIGHUP: gunicorn treats it as "reload" and Redis/Caddy ignore it, so
  services survive as orphans that keep their ports. `plane.sh stop` sends SIGTERM first.
- The Caddy site address must be `http://:58080` (any host): with `http://127.0.0.1:58080`
  requests carrying the public `Host` get an empty 200.
- A logged-out deep link (e.g. `/plane/<workspace>/projects/`) can sit on the loading spinner;
  open `/plane/` to sign in.
- Nothing starts at boot; run `plane.sh start` after a reboot.
