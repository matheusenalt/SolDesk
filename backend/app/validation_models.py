"""Fidelidade do conteúdo, independente do estado operacional."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models import new_id, now


class RecordContentVersion(Base):
    __tablename__ = "record_content_version"
    __table_args__ = (UniqueConstraint("record_id", "record_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    record_id: Mapped[str] = mapped_column(String(36), index=True)
    record_revision: Mapped[int] = mapped_column(Integer)
    source_version_id: Mapped[str] = mapped_column(String(36))
    canonical_snapshot: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ContentValidation(Base):
    __tablename__ = "content_validation"
    __table_args__ = (UniqueConstraint("version_id", "validated_by"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    record_id: Mapped[str] = mapped_column(String(36), index=True)
    version_id: Mapped[str] = mapped_column(String(36), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    validated_by: Mapped[str] = mapped_column(String(36))
    validado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
