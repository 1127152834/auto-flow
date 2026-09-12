from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class ProxyConnectionRow(Base):
    __tablename__ = "proxy_connections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    secret_ref: Mapped[str] = mapped_column(String(240), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sync_token: Mapped[str | None] = mapped_column(String(36))
    sync_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[dict | None] = mapped_column(JSON)
    capabilities: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProxyProjectionRow(Base):
    __tablename__ = "proxy_projections"
    __table_args__ = (UniqueConstraint("connection_id", "provider_id"),)
    proxy_id: Mapped[str] = mapped_column(ForeignKey("proxies.id", ondelete="CASCADE"), primary_key=True)
    connection_id: Mapped[str] = mapped_column(ForeignKey("proxy_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(String(240), nullable=False)
    remote_name: Mapped[str] = mapped_column(String(240), nullable=False)
    name_override: Mapped[str | None] = mapped_column(String(120))
    remote_status: Mapped[str | None] = mapped_column(String(120))
    remote_missing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    carrier: Mapped[str | None] = mapped_column(String(240))
    city: Mapped[str | None] = mapped_column(String(240))
    region: Mapped[str | None] = mapped_column(String(240))
    exit_ip: Mapped[str | None] = mapped_column(String(64))
    http_host: Mapped[str | None] = mapped_column(String(255))
    http_port: Mapped[int | None] = mapped_column(Integer)
    socks5_host: Mapped[str | None] = mapped_column(String(255))
    socks5_port: Mapped[int | None] = mapped_column(Integer)
    credential_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    health_state: Mapped[str] = mapped_column(String(30), nullable=False, default="untested")
    health_latency_ms: Mapped[float | None] = mapped_column(Float)
    health_exit_ip: Mapped[str | None] = mapped_column(String(64))
    health_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    health_source: Mapped[str] = mapped_column(String(30), nullable=False, default="none")
    health_error: Mapped[dict | None] = mapped_column(JSON)
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capabilities: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProxyGroupDetailRow(Base):
    __tablename__ = "proxy_group_details"
    proxy_pool_id: Mapped[str] = mapped_column(ForeignKey("proxy_pools.id", ondelete="CASCADE"), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cursor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cursor_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProxyGroupMemberRow(Base):
    __tablename__ = "proxy_group_members"
    __table_args__ = (UniqueConstraint("group_id", "position"),)
    group_id: Mapped[str] = mapped_column(ForeignKey("proxy_pools.id", ondelete="CASCADE"), primary_key=True)
    proxy_id: Mapped[str] = mapped_column(ForeignKey("proxies.id", ondelete="RESTRICT"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class ProxyGroupResolutionRow(Base):
    __tablename__ = "proxy_group_resolutions"
    group_id: Mapped[str] = mapped_column(ForeignKey("proxy_pools.id", ondelete="CASCADE"), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    proxy_id: Mapped[str] = mapped_column(ForeignKey("proxies.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProxyOperationRow(Base):
    __tablename__ = "proxy_operations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    connection_id: Mapped[str | None] = mapped_column(String(36))
    secret_ref: Mapped[str | None] = mapped_column(String(255))
    idempotency_key: Mapped[str | None] = mapped_column(String(36), unique=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict | None] = mapped_column(JSON)
    before: Mapped[dict | None] = mapped_column(JSON)

    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    resource_revision: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
