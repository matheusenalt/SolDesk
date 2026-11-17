"""Tarefas independentes dos ciclos de atendimento, chamado e revisão de texto."""

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models import new_id, now


class Task(Base):
    __tablename__ = "task"
    __table_args__ = (UniqueConstraint("organization_id", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    team_id: Mapped[str | None] = mapped_column(ForeignKey("team.id"))
    client_id: Mapped[str | None] = mapped_column(ForeignKey("client.id"))
    system_id: Mapped[str | None] = mapped_column(ForeignKey("software_system.id"))
    attendance_id: Mapped[str | None] = mapped_column(ForeignKey("attendance.id"))
    ticket_id: Mapped[str | None] = mapped_column(ForeignKey("ticket.id"))
    prevista_para: Mapped[date] = mapped_column(Date)
    agendado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    status: Mapped[str] = mapped_column(String(16), default="pendente")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskEvent(Base):
    __tablename__ = "task_event"
    __table_args__ = (UniqueConstraint("task_id", "revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("task.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    revision: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(Text, default="")
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TaskReceipt(Base):
    __tablename__ = "task_receipt"
    __table_args__ = (UniqueConstraint("organization_id", "actor_id", "key_hash"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    task_id: Mapped[str] = mapped_column(ForeignKey("task.id"))
    key_hash: Mapped[str] = mapped_column(String(64))
    fingerprint: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
