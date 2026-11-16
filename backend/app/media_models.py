"""Arquivos privados, processamento e configuração versionada por organização."""

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

from app.database import Base
from app.models import new_id, now


class Attachment(Base):
    __tablename__ = "attachment"
    __table_args__ = (UniqueConstraint("organization_id", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    owner_type: Mapped[str] = mapped_column(String(16))
    client_id: Mapped[str | None] = mapped_column(ForeignKey("client.id"))
    ticket_id: Mapped[str | None] = mapped_column(ForeignKey("ticket.id"))
    record_id: Mapped[str | None] = mapped_column(ForeignKey("record.id"))
    kind: Mapped[str] = mapped_column(String(16))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    object_key: Mapped[str] = mapped_column(String(160), unique=True)
    storage_backend: Mapped[str] = mapped_column(String(16))
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    enviado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    purgado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TemplateVersion(Base):
    __tablename__ = "template_version"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "type", "version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    type: Mapped[str] = mapped_column(String(24))
    version: Mapped[int] = mapped_column(Integer)
    fields: Mapped[list] = mapped_column(JSON)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class GlossaryTerm(Base):
    __tablename__ = "glossary_term"
    __table_args__ = (UniqueConstraint("organization_id", "term"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    term: Mapped[str] = mapped_column(String(80))
    aliases: Mapped[list] = mapped_column(JSON)


class AudioJob(Base):
    __tablename__ = "audio_job"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    record_id: Mapped[str] = mapped_column(ForeignKey("record.id"), index=True)
    attachment_id: Mapped[str] = mapped_column(ForeignKey("attachment.id"))
    template_id: Mapped[str] = mapped_column(ForeignKey("template_version.id"))
    template_snapshot: Mapped[dict] = mapped_column(JSON)
    glossary_snapshot: Mapped[list] = mapped_column(JSON)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("audio_job.id"))
    status: Mapped[str] = mapped_column(String(24), default="aguardando")
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease: Mapped[str | None] = mapped_column(String(36))
    raw_text: Mapped[str | None] = mapped_column(Text)
    normalized_text: Mapped[str | None] = mapped_column(Text)
    organized_text: Mapped[str | None] = mapped_column(Text)
    segments: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    sections: Mapped[list] = mapped_column(JSON, default=list)
    provider_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(40))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    enfileirado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    iniciado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proxima_tentativa_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
