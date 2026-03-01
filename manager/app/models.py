from datetime import datetime

from pydantic import BaseModel


# --- Route Schemas ---

class RouteCreate(BaseModel):
    name: str
    route_type: str  # "path" or "host"
    match_pattern: str
    target_host: str
    target_port: int
    ssl_enabled: bool = False
    certificate_id: int | None = None
    enabled: bool = True


class RouteUpdate(BaseModel):
    name: str | None = None
    route_type: str | None = None
    match_pattern: str | None = None
    target_host: str | None = None
    target_port: int | None = None
    ssl_enabled: bool | None = None
    certificate_id: int | None = None
    enabled: bool | None = None


class RouteResponse(BaseModel):
    id: int
    name: str
    route_type: str
    match_pattern: str
    target_host: str
    target_port: int
    ssl_enabled: bool
    certificate_id: int | None
    enabled: bool
    health_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Certificate Schemas ---

class CertificateIssue(BaseModel):
    common_name: str
    domain_names: list[str] = []
    validity_days: int | None = None


class CertificateResponse(BaseModel):
    id: int
    common_name: str
    domain_names: str
    ca_signed: bool
    valid_until: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# --- CA Schemas ---

class CACreate(BaseModel):
    name: str | None = None


class CAResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Health Schemas ---

class HealthStatus(BaseModel):
    route_id: int
    route_name: str
    target: str
    status: str
    enabled: bool
