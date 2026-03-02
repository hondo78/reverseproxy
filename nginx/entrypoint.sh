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

# Generate default catch-all server config if no configs exist yet
if [ ! -f /etc/nginx/conf.d/host__.conf ]; then
    cat > /etc/nginx/conf.d/host_default.conf <<'CONF'
# Default catch-all server (bootstrap fallback, replaced by manager)
server {
    listen 80 default_server;
    listen 443 ssl default_server;
    server_name _;

    set $route_target "-";

    ssl_certificate /etc/nginx/certs/default.crt;
    ssl_certificate_key /etc/nginx/certs/default.key;

    return 444;
}
CONF
    echo "Generated default catch-all server config"
fi

exec nginx -g "daemon off;"
