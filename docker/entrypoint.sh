#!/usr/bin/env bash
set -euo pipefail

cmd="${1:-web}"

wait_for_db() {
  python - <<'PY'
import os, time, socket, urllib.parse as up
url = os.environ.get("DATABASE_URL", "")
if not url.startswith("postgres"):
    raise SystemExit(0)
p = up.urlparse(url)
host, port = p.hostname or "db", p.port or 5432
deadline = time.time() + 60
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"[entrypoint] database {host}:{port} reachable")
            raise SystemExit(0)
    except OSError:
        time.sleep(1)
print("[entrypoint] database not reachable in time")
raise SystemExit(1)
PY
}

case "$cmd" in
  web)
    wait_for_db
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
    exec gunicorn family_circle.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers "${GUNICORN_WORKERS:-3}" \
        --timeout "${GUNICORN_TIMEOUT:-60}"
    ;;
  worker)
    wait_for_db
    exec celery -A family_circle worker --loglevel=INFO --concurrency="${CELERY_CONCURRENCY:-2}"
    ;;
  beat)
    wait_for_db
    exec celery -A family_circle beat --loglevel=INFO
    ;;
  bot)
    wait_for_db
    exec python -m bot.main
    ;;
  shell|manage)
    shift || true
    exec python manage.py "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
