#!/usr/bin/env bash
# Manual schema operation; never called by automatic deployment.
set -euo pipefail
umask 077

usage() {
  echo "Usage: bash scripts/migrate-production.sh ghcr.io/keruji/tanaspace@sha256:<digest> [--apply]"
  echo "Without --apply, show pending migrations without applying them."
}

if [[ ${1:-} == --help && $# == 1 ]]; then
  usage
  exit 0
fi
candidate_image=${1:-}
if [[ $# -lt 1 || $# -gt 2 || ! "$candidate_image" =~ ^ghcr\.io/keruji/tanaspace@sha256:[a-f0-9]{64}$ ]]; then
  usage >&2
  exit 1
fi
if [[ $# == 2 && $2 != --apply ]]; then
  usage >&2
  exit 1
fi
apply=false
if [[ ${2:-} == --apply ]]; then apply=true; fi

deployment_path=${DEPLOY_PATH:-/home/keruji/TanaSpace}
production_env=${PRODUCTION_ENV_FILE:-"$deployment_path/.env.production"}
# This must match the state directory used by deploy-release.sh.
release_state=${DEPLOY_STATE_DIR:-/home/keruji/.local/state/tanaspace}

for tool in docker python3 flock mktemp; do command -v "$tool" >/dev/null; done
if [[ ! -f "$production_env" || ! -f "$deployment_path/compose.production.yml" ]]; then
  echo "STOP: production Compose file or environment file is missing in $deployment_path." >&2
  exit 1
fi
mkdir -p "$release_state"
exec 9>"$release_state/deployment.lock"
echo "Waiting for the deployment lock (up to 60 seconds)..."
if ! flock -w 60 9; then
  echo "STOP: another deployment or schema operation holds the lock. Try again after it finishes." >&2
  exit 1
fi

work_dir=$(mktemp -d "$release_state/migration.XXXXXX")
cleanup() { rm -rf -- "$work_dir"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Older VPS Compose files build a local image and ignore APP_IMAGE. Override it
# explicitly, without editing that file or replacing the running application.
cat > "$work_dir/image.yml" <<YAML
services:
  app:
    image: $candidate_image
    pull_policy: never
YAML
export APP_IMAGE="$candidate_image"
compose=(
  docker compose
  --project-directory "$deployment_path"
  --env-file "$production_env"
  -p tanaspace_prod
  -f "$deployment_path/compose.production.yml"
  -f "$work_dir/image.yml"
)

"${compose[@]}" config --format json > "$work_dir/compose.json"
python3 - "$work_dir/compose.json" "$candidate_image" <<'PY'
import json
import sys
with open(sys.argv[1]) as source:
    selected = json.load(source)["services"]["app"]["image"]
if selected != sys.argv[2]:
    raise SystemExit("STOP: Compose did not select the requested candidate image.")
PY

echo "Candidate image: $candidate_image"
docker pull "$candidate_image"
echo "Checking candidate Django configuration..."
"${compose[@]}" run --rm --no-deps -T app python manage.py check --database default
echo "Pending migration plan:"
"${compose[@]}" run --rm --no-deps -T app python manage.py migrate --plan

if [[ "$apply" == false ]]; then
  echo "Preview complete. No migrations were applied. Review the plan, then rerun with --apply."
  exit 0
fi

echo "Applying candidate migrations to production..."
"${compose[@]}" run --rm --no-deps -T app python manage.py migrate --noinput
echo "Verifying that no candidate migrations remain pending..."
"${compose[@]}" run --rm --no-deps -T app python manage.py migrate --check --noinput
echo "Migrations completed and verified. You can now rerun the deployment workflow."
