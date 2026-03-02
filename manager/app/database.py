from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    route_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "path" or "host"
    match_pattern: Mapped[str] = mapped_column(String(512), nullable=False)
    match_host: Mapped[str | None] = mapped_column(String(512), nullable=True, default=None)
    target_host: Mapped[str] = mapped_column(String(512), nullable=False)
    target_port: Mapped[int] = mapped_column(Integer, nullable=False)
    ssl_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    certificate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    health_status: Mapped[str] = mapped_column(String(20), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    common_name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain_names: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON array
    cert_pem: Mapped[str] = mapped_column(Text, nullable=False)
    key_pem: Mapped[str] = mapped_column(Text, nullable=False)
    ca_signed: Mapped[bool] = mapped_column(Boolean, default=True)
    valid_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CertificateAuthority(Base):
    __tablename__ = "certificate_authorities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cert_pem: Mapped[str] = mapped_column(Text, nullable=False)
    key_pem: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migrate: add match_host column if missing (for existing databases)
        try:
            await conn.execute(text("ALTER TABLE routes ADD COLUMN match_host VARCHAR(512)"))
        except Exception:
            pass


async def get_db():
    async with async_session() as session:
        yield session
