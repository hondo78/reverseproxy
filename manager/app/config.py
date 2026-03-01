import os


DB_PATH = os.getenv("DB_PATH", "/data/db/proxy.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

CA_COMMON_NAME = os.getenv("CA_COMMON_NAME", "Reverse Proxy CA")
CA_VALIDITY_YEARS = int(os.getenv("CA_VALIDITY_YEARS", "10"))
CERT_VALIDITY_DAYS = int(os.getenv("CERT_VALIDITY_DAYS", "365"))

HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))

NGINX_CONTAINER_NAME = os.getenv("NGINX_CONTAINER_NAME", "reverseproxy-nginx")
NGINX_CONF_DIR = "/etc/nginx/conf.d"
CERTS_DIR = "/data/certs"
NGINX_CERTS_DIR = "/etc/nginx/certs"  # Path as seen by nginx container
CA_DIR = "/data/ca"
