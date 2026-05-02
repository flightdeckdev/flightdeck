#!/bin/sh
set -e
cd /workspace
if [ ! -f flightdeck.yaml ]; then
  flightdeck init
fi
exec flightdeck serve --host 0.0.0.0 --port 8765 "$@"
