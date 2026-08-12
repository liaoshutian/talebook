#!/bin/sh
set -eu

# Vercel Functions expose only /tmp as writable space. The image contains a
# /data symlink to this runtime directory so Talebook's existing absolute paths
# keep working without changing the normal Docker deployment.
runtime_dir=/tmp/talebook
data_dir="$runtime_dir/data"

mkdir -p \
  "$data_dir" \
  "$data_dir/log/nginx" \
  "$runtime_dir/calibre" \
  "$runtime_dir/log/nginx" \
  "$runtime_dir/nginx/client_body" \
  "$runtime_dir/nginx/fastcgi" \
  "$runtime_dir/nginx/proxy" \
  "$runtime_dir/nginx/scgi" \
  "$runtime_dir/nginx/uwsgi" \
  "$runtime_dir/run" \
  "$runtime_dir/status"

cp /var/www/talebook/status/status_page.html "$runtime_dir/status/status_page.html"

export CALIBRE_CONFIG_DIRECTORY="$runtime_dir/calibre"
export PYTHONDONTWRITEBYTECODE=1
export TALEBOOK_DATA_DIR=/data
export TALEBOOK_STATUS_DIR="$runtime_dir/status"

echo "====== Start Vercel demo server ===="
exec /usr/bin/supervisord --nodaemon -u root -c /etc/supervisor/supervisord.conf
