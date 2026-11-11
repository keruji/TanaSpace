#!/usr/bin/env bash
set -euo pipefail

failed_commit=${1:-}
deployment_path=${2:-}
public_url=${3:-}

if [[ ! "$failed_commit" =~ ^[a-f0-9]{40}$ || "$public_url" != https://* ]]; then
  echo "Invalid inspection arguments." >&2
  exit 1
fi

release_state=/home/keruji/.local/state/tanaspace
exec 9>"$release_state/deployment.lock"
flock -w 60 9

test -d "$deployment_path"
current_image=$(cat "$release_state/current-image")
recorded_id=$(cat "$release_state/current-image-id")
running_id=$(docker inspect tanaspace_prod-app-1 --format '{{.Image}}')
image_id=$(docker image inspect "$current_image" --format '{{.Id}}')
running=$(docker inspect tanaspace_prod-app-1 --format '{{.State.Running}}')

if [[ "$running" != true || "$running_id" != "$recorded_id" || "$image_id" != "$recorded_id" ]]; then
  echo "Production does not match its successful release record." >&2
  exit 1
fi

current_commit=$(docker image inspect "$current_image" \
  --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}')
if [[ ! "$current_commit" =~ ^[a-f0-9]{40}$ ]]; then
  echo "Production image source commit is unknown." >&2
  exit 1
fi

for endpoint in /health/ /static/app.css /static/app.js; do
  status=$(curl --silent --show-error --output /dev/null \
    --write-out '%{http_code}' --connect-timeout 5 --max-time 10 \
    "${public_url%/}$endpoint")
  if [[ "$status" != 200 ]]; then
    echo "Production verification failed: $endpoint" >&2
    exit 1
  fi
done

python3 - "$failed_commit" "$current_commit" "$current_image" "$running_id" <<'PYTHON'
import json
import sys

print(json.dumps({
    "schema_version": 1,
    "outcome": "unchanged_healthy",
    "stage": "python_tests",
    "failed_commit": sys.argv[1],
    "current_commit": sys.argv[2],
    "current_image": sys.argv[3],
    "current_image_id": sys.argv[4],
    "health_ok": True,
    "assets_ok": True,
}, indent=2))
PYTHON
