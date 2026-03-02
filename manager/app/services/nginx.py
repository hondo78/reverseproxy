import os
import re
import subprocess
from collections import defaultdict

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import CERTS_DIR, NGINX_CERTS_DIR, NGINX_CONF_DIR, NGINX_CONTAINER_NAME
from ..database import Certificate, Route

_template_env = Environment(
    loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "../../templates")),
    autoescape=False,
)


def _get_template():
    return _template_env.get_template("nginx_route.conf.j2")


def _get_effective_hostname(route: Route) -> str:
    """Return the effective hostname for grouping routes into server blocks."""
    if route.route_type == "host":
        return route.match_pattern.split(":")[0].split("/")[0]
    return route.match_host if route.match_host else "_"


def _sanitize_hostname(hostname: str) -> str:
    """Sanitize hostname for use in a config filename."""
    return re.sub(r"[^a-zA-Z0-9._-]", "_", hostname)


async def generate_all_configs(db: AsyncSession) -> None:
    """Regenerate all nginx route config files from the database."""
    result = await db.execute(select(Route).where(Route.enabled.is_(True)))
    routes = result.scalars().all()

    # Clear existing generated configs (both old route_* and new host_* patterns)
    os.makedirs(NGINX_CONF_DIR, exist_ok=True)
    for f in os.listdir(NGINX_CONF_DIR):
        if (f.startswith("route_") or f.startswith("host_")) and f.endswith(".conf"):
            os.remove(os.path.join(NGINX_CONF_DIR, f))

    # Group routes by effective hostname
    groups: dict[str, list[dict]] = defaultdict(list)
    for route in routes:
        hostname = _get_effective_hostname(route)
        location = "/" if route.route_type == "host" else route.match_pattern
        groups[hostname].append({"route": route, "location": location})

    # Load certificates for all routes that need SSL
    cert_cache: dict[int, Certificate] = {}
    for entries in groups.values():
        for entry in entries:
            route = entry["route"]
            if route.ssl_enabled and route.certificate_id and route.certificate_id not in cert_cache:
                cert_result = await db.execute(
                    select(Certificate).where(Certificate.id == route.certificate_id)
                )
                cert = cert_result.scalar_one_or_none()
                if cert:
                    cert_cache[route.certificate_id] = cert

    template = _get_template()

    # Always generate the default catch-all server (with any "_" path routes)
    default_entries = groups.pop("_", [])
    has_root_location = any(e["location"] == "/" for e in default_entries)
    config_content = template.render(
        hostname="_",
        entries=default_entries,
        ssl_cert=None,
        is_default=True,
        has_root_location=has_root_location,
        certs_dir=NGINX_CERTS_DIR,
    )
    config_path = os.path.join(NGINX_CONF_DIR, "host__.conf")
    with open(config_path, "w") as f:
        f.write(config_content)

    # Remove bootstrap fallback if it exists (replaced by host__.conf)
    fallback_path = os.path.join(NGINX_CONF_DIR, "host_default.conf")
    if os.path.exists(fallback_path):
        os.remove(fallback_path)

    for hostname, entries in groups.items():
        # Find the first SSL certificate in the group
        ssl_cert = None
        for entry in entries:
            route = entry["route"]
            if route.ssl_enabled and route.certificate_id:
                ssl_cert = cert_cache.get(route.certificate_id)
                if ssl_cert:
                    break

        config_content = template.render(
            hostname=hostname,
            entries=entries,
            ssl_cert=ssl_cert,
            is_default=False,
            has_root_location=False,
            certs_dir=NGINX_CERTS_DIR,
        )

        safe_name = _sanitize_hostname(hostname)
        config_path = os.path.join(NGINX_CONF_DIR, f"host_{safe_name}.conf")
        with open(config_path, "w") as f:
            f.write(config_content)


def validate_nginx_config() -> tuple[bool, str]:
    """Validate nginx configuration inside the nginx container."""
    try:
        result = subprocess.run(
            ["docker", "exec", NGINX_CONTAINER_NAME, "nginx", "-t"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return True, result.stderr.strip()
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "Nginx config test timed out"
    except Exception as e:
        return False, str(e)


def reload_nginx() -> tuple[bool, str]:
    """Reload nginx configuration."""
    try:
        result = subprocess.run(
            ["docker", "exec", NGINX_CONTAINER_NAME, "nginx", "-s", "reload"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return True, "Nginx reloaded successfully"
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "Nginx reload timed out"
    except Exception as e:
        return False, str(e)


async def apply_config(db: AsyncSession) -> tuple[bool, str]:
    """Generate configs, validate, and reload nginx."""
    await generate_all_configs(db)

    valid, msg = validate_nginx_config()
    if not valid:
        return False, f"Config validation failed: {msg}"

    return reload_nginx()


async def generate_default_cert() -> None:
    """Generate a self-signed default certificate for the nginx default server."""
    cert_path = os.path.join(CERTS_DIR, "default.crt")
    key_path = os.path.join(CERTS_DIR, "default.key")

    if os.path.exists(cert_path) and os.path.exists(key_path):
        return

    os.makedirs(CERTS_DIR, exist_ok=True)

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from datetime import datetime, timedelta, timezone

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(key, hashes.SHA256())
    )

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
    os.chmod(key_path, 0o600)
