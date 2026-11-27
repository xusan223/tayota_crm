#!/usr/bin/env bash
# Deploy the latest code from GitHub:  sudo bash /srv/tayota_crm/deploy/oracle/update.sh
set -euo pipefail

APP_DIR=/srv/tayota_crm
sudo -u crm git -C "$APP_DIR" pull --ff-only
sudo -u crm "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
install -m 755 "$APP_DIR/deploy/oracle/tayota-manage" /usr/local/bin/tayota-manage
install -m 755 "$APP_DIR/deploy/oracle/tayota-backup" /usr/local/bin/tayota-backup
tayota-manage migrate --noinput
tayota-manage collectstatic --noinput -v 0
systemctl restart tayota-crm.service
host=$(grep '^DJANGO_ALLOWED_HOSTS=' /etc/tayota-crm.env | cut -d= -f2 | cut -d, -f1)
for _ in $(seq 1 20); do
  curl -fsS --resolve "$host:443:127.0.0.1" "https://$host/health/" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS --resolve "$host:443:127.0.0.1" "https://$host/health/" && echo
echo "Updated to $(sudo -u crm git -C "$APP_DIR" log -1 --format='%h %s')"
