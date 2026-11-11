#!/usr/bin/env bash
set -euo pipefail
umask 077

candidate_image=${1:-}
expected_commit=${2:-}
test_rollback=${TEST_ROLLBACK:-false}

case "$test_rollback" in
  true|false) ;;
  *)
    echo "TEST_ROLLBACK must be true or false."
    exit 1
    ;;
esac

if [[ ! "$candidate_image" =~ ^ghcr\.io/keruji/tanaspace@sha256:[a-f0-9]{64}$ ]]; then
  echo "Provide a complete application image reference pinned by digest."
  exit 1
fi

if [[ ! "$expected_commit" =~ ^[a-f0-9]{40}$ ]]; then
  echo "Provide the full source commit SHA as the second argument."
  exit 1
fi

: "${PRODUCTION_URL:?Set PRODUCTION_URL}"

if [[ "$PRODUCTION_URL" != https://* ]]; then
  echo "PRODUCTION_URL must use HTTPS."
  exit 1
fi

public_url=${PRODUCTION_URL%/}
deployment_path=${DEPLOY_PATH:-/home/keruji/TanaSpace}
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
production_env="$deployment_path/.env.production"
release_state=/home/keruji/.local/state/tanaspace

for tool in docker curl python3 flock; do
  command -v "$tool" >/dev/null
done

test -f "$production_env"
test -f "$release_state/current-image"
test -f "$release_state/current-image-id"

exec 9>"$release_state/deployment.lock"
flock -w 60 9

previous_image=$(cat "$release_state/current-image")
previous_id=$(cat "$release_state/current-image-id")
previous_commit=$(docker image inspect "$previous_image" \
  --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}')
if [[ ! "$previous_commit" =~ ^[a-f0-9]{40}$ ]]; then
  previous_commit=""
fi
previous_health_path=/

if [[ -f "$release_state/current-health-path" ]]; then
  previous_health_path=$(cat "$release_state/current-health-path")
fi

if [[ "$previous_health_path" != / && "$previous_health_path" != /health/ ]]; then
  echo "Invalid health path in the release record."
  exit 1
fi

running_id=$(docker inspect tanaspace_prod-app-1 --format '{{.Image}}')
available_previous_id=$(docker image inspect "$previous_image" --format '{{.Id}}')

if [[ "$running_id" != "$previous_id" || "$available_previous_id" != "$previous_id" ]]; then
  echo "STOP: production or the saved image differs from the release record."
  exit 1
fi

export APP_IMAGE="$candidate_image"

compose=(
  docker compose
  --project-directory "$deployment_path"
  --env-file "$production_env"
  -p tanaspace_prod
  -f "$source_dir/compose.production.yml"
)

work_dir=$(mktemp -d "$release_state/deployment.XXXXXX")
switched=0
deployment_stage=preflight

wait_for_url() {
  local path=$1
  local status
  local attempt

  for attempt in {1..20}; do
    status=$(curl --silent --output /dev/null \
      --write-out '%{http_code}' \
      --connect-timeout 5 --max-time 10 \
      "$public_url$path" || true)

    if [[ "$status" == 200 ]]; then
      return 0
    fi

    sleep 3
  done

  echo "Verification failed for: $path"
  return 1
}

record_release() {
  printf '%s\n' "$1" > "$work_dir/current-image" &&
  printf '%s\n' "$2" > "$work_dir/current-image-id" &&
  printf '%s\n' "$3" > "$work_dir/current-health-path" &&
  mv "$work_dir/current-image" "$release_state/current-image" &&
  mv "$work_dir/current-image-id" "$release_state/current-image-id" &&
  mv "$work_dir/current-health-path" "$release_state/current-health-path"
}

start_app() {
  "${compose[@]}" up \
    --no-deps --no-build --pull never \
    --force-recreate --wait --wait-timeout 120 app
}

verify_previous_image() {
  local restored_id

  restored_id=$(docker inspect tanaspace_prod-app-1 \
    --format '{{.Image}}') || return 1

  if [[ "$restored_id" != "$previous_id" ]]; then
    echo "Restored container does not match the previous image."
    return 1
  fi
}

write_result() {
  python3 - "$source_dir/deployment-result.json" "$1" "$2" \
    "$deployment_stage" "$test_rollback" "$expected_commit" \
    "$candidate_image" "$previous_image" "$previous_commit" <<'PYTHON'
import json
import os
from pathlib import Path
import sys
import tempfile

path = Path(sys.argv[1])
result = {
    "schema_version": 1,
    "outcome": sys.argv[2],
    "exit_code": int(sys.argv[3]),
    "stage": sys.argv[4],
    "test_rollback": sys.argv[5] == "true",
    "source_commit": sys.argv[6],
    "candidate_image": sys.argv[7],
    "previous_image": sys.argv[8],
    "previous_commit": sys.argv[9],
}
with tempfile.NamedTemporaryFile(
    mode="w", dir=path.parent, prefix=".deployment-result-", delete=False
) as output:
    json.dump(result, output, indent=2)
    output.write("\n")
    temporary_path = output.name
os.replace(temporary_path, path)
PYTHON
}

finish() {
  local result=$1
  local outcome=stopped_before_switch
  trap - EXIT INT TERM
  set +e

  if (( result == 0 )); then
    outcome=deployed
  elif (( switched == 1 )); then
    echo "Deployment failed. Restoring the previous application image."

    "${compose[@]}" logs --no-color --tail 80 app
    export APP_IMAGE="$previous_image"

    if start_app &&
       verify_previous_image &&
       "${compose[@]}" restart proxy &&
       wait_for_url "$previous_health_path" &&
       wait_for_url /static/app.css &&
       wait_for_url /static/app.js &&
       record_release "$previous_image" "$previous_id" "$previous_health_path"; then
      outcome=rolled_back
      if [[ "$test_rollback" == true ]]; then
        outcome=rollback_test_passed
      fi
      echo "Previous release restored and verified."
    else
      outcome=rollback_failed
      echo "RECOVERY FAILED: manual investigation is required."
    fi
  fi

  if write_result "$outcome" "$result"; then
    echo "Deployment result recorded: $outcome"
  else
    echo "ERROR: could not record the deployment result."
    result=1
  fi

  rm -rf -- "$work_dir"
  exit "$result"
}

trap 'finish $?' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "Checking that Nginx configuration is unchanged..."
cmp "$source_dir/deploy/nginx.conf" "$deployment_path/deploy/nginx.conf"

echo "Checking that production settings differ only by image selection..."
"${compose[@]}" config --format json > "$work_dir/candidate.json"

docker compose \
  --project-directory "$deployment_path" \
  --env-file "$production_env" \
  -p tanaspace_prod \
  -f "$deployment_path/compose.production.yml" \
  config --format json > "$work_dir/existing.json"

python3 - "$work_dir/existing.json" "$work_dir/candidate.json" <<'PYTHON'
import json
import sys

configs = []
for filename in sys.argv[1:]:
    with open(filename) as source:
        config = json.load(source)
    config["services"]["app"].pop("build", None)
    config["services"]["app"].pop("image", None)
    configs.append(config)

if configs[0] != configs[1]:
    raise SystemExit(
        "STOP: production configuration differs beyond image selection."
    )
PYTHON

echo "Downloading candidate image for identity verification..."
docker pull "$candidate_image"

image_commit=$(docker image inspect "$candidate_image" \
  --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}')

if [[ "$image_commit" != "$expected_commit" ]]; then
  echo "STOP: candidate image does not match the expected source commit."
  exit 1
fi

echo "Running release preflight..."
PRODUCTION_ENV_FILE="$production_env" \
  bash "$source_dir/scripts/check-release.sh" "$candidate_image"

candidate_id=$(docker image inspect "$candidate_image" --format '{{.Id}}')

echo "Verifying the existing site before deployment..."
wait_for_url "$previous_health_path"

echo "Switching application image..."
switched=1
deployment_stage=starting_application
start_app

deployment_stage=verifying_image
actual_id=$(docker inspect tanaspace_prod-app-1 --format '{{.Image}}')
if [[ "$actual_id" != "$candidate_id" ]]; then
  echo "The running application does not match the candidate image."
  exit 1
fi

deployment_stage=restarting_proxy
echo "Restarting Nginx to refresh the application connection..."
"${compose[@]}" restart proxy

echo "Verifying application readiness and frontend assets..."
deployment_stage=verifying_application
wait_for_url /health/
deployment_stage=verifying_assets
wait_for_url /static/app.css
wait_for_url /static/app.js

if [[ "$test_rollback" == true ]]; then
  deployment_stage=testing_rollback
  echo "Intentional deployment failure: testing rollback."
  exit 1
fi

deployment_stage=recording_release
echo "Recording successful release..."
record_release "$candidate_image" "$candidate_id" /health/

switched=0
echo "Deployment successful."