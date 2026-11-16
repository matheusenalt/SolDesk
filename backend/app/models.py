"""Identidade global e dados de negócio isolados por organização."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def now():
    return datetime.now(UTC)


def new_id():
    return str(uuid4())


class Organization(Base):
    __tablename__ = "organization"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    timezone: Mapped[str] = mapped_column(String(80), default="America/Sao_Paulo")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Base):
    __tablename__ = "app_user"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class OrganizationMembership(Base):
    __tablename__ = "organization_membership"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True)
    role: Mapped[str] = mapped_column(String(24))
    situation: Mapped[str] = mapped_column(String(16), default="ativo")


class AuthSession(Base):
    __tablename__ = "auth_session"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_kind: Mapped[str] = mapped_column(String(16), default="web")


class CsrfGrant(Base):
    __tablename__ = "csrf_grant"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_hash: Mapped[str | None] = mapped_column(String(64))
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthThrottle(Base):
    __tablename__ = "auth_throttle"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    window_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Invitation(Base):
    __tablename__ = "invitation"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(24))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Client(Base):
    __tablename__ = "client"
    __table_args__ = (
        UniqueConstraint("organization_id", "name_key"),
        UniqueConstraint("organization_id", "id"),
        Index("client_org_created", "organization_id", "criado_em", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    name_key: Mapped[str] = mapped_column(String(200))
    nickname: Mapped[str] = mapped_column(String(160), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    situation: Mapped[str] = mapped_column(String(16), default="ativo")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ClientExternalRef(Base):
    __tablename__ = "client_external_ref"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("client.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    identifier: Mapped[str] = mapped_column(String(200))
    label: Mapped[str] = mapped_column(String(160), default="")


class AuditEvent(Base):
    __tablename__ = "audit_event"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(36))
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    origin: Mapped[str] = mapped_column(String(80), default="cli")
