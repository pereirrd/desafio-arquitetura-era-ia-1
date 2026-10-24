#!/bin/sh
set -eu
cd /app
if [ -f /app/docker/prod_entrypoint.sh ]; then
  /app/docker/prod_entrypoint.sh --config /gateway/config.yaml --port 4000 &
else
  litellm --config /gateway/config.yaml --port 4000 &
fi
pid=$!
python /gateway/bootstrap_keys.py
touch /tmp/keys-ready
wait "$pid"
