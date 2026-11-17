"""Conclusão operacional não valida a fidelidade do conteúdo."""

import json
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from pydantic import Field
from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, func, select, text
from sqlalchemy.orm import Mapped, mapped_column

from app.access import context
from app.database import Base
from app.models import Organization, new_id, now
from app.schemas import Input
from app.security import check_csrf, digest
from app.task_routes import Key
from app.work import change_ticket, find_ticket, ticket_data, ticket_query
from app.work_models import Ticket, TicketEvent, TicketInterval
from app.work_schemas import TicketEdit


class TicketReceipt(Base):
    __tablename__ = "ticket_receipt"
    __table_args__ = (UniqueConstraint("organization_id", "actor_id", "key_hash"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    ticket_id: Mapped[str] = mapped_column(ForeignKey("ticket.id"))
    key_hash: Mapped[str] = mapped_column(String(64))
    fingerprint: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


router = APIRouter(prefix="/api/v1", tags=["Fluxo de chamados"], dependencies=[Depends(check_csrf)])


class Action(Input):
    revision: int = Field(ge=1)
    action: Literal[
        "iniciar",
        "aguardar_retorno",
        "retomar",
        "concluir",
        "aceitar",
        "devolver",
        "reabrir",
        "cancelar",
    ]
    description: str = Field(default="", max_length=20000)
    reason: str = Field(default="", max_length=2000)


@router.post("/tickets/{identifier}/actions")
def action(
    identifier: str,
    body: Action,
    request: Request,
    key: Key,
    ctx=Depends(context, scope="function"),
):
    fingerprint = digest(json.dumps([identifier, body.model_dump()], sort_keys=True))
    key_hash = digest(key)
    ctx.db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"{ctx.organization_id}:{ctx.user.id}:ticket:{key_hash}"},
    )
    prior = ctx.db.scalar(
        ctx.query(TicketReceipt).where(
            TicketReceipt.actor_id == ctx.user.id, TicketReceipt.key_hash == key_hash
        )
    )
    if prior:
        if prior.fingerprint != fingerprint:
            raise HTTPException(409, "Idempotency-Key já usada com outra ação")
        return prior.snapshot
    item = find_ticket(ctx, identifier, body.revision)
    if body.action == "retomar" and item.status not in {
        "aguardando_esclarecimento",
        "aguardando_terceiros",
    }:
        raise HTTPException(409, "Somente chamado aguardando retorno pode ser retomado")
    if body.action == "iniciar" and item.status not in {"aberto", "reaberto"}:
        raise HTTPException(409, "Este chamado já foi iniciado")
    targets = {
        "iniciar": "em_andamento",
        "aguardar_retorno": "aguardando_terceiros",
        "retomar": "em_andamento",
        "concluir": "resolvido",
        "aceitar": "encerrado",
        "devolver": "reaberto",
        "reabrir": "reaberto",
        "cancelar": "cancelado",
    }
    if body.action == "devolver" and item.status != "resolvido":
        raise HTTPException(409, "Somente conclusão pendente pode ser devolvida")
    if body.action == "reabrir" and item.status != "encerrado":
        raise HTTPException(409, "Somente chamado concluído pode ser reaberto")
    change_ticket(
        ctx,
        request,
        item,
        TicketEdit(
            revision=body.revision,
            status=targets[body.action],
            completion_description=body.description,
            reason=body.reason,
        ),
    )
    result = ticket_data(ctx, item)
    ctx.db.add(
        TicketReceipt(
            organization_id=ctx.organization_id,
            actor_id=ctx.user.id,
            ticket_id=item.id,
            key_hash=key_hash,
            fingerprint=fingerprint,
            snapshot=jsonable_encoder(result),
        )
    )
    ctx.db.flush()
    return result


@router.get("/ticket-monitoring")
def monitoring(
    stale_hours: int | None = Query(default=None, ge=1, le=8760),
    due_within_hours: int = Query(default=24, ge=1, le=8760),
    overdue: bool = False,
    due_soon: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx=Depends(context, scope="function"),
):
    instant = now()
    q = ticket_query(ctx).where(Ticket.status.not_in(("encerrado", "cancelado")))
    if stale_hours:
        q = q.where(
            Ticket.status.not_in(("aguardando_esclarecimento", "aguardando_terceiros")),
            Ticket.ultima_interacao_em <= instant - timedelta(hours=stale_hours),
        )
    if overdue:
        q = q.where(Ticket.prazo_em < instant)
    if due_soon:
        q = q.where(
            Ticket.prazo_em >= instant,
            Ticket.prazo_em <= instant + timedelta(hours=due_within_hours),
        )
    total = ctx.db.scalar(select(func.count()).select_from(q.subquery()))
    rows = ctx.db.scalars(
        q.order_by(Ticket.ultima_interacao_em, Ticket.id).offset(offset).limit(limit)
    )
    items = []
    for item in rows:
        row = ticket_data(ctx, item)
        waiting = ctx.db.scalar(
            ctx.query(TicketInterval).where(
                TicketInterval.ticket_id == item.id, TicketInterval.saida_em.is_(None)
            )
        )
        last = ctx.db.scalar(
            ctx.query(TicketEvent)
            .where(TicketEvent.ticket_id == item.id)
            .order_by(TicketEvent.ocorrido_em.desc(), TicketEvent.id.desc())
            .limit(1)
        )
        row.update(
            aguardando_desde_em=waiting.entrada_em if waiting else None,
            sem_atualizacao_horas=None
            if waiting
            else max(0, (instant - item.ultima_interacao_em).total_seconds() / 3600),
            ultima_interacao={
                "actor_id": last.actor_id,
                "change": last.change,
                "ocorrido_em": last.ocorrido_em,
            }
            if last
            else None,
        )
        items.append(row)
    return {"total": total, "items": items}


@router.get("/ticket-policy")
def policy(ctx=Depends(context, scope="function")):
    return {
        "self_accept": ctx.db.get(Organization, ctx.organization_id).settings.get(
            "ticket_self_accept", True
        )
    }
