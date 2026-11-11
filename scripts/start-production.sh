#!/bin/sh
set -eu

# Stop if this release requires migrations.
# Schema changes must be handled separately from application deployment.
python manage.py migrate --check --noinput

python manage.py collectstatic --noinput

(
  while true; do
    python manage.py cleanup_demo_users
    sleep 300
  done
) &

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --timeout 30 \
  --access-logfile - \
  --error-logfile -