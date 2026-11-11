#!/usr/bin/env bash
set -euo pipefail

candidate_image=${1:-}

if [[ ! "$candidate_image" =~ ^ghcr\.io/keruji/tanaspace@sha256:[a-f0-9]{64}$ ]]; then
  echo "Usage: bash scripts/check-release.sh ghcr.io/keruji/tanaspace@sha256:<digest>"
  exit 1
fi

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

production_env=${PRODUCTION_ENV_FILE:-"$repo_dir/.env.production"}

if [[ ! -f "$production_env" ]]; then
  echo "Production environment file is missing: $production_env"
  exit 1
fi

export APP_IMAGE="$candidate_image"

compose=(
  docker compose
  --project-directory "$repo_dir"
  --env-file "$production_env"
  -p tanaspace_prod
  -f "$repo_dir/compose.production.yml"
)

echo "Checking production configuration..."
"${compose[@]}" config --quiet

echo "Checking that the existing production application is running..."
running=$(docker inspect tanaspace_prod-app-1 --format '{{.State.Running}}')

if [[ "$running" != "true" ]]; then
  echo "Production application is not running. Investigate before deploying."
  exit 1
fi

echo "Downloading candidate image..."
docker pull "$candidate_image"

echo "Checking Django configuration in the candidate image..."
"${compose[@]}" run --rm --no-deps -T \
  app python manage.py check --database default

echo "Checking database connectivity and pending migrations..."
if ! "${compose[@]}" run --rm --no-deps -T \
  app python manage.py migrate --check --noinput; then
  echo "STOP: database access failed or the release requires migrations."
  echo "No deployment was performed. Review the command output above."
  exit 1
fi

echo "Release preflight passed. No production containers were replaced."