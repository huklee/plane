#!/bin/bash
# Plane API runner: run-api.sh <manage.py args> | gunicorn | worker | beat
set -e
source "$(dirname "$0")/lib.sh"
set -a; source "$PLANE_RUNTIME/api.env"; set +a
cd "$PLANE_SRC/apps/api"
PY="$PLANE_RUNTIME/venv/bin"
case "$1" in
  gunicorn) exec "$PY/gunicorn" -w "$GUNICORN_WORKERS" -k uvicorn.workers.UvicornWorker plane.asgi:application --bind 127.0.0.1:58000 --max-requests 1200 --max-requests-jitter 1000 --access-logfile - ;;
  # threads pool: forked prefork children die silently on macOS (tasks "received", never run)
  worker) exec "$PY/celery" -A plane worker -P threads -c 4 -l info ;;
  beat) exec "$PY/celery" -A plane beat -l info ;;
  *) exec "$PY/python" manage.py "$@" ;;
esac
