#!/bin/sh
set -eu

status_path=/tmp/talebook/status/status.json

printf '%s\n' '{"schema":1,"phase":"starting","steps":[]}' > "$status_path"

echo "[vercel-bootstrap] seed ephemeral demo library"
if [ ! -d /data/books ]; then
  cp -a /prebuilt/books /data/
fi

echo "[vercel-bootstrap] sync database"
/var/www/talebook/server.py --syncdb

echo "[vercel-bootstrap] migrate database"
python3 /var/www/talebook/webserver/migrate_db.py

echo "[vercel-bootstrap] update frontend config"
/var/www/talebook/server.py --update-config

echo "[vercel-bootstrap] start tornado"
supervisorctl start talebook:tornado
printf '%s\n' '{"schema":1,"phase":"ready","steps":[]}' > "$status_path"
