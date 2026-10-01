#!/bin/bash
# Build the frontends with $PLANE_RUNTIME/build.env baked in: build.sh [web admin space live]
set -e
source "$(dirname "$0")/lib.sh"
set -a; source "$PLANE_RUNTIME/build.env"; set +a
export PATH="$PLANE_RUNTIME/bin:$PATH" NODE_OPTIONS=--max-old-space-size=3072 TURBO_TELEMETRY_DISABLED=1 DO_NOT_TRACK=1
cd "$PLANE_SRC"
for app in ${@:-web admin space live}; do
  echo "=== build $app $(date +%T)"; pnpm turbo run build --filter="$app" --env-mode=loose 2>&1 | tail -6
done
