"""Somente eventos próprios da agenda; outras fontes não são copiadas."""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models import new_id, now


class CalendarEvent(Base):
    __tablename__ = "calendar_event"
    __table_args__ = (UniqueConstraint("organization_id", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    assignee_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    client_id: Mapped[str | None] = mapped_column(ForeignKey("client.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[date] = mapped_column(Date)
    inicio_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fim_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="ativo")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    cancelado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CalendarParticipant(Base):
    __tablename__ = "calendar_participant"
    __table_args__ = (UniqueConstraint("event_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("calendar_event.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CalendarVersion(Base):
    __tablename__ = "calendar_version"
    __table_args__ = (UniqueConstraint("event_id", "revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("calendar_event.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    revision: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(Text, default="")
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CalendarReceipt(Base):
    __tablename__ = "calendar_receipt"
    __table_args__ = (UniqueConstraint("organization_id", "actor_id", "key_hash"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    event_id: Mapped[str] = mapped_column(ForeignKey("calendar_event.id"))
    key_hash: Mapped[str] = mapped_column(String(64))
    fingerprint: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
