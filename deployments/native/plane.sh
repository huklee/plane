#!/bin/bash
# Plane native stack (no Docker), served under $PLANE_PUBLIC_URL/plane
#   ./plane.sh start | stop | status | restart
# A front proxy on :443 must forward /plane/* and /plane-uploads/* to http://127.0.0.1:58080 (see README.md)
set -u
source "$(dirname "$0")/lib.sh"
R="$PLANE_RUNTIME"
P="$PLANE_SRC/apps"
D="$(cd "$(dirname "$0")" && pwd)"
cd "$R"

svc() { # name dir command...
  local name=$1 dir=$2; shift 2
  tmux has-session -t "plane-$name" 2>/dev/null && { echo "  plane-$name already running"; return; }
  tmux new-session -d -s "plane-$name" -c "$dir" "exec $* >> $R/logs/$name.log 2>&1"
  echo "  plane-$name started"
}

start() {
  mkdir -p logs
  if ! pg/bin/pg_ctl -D data/pg status >/dev/null 2>&1; then
    pg/bin/pg_ctl -D data/pg -o "-p 55432 -k /tmp -c listen_addresses=127.0.0.1" -l logs/postgres.log start >/dev/null && echo "  postgres started"
  fi
  svc redis "$R" bin/redis-server --port 56379 --bind 127.0.0.1 --dir "$R/data/redis" --save 60 1
  svc minio "$R" env MINIO_ROOT_USER=plane-minio MINIO_ROOT_PASSWORD="$(cat "$R/.minio_pw")" bin/minio server data/minio --address 127.0.0.1:59000 --console-address 127.0.0.1:59001
  sleep 2
  svc api "$R" "$D/run-api.sh" gunicorn
  svc worker "$R" "$D/run-api.sh" worker
  svc beat "$R" "$D/run-api.sh" beat
  svc live "$P/live" node --env-file="$R/live.env" .
  svc space "$P/space" env $(grep -v '^#' "$R/build.env" | xargs) HOST=127.0.0.1 PORT=53002 ./node_modules/.bin/react-router-serve ./build/server/index.js
  svc caddy "$R" bin/caddy run --config "$D/Caddyfile" --adapter caddyfile
}

stop() {
  for s in caddy space live beat worker api minio redis; do
    tmux kill-session -t "plane-$s" 2>/dev/null && echo "  plane-$s stopped"
  done
  pkill -f "$R/bin/caddy run" 2>/dev/null; pkill -f "celery -A plane" 2>/dev/null
  pg/bin/pg_ctl -D data/pg stop -m fast >/dev/null 2>&1 && echo "  postgres stopped"
}

status() {
  H="$PLANE_PUBLIC_URL"
  pg/bin/pg_ctl -D data/pg status >/dev/null 2>&1 && echo "  postgres   up" || echo "  postgres   DOWN"
  bin/redis-cli -p 56379 ping >/dev/null 2>&1 && echo "  redis      up" || echo "  redis      DOWN"
  for u in /plane/ /plane/god-mode/ /plane/spaces/ /plane/api/instances/ /plane/live/health; do
    printf "  %-22s %s\n" "$u" "$(curl -sk -o /dev/null -m 10 -w '%{http_code}' "$H$u")"
  done
}

case "${1:-status}" in
  start) start ;;
  stop) stop ;;
  restart) stop; sleep 2; start ;;
  status) status ;;
  *) echo "usage: $0 start|stop|restart|status"; exit 1 ;;
esac
