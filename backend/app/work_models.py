"""Registros, chamados e notificações com revisão humana preservada."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models import new_id, now
from app.system_models import SystemFields


class Record(SystemFields, Base):
    __tablename__ = "record"
    __table_args__ = (UniqueConstraint("organization_id", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    client_id: Mapped[str | None] = mapped_column(ForeignKey("client.id"), index=True)
    internal_activity: Mapped[bool] = mapped_column(Boolean, default=False)
    author_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True)
    type: Mapped[str] = mapped_column(String(24))
    texto_original: Mapped[str] = mapped_column(Text)
    texto_organizado: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="rascunho", index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    origem_record_id: Mapped[str | None] = mapped_column(ForeignKey("record.id"))
    ticket_id: Mapped[str | None] = mapped_column(String(36))
    article_id: Mapped[str | None] = mapped_column(String(36))
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    enviado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    capturado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revisado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revisado_por: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    publicado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    template_version_id: Mapped[str | None] = mapped_column(String(36))
    ditado_texto: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80), default="")
    system: Mapped[str] = mapped_column(String(80), default="")


class Attendance(Base):
    """Ciclo operacional separado do conteúdo/revisão do registro existente."""

    __tablename__ = "attendance"
    id: Mapped[str] = mapped_column(ForeignKey("record.id"), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    assignee_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="em_andamento")
    next_action: Mapped[str] = mapped_column(Text, default="")
    retomada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)


class RecordVersion(Base):
    __tablename__ = "record_version"
    __table_args__ = (UniqueConstraint("record_id", "revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    record_id: Mapped[str] = mapped_column(ForeignKey("record.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    change: Mapped[str] = mapped_column(String(40))
    snapshot: Mapped[dict] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TicketSequence(Base):
    __tablename__ = "ticket_sequence"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)


class Ticket(SystemFields, Base):
    __tablename__ = "ticket"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "code"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    record_id: Mapped[str] = mapped_column(ForeignKey("record.id"), unique=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("client.id"), index=True)
    code: Mapped[str] = mapped_column(String(24))
    description: Mapped[str] = mapped_column(Text)
    opened_by: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    assignee_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True)
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    closed_by: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    category: Mapped[str] = mapped_column(String(80), default="")
    system: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(32), default="aberto", index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    reopen_count: Mapped[int] = mapped_column(Integer, default=0)
    aberto_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolvido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    encerrado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TicketParticipant(Base):
    __tablename__ = "ticket_participant"
    __table_args__ = (UniqueConstraint("ticket_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("ticket.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True)


class TicketComment(Base):
    __tablename__ = "ticket_comment"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("ticket.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(24), default="comentario")
    mentioned_user_ids: Mapped[list] = mapped_column(JSON, default=list)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TicketEvent(Base):
    __tablename__ = "ticket_event"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("ticket.id"), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    change: Mapped[str] = mapped_column(String(40))
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TicketInterval(Base):
    __tablename__ = "ticket_interval"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("ticket.id"), index=True)
    status: Mapped[str] = mapped_column(String(32))
    entrada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    saida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeArticle(SystemFields, Base):
    __tablename__ = "knowledge_article"
    __table_args__ = (UniqueConstraint("organization_id", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    record_id: Mapped[str] = mapped_column(ForeignKey("record.id"), unique=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    status: Mapped[str] = mapped_column(String(24), default="rascunho")
    text: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    title: Mapped[str] = mapped_column(String(200), default="")
    problem: Mapped[str] = mapped_column(Text, default="")
    context: Mapped[str] = mapped_column(Text, default="")
    confirmed_cause: Mapped[str] = mapped_column(Text, default="")
    procedure: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    category: Mapped[str] = mapped_column(String(80), default="")
    system: Mapped[str] = mapped_column(String(80), default="")
    client_id: Mapped[str | None] = mapped_column(ForeignKey("client.id"))
    template_version_id: Mapped[str | None] = mapped_column(ForeignKey("template_version.id"))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    enviado_revisao_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publicado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arquivado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_comment: Mapped[str] = mapped_column(Text, default="")
    search_text: Mapped[str] = mapped_column(Text, default="")


class Notification(Base):
    __tablename__ = "notification"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    reference_type: Mapped[str] = mapped_column(String(24))
    reference_id: Mapped[str] = mapped_column(String(36))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    lida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RequestReceipt(Base):
    __tablename__ = "request_receipt"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", "scope", "key_hash"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    scope: Mapped[str] = mapped_column(String(80))
    key_hash: Mapped[str] = mapped_column(String(64))
    fingerprint: Mapped[str] = mapped_column(String(64))
    record_id: Mapped[str] = mapped_column(ForeignKey("record.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
