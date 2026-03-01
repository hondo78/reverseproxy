import json
import os
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import CA_COMMON_NAME, CA_DIR, CA_VALIDITY_YEARS, CERT_VALIDITY_DAYS, CERTS_DIR
from ..database import Certificate, CertificateAuthority


async def get_active_ca(db: AsyncSession) -> CertificateAuthority | None:
    result = await db.execute(
        select(CertificateAuthority).order_by(CertificateAuthority.id.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def create_ca(db: AsyncSession, name: str | None = None) -> CertificateAuthority:
    ca_name = name or CA_COMMON_NAME

    # Generate RSA 4096 key
    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, ca_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Reverse Proxy Manager"),
    ])

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365 * CA_VALIDITY_YEARS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_cert_sign=True, crl_sign=True,
                content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False,
                encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()

    # Save to filesystem
    os.makedirs(CA_DIR, exist_ok=True)
    with open(os.path.join(CA_DIR, "ca.crt"), "w") as f:
        f.write(cert_pem)
    with open(os.path.join(CA_DIR, "ca.key"), "w") as f:
        f.write(key_pem)
    os.chmod(os.path.join(CA_DIR, "ca.key"), 0o600)

    # Save to database
    ca = CertificateAuthority(name=ca_name, cert_pem=cert_pem, key_pem=key_pem)
    db.add(ca)
    await db.commit()
    await db.refresh(ca)
    return ca


async def issue_certificate(
    db: AsyncSession,
    common_name: str,
    domain_names: list[str] | None = None,
    validity_days: int | None = None,
) -> Certificate:
    ca = await get_active_ca(db)
    if ca is None:
        raise ValueError("No CA exists. Create a CA first.")

    # Load CA key and cert
    ca_key = serialization.load_pem_private_key(ca.key_pem.encode(), password=None)
    ca_cert = x509.load_pem_x509_certificate(ca.cert_pem.encode())

    # Generate server key (RSA 2048)
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    days = validity_days or CERT_VALIDITY_DAYS
    all_domains = [common_name] + (domain_names or [])
    # Deduplicate while preserving order
    seen = set()
    unique_domains = []
    for d in all_domains:
        if d not in seen:
            seen.add(d)
            unique_domains.append(d)

    san_names = [x509.DNSName(d) for d in unique_domains]

    now = datetime.now(timezone.utc)
    valid_until = now + timedelta(days=days)

    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]))
        .issuer_name(ca_cert.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(valid_until)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName(san_names), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    key_pem = server_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()

    # Save to filesystem
    os.makedirs(CERTS_DIR, exist_ok=True)
    safe_name = common_name.replace("*", "_wildcard_").replace("/", "_")
    with open(os.path.join(CERTS_DIR, f"{safe_name}.crt"), "w") as f:
        f.write(cert_pem)
    with open(os.path.join(CERTS_DIR, f"{safe_name}.key"), "w") as f:
        f.write(key_pem)
    os.chmod(os.path.join(CERTS_DIR, f"{safe_name}.key"), 0o600)

    # Save to database
    db_cert = Certificate(
        common_name=common_name,
        domain_names=json.dumps(unique_domains),
        cert_pem=cert_pem,
        key_pem=key_pem,
        ca_signed=True,
        valid_until=valid_until,
    )
    db.add(db_cert)
    await db.commit()
    await db.refresh(db_cert)
    return db_cert
