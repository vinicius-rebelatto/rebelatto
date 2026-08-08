#!/bin/sh
set -e

echo "Waiting for PostgreSQL at ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."
python <<'PY'
import os, socket, time
host = os.environ.get("POSTGRES_HOST", "db")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
deadline = time.time() + 60
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit(f"PostgreSQL unavailable at {host}:{port}")
PY

python manage.py migrate --noinput
python manage.py collectstatic --noinput

workers="${WEB_CONCURRENCY:-3}"
exec gunicorn setup.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "$workers" \
  --access-logfile - \
  --error-logfile -
