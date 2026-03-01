from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import Certificate, CertificateAuthority, get_db
from ..models import CACreate, CAResponse, CertificateIssue, CertificateResponse
from ..services.ca import create_ca, get_active_ca, issue_certificate

router = APIRouter(prefix="/api", tags=["certificates"])


# --- CA Endpoints ---

@router.get("/ca", response_model=CAResponse | None)
async def get_ca(db: AsyncSession = Depends(get_db)):
    ca = await get_active_ca(db)
    return ca


@router.post("/ca/init", response_model=CAResponse, status_code=201)
async def init_ca(body: CACreate | None = None, db: AsyncSession = Depends(get_db)):
    existing = await get_active_ca(db)
    if existing:
        raise HTTPException(400, "CA already exists. Delete the existing CA first.")
    name = body.name if body else None
    ca = await create_ca(db, name)
    return ca


@router.get("/ca/download")
async def download_ca(db: AsyncSession = Depends(get_db)):
    ca = await get_active_ca(db)
    if not ca:
        raise HTTPException(404, "No CA exists")
    return Response(
        content=ca.cert_pem,
        media_type="application/x-pem-file",
        headers={"Content-Disposition": "attachment; filename=ca.crt"},
    )


# --- Certificate Endpoints ---

@router.get("/certificates", response_model=list[CertificateResponse])
async def list_certificates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Certificate).order_by(Certificate.id))
    return result.scalars().all()


@router.post("/certificates/issue", response_model=CertificateResponse, status_code=201)
async def issue_cert(body: CertificateIssue, db: AsyncSession = Depends(get_db)):
    try:
        cert = await issue_certificate(
            db,
            common_name=body.common_name,
            domain_names=body.domain_names,
            validity_days=body.validity_days,
        )
        return cert
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/certificates/{cert_id}", response_model=CertificateResponse)
async def get_certificate(cert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Certificate).where(Certificate.id == cert_id))
    cert = result.scalar_one_or_none()
    if not cert:
        raise HTTPException(404, "Certificate not found")
    return cert


@router.delete("/certificates/{cert_id}")
async def delete_certificate(cert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Certificate).where(Certificate.id == cert_id))
    cert = result.scalar_one_or_none()
    if not cert:
        raise HTTPException(404, "Certificate not found")
    await db.delete(cert)
    await db.commit()
    return {"detail": "Certificate deleted"}


@router.get("/certificates/{cert_id}/download")
async def download_certificate(cert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Certificate).where(Certificate.id == cert_id))
    cert = result.scalar_one_or_none()
    if not cert:
        raise HTTPException(404, "Certificate not found")
    safe_name = cert.common_name.replace("*", "_wildcard_").replace("/", "_")
    return Response(
        content=cert.cert_pem,
        media_type="application/x-pem-file",
        headers={"Content-Disposition": f"attachment; filename={safe_name}.crt"},
    )
