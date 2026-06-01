#!/bin/sh
set -e
cd /workspace
if [ ! -f flightdeck.yaml ]; then
  flightdeck init
fi
# Railway (and some PaaS) inject PORT; local Compose defaults to 8765 via Dockerfile EXPOSE.
FD_PORT="${PORT:-8765}"
exec flightdeck serve --host 0.0.0.0 --port "$FD_PORT" "$@"
