"""Catálogo por empresa, vínculos e decisões humanas sobre o legado."""

from datetime import datetime

from sqlalchemy import JSON, Computed, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models import new_id, now


class SoftwareSystem(Base):
    __tablename__ = "software_system"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "name_key"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    name_key: Mapped[str] = mapped_column(
        Text,
        Computed(
            "regexp_replace(btrim(public.search_normalize(name)), '\\s+', ' ', 'g')", persisted=True
        ),
    )
    description: Mapped[str] = mapped_column(Text, default="")
    manufacturer: Mapped[str] = mapped_column(String(160), default="")
    category: Mapped[str] = mapped_column(String(80), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    situation: Mapped[str] = mapped_column(String(16), default="ativo")
    revision: Mapped[int] = mapped_column(Integer, default=1)


class ClientSystem(Base):
    __tablename__ = "client_system"
    __table_args__ = (UniqueConstraint("organization_id", "client_id", "system_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("client.id"))
    system_id: Mapped[str] = mapped_column(ForeignKey("software_system.id"))
    version_in_use: Mapped[str] = mapped_column(String(160), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)


class SystemReconciliation(Base):
    __tablename__ = "system_reconciliation"
    __table_args__ = (UniqueConstraint("organization_id", "actor_id", "key_hash"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    kind: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[str] = mapped_column(String(36))
    decision: Mapped[str] = mapped_column(String(16))
    legacy_text: Mapped[str] = mapped_column(String(80))
    system_id: Mapped[str | None] = mapped_column(ForeignKey("software_system.id"))
    key_hash: Mapped[str] = mapped_column(String(64))
    fingerprint: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SystemFields:
    system_id: Mapped[str | None] = mapped_column(ForeignKey("software_system.id"))
    system_name_snapshot: Mapped[str | None] = mapped_column(String(160))
    legacy_system_snapshot: Mapped[str | None] = mapped_column(String(80))
