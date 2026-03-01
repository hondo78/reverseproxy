#!/bin/sh
set -e

# Generate default self-signed cert if not present
if [ ! -f /etc/nginx/certs/default.crt ] || [ ! -f /etc/nginx/certs/default.key ]; then
    apk add --no-cache openssl > /dev/null 2>&1 || true
    openssl req -x509 -nodes -days 3650 \
        -newkey rsa:2048 \
        -keyout /etc/nginx/certs/default.key \
        -out /etc/nginx/certs/default.crt \
        -subj "/CN=localhost" \
        2>/dev/null
    echo "Generated default SSL certificate"
fi

exec nginx -g "daemon off;"
