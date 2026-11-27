#!/usr/bin/env bash
# Get a Let's Encrypt certificate for the server name and switch the app to
# HTTPS-only (secure cookies, HSTS, HTTP -> HTTPS redirect).
#
#   sudo bash enable-https.sh <server-name>
#
# Needs a DNS name that points at this server, e.g. 158-101-12-34.sslip.io.
# certbot installs a timer that renews the certificate automatically.
set -euo pipefail

SERVER_NAME="${1:?usage: sudo bash enable-https.sh <server-name>}"
ENV_FILE=/etc/tayota-crm.env

if [[ $EUID -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

certbot --nginx -d "$SERVER_NAME" --non-interactive --agree-tos \
  --register-unsafely-without-email --redirect

sed -i 's/^DJANGO_SERVE_HTTPS=.*/DJANGO_SERVE_HTTPS=True/' "$ENV_FILE"
sed -i 's/^DJANGO_SECURE_SSL_REDIRECT=.*/DJANGO_SECURE_SSL_REDIRECT=True/' "$ENV_FILE"
systemctl restart tayota-crm.service
systemctl reload nginx

for _ in $(seq 1 20); do
  curl -fsS "https://$SERVER_NAME/health/" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS "https://$SERVER_NAME/health/" && echo
echo "HTTPS enabled: https://$SERVER_NAME/"
