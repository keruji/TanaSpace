#!/bin/sh
set -eu
python manage.py migrate
(
  while true; do
    python manage.py cleanup_demo_users
    sleep 300
  done
) &
exec python manage.py runserver 0.0.0.0:8000
