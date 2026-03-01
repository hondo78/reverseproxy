import os
import subprocess

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


async def generate_all_configs(db: AsyncSession) -> None:
    """Regenerate all nginx route config files from the database."""
    result = await db.execute(select(Route).where(Route.enabled.is_(True)))
    routes = result.scalars().all()

    # Clear existing generated configs
    os.makedirs(NGINX_CONF_DIR, exist_ok=True)
    for f in os.listdir(NGINX_CONF_DIR):
        if f.startswith("route_") and f.endswith(".conf"):
            os.remove(os.path.join(NGINX_CONF_DIR, f))

    template = _get_template()

    for route in routes:
        cert = None
        if route.ssl_enabled and route.certificate_id:
            cert_result = await db.execute(
                select(Certificate).where(Certificate.id == route.certificate_id)
            )
            cert = cert_result.scalar_one_or_none()

        config_content = template.render(
            route=route,
            cert=cert,
            certs_dir=NGINX_CERTS_DIR,
        )

        config_path = os.path.join(NGINX_CONF_DIR, f"route_{route.id}.conf")
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
