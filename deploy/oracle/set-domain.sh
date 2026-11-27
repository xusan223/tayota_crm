#!/usr/bin/env bash
# Serve the site on one or more host names with HTTPS for each of them.
#
#   sudo bash set-domain.sh husanprogrammer.uz www.husanprogrammer.uz 92-6-237-206.sslip.io
#
# The first name is the main one. Every name must already resolve to this
# server (an A record), otherwise Let's Encrypt cannot issue the certificate.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo "Run as root." >&2; exit 1; fi
if [[ $# -lt 1 ]]; then echo "usage: sudo bash $0 <name> [more names...]" >&2; exit 1; fi

ENV_FILE=/etc/tayota-crm.env
SITE=/etc/nginx/sites-available/tayota-crm
NAMES=("$@")
my_ip=$(curl -fsS https://checkip.amazonaws.com)

for name in "${NAMES[@]}"; do
  resolved=$(getent ahostsv4 "$name" | awk 'NR==1 {print $1}')
  if [[ "$resolved" != "$my_ip" ]]; then
    echo "$name resolves to '${resolved:-nothing}', not $my_ip. Fix its A record first." >&2
    exit 1
  fi
done

hosts=$(IFS=,; echo "${NAMES[*]}")
origins=$(printf 'https://%s,' "${NAMES[@]}"); origins=${origins%,}
sed -i "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=$hosts|" "$ENV_FILE"
sed -i "s|^DJANGO_CSRF_TRUSTED_ORIGINS=.*|DJANGO_CSRF_TRUSTED_ORIGINS=$origins|" "$ENV_FILE"

# Rebuild the plain-HTTP site from the template; certbot adds the TLS parts.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sed "s|__SERVER_NAME__|${NAMES[*]}|g" "$here/nginx.conf" > "$SITE"
nginx -t && systemctl reload nginx

domain_args=()
for name in "${NAMES[@]}"; do domain_args+=(-d "$name"); done
certbot --nginx "${domain_args[@]}" --cert-name tayota-crm --expand --non-interactive \
  --agree-tos --register-unsafely-without-email --redirect

sed -i 's/^DJANGO_SERVE_HTTPS=.*/DJANGO_SERVE_HTTPS=True/' "$ENV_FILE"
sed -i 's/^DJANGO_SECURE_SSL_REDIRECT=.*/DJANGO_SECURE_SSL_REDIRECT=True/' "$ENV_FILE"
systemctl restart tayota-crm.service
systemctl reload nginx

for _ in $(seq 1 20); do
  curl -fsS "https://${NAMES[0]}/health/" >/dev/null 2>&1 && break
  sleep 1
done
for name in "${NAMES[@]}"; do
  echo "https://$name/health/ -> $(curl -fsS "https://$name/health/")"
done
