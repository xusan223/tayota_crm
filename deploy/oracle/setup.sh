#!/usr/bin/env bash
# Provision Toyota CRM on a fresh Ubuntu 24.04 VM (Oracle Cloud Always Free).
#
#   sudo bash setup.sh <server-name>
#
# <server-name> is the host people open in the browser, for example
# 158-101-12-34.sslip.io or the bare public IP. The script can be run again:
# it keeps the generated secrets, the database and uploaded files.
#
# Layout:
#   /srv/tayota_crm           application code (git checkout) and its venv
#   /etc/tayota-crm.env       settings and secrets (root:crm, 0640)
#   /var/lib/tayota-crm       invoices (media/) and nightly backups (backups/)
#   nginx :80/:443  ->  gunicorn 127.0.0.1:8000  ->  PostgreSQL (unix socket)
set -euo pipefail

SERVER_NAME="${1:?usage: sudo bash setup.sh <server-name>}"
REPO_URL="${REPO_URL:-https://github.com/xusan223/tayota_crm.git}"
APP_USER=crm
APP_DIR=/srv/tayota_crm
ENV_FILE=/etc/tayota-crm.env
DATA_DIR=/var/lib/tayota-crm
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo bash $0 $SERVER_NAME" >&2
  exit 1
fi

log() { printf '\n=== %s ===\n' "$*"; }

log "Packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q python3-venv python3-dev build-essential libpq-dev \
  postgresql nginx git curl certbot python3-certbot-nginx netfilter-persistent

# Small shapes (1 GB RAM) need swap for pip builds.
if [[ $(awk '/MemTotal/ {print $2}' /proc/meminfo) -lt 2000000 && ! -f /swapfile ]]; then
  log "Swap (low-memory shape)"
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

log "Firewall: open 80 and 443"
# Oracle's Ubuntu images ship iptables rules that end in a REJECT; the VCN
# security list is the outer firewall, this is the inner one.
for port in 80 443; do
  if ! iptables -C INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT 2>/dev/null; then
    reject_line=$(iptables -L INPUT --line-numbers -n | awk '$2 == "REJECT" {print $1; exit}')
    if [[ -n "$reject_line" ]]; then
      iptables -I INPUT "$reject_line" -p tcp --dport "$port" -m state --state NEW -j ACCEPT
    else
      iptables -A INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT
    fi
  fi
done
netfilter-persistent save

log "Application user and folders"
id -u "$APP_USER" >/dev/null 2>&1 || \
  useradd --system --create-home --home-dir /home/$APP_USER --shell /usr/sbin/nologin "$APP_USER"
install -d -o "$APP_USER" -g "$APP_USER" -m 750 "$DATA_DIR" "$DATA_DIR/media" "$DATA_DIR/backups"

log "Code"
if [[ -d "$APP_DIR/.git" ]]; then
  sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only
else
  install -d -o "$APP_USER" -g "$APP_USER" "$APP_DIR"
  sudo -u "$APP_USER" git clone --depth 1 "$REPO_URL" "$APP_DIR"
fi
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -q --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

log "Database"
# Peer authentication over the unix socket: the OS user crm is the database
# role crm, so no database password exists to leak.
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$APP_USER'" | grep -q 1 || \
  sudo -u postgres createuser "$APP_USER"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='tayotacrm'" | grep -q 1 || \
  sudo -u postgres createdb -O "$APP_USER" tayotacrm

log "Settings"
if [[ ! -f "$ENV_FILE" ]]; then
  secret=$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')
  umask 027
  cat > "$ENV_FILE" <<EOF
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=$secret
DATABASE_URL=postgresql://$APP_USER@%2Fvar%2Frun%2Fpostgresql/tayotacrm
DJANGO_ALLOWED_HOSTS=$SERVER_NAME
DJANGO_CSRF_TRUSTED_ORIGINS=https://$SERVER_NAME,http://$SERVER_NAME
DJANGO_MEDIA_ROOT=$DATA_DIR/media
DJANGO_SERVE_HTTPS=False
DJANGO_SECURE_SSL_REDIRECT=False
# Optional: Object Storage pre-authenticated request URL (ends with /o/)
# for off-server copies of the nightly backup.
BACKUP_PAR_URL=
EOF
  umask 022
else
  sed -i "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=$SERVER_NAME|" "$ENV_FILE"
  sed -i "s|^DJANGO_CSRF_TRUSTED_ORIGINS=.*|DJANGO_CSRF_TRUSTED_ORIGINS=https://$SERVER_NAME,http://$SERVER_NAME|" "$ENV_FILE"
fi
chown root:"$APP_USER" "$ENV_FILE"
chmod 640 "$ENV_FILE"

install -m 755 "$HERE/tayota-manage" /usr/local/bin/tayota-manage
install -m 755 "$HERE/tayota-backup" /usr/local/bin/tayota-backup

log "Migrate and collect static files"
tayota-manage migrate --noinput
tayota-manage collectstatic --noinput -v 0
tayota-manage check --deploy --fail-level ERROR

log "Services"
install -m 644 "$HERE/tayota-crm.service" /etc/systemd/system/tayota-crm.service
install -m 644 "$HERE/tayota-backup.service" /etc/systemd/system/tayota-backup.service
install -m 644 "$HERE/tayota-backup.timer" /etc/systemd/system/tayota-backup.timer
sed "s|__SERVER_NAME__|$SERVER_NAME|g" "$HERE/nginx.conf" > /etc/nginx/sites-available/tayota-crm
ln -sf /etc/nginx/sites-available/tayota-crm /etc/nginx/sites-enabled/tayota-crm
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl daemon-reload
systemctl enable --now tayota-crm.service tayota-backup.timer
systemctl restart tayota-crm.service
systemctl reload nginx

log "Health"
for _ in $(seq 1 20); do
  if curl -fsS -H "Host: $SERVER_NAME" http://127.0.0.1/health/; then echo; break; fi
  sleep 1
done
echo "Done: http://$SERVER_NAME/"
