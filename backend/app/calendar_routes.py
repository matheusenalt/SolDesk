"""Consulta da agenda e mutações exclusivas de eventos próprios."""

import json
from datetime import UTC, date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import AwareDatetime, Field
from sqlalchemy import select, text

from app.access import context
from app.calendar import event_query, page
from app.calendar_models import CalendarEvent, CalendarParticipant, CalendarReceipt, CalendarVersion
from app.insight_models import Team
from app.models import Client, now
from app.schemas import Input
from app.security import check_csrf, digest
from app.task_routes import Identifier, Key, own_teams, zone
from app.work import active_member

router = APIRouter(
    prefix="/api/v1/calendar", tags=["Calendário"], dependencies=[Depends(check_csrf)]
)


class EventContent(Input):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)
    data: date | None = None
    inicio_em: AwareDatetime | None = None
    fim_em: AwareDatetime | None = None
    assignee_id: Identifier | None = None
    participant_ids: list[Identifier] = Field(default_factory=list, max_length=200)
    client_id: Identifier | None = None


class EventEdit(EventContent):
    revision: int = Field(ge=1)


class Cancellation(Input):
    revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2000)


@router.get("")
def calendar(
    date_from: date,
    date_until: date,
    assignee_id: Identifier | None = None,
    team_id: Identifier | None = None,
    include_cancelled: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    ctx=Depends(context, scope="function"),
):
    if not 0 < (date_until - date_from).days <= 93:
        raise HTTPException(422, "Escolha um intervalo de 1 a 93 dias, com fim exclusivo")
    team = ctx.get(Team, team_id) if team_id else None
    if team and ctx.membership.role == "tecnico" and team.id not in own_teams(ctx):
        raise HTTPException(403, "Escolha uma equipe da qual você participa")
    return page(
        ctx,
        date_from,
        date_until,
        offset,
        limit,
        assignee_id=assignee_id,
        team=team,
        include_cancelled=include_cancelled,
    )


def find(ctx, identifier, lock=False):
    q = event_query(ctx).where(CalendarEvent.id == identifier)
    item = ctx.db.scalar(q.with_for_update() if lock else q)
    if item is None:
        raise HTTPException(404, "Evento não encontrado")
    return item


def snapshot(ctx, item):
    fields = (
        "id",
        "title",
        "description",
        "author_id",
        "assignee_id",
        "client_id",
        "data",
        "inicio_em",
        "fim_em",
        "status",
        "revision",
        "criado_em",
        "atualizado_em",
        "cancelado_em",
    )
    result = {
        f: getattr(item, f).isoformat()
        if hasattr(getattr(item, f), "isoformat")
        else getattr(item, f)
        for f in fields
    }
    result["participant_ids"] = sorted(
        ctx.db.scalars(
            ctx.query(CalendarParticipant)
            .with_only_columns(CalendarParticipant.user_id)
            .where(CalendarParticipant.event_id == item.id, CalendarParticipant.active.is_(True))
        )
    )
    return result


def replay(ctx, key, operation, body):
    fingerprint = digest(json.dumps([operation, body.model_dump(mode="json")], sort_keys=True))
    key_hash = digest(key)
    ctx.db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"{ctx.organization_id}:{ctx.user.id}:calendar:{key_hash}"},
    )
    prior = ctx.db.scalar(
        ctx.query(CalendarReceipt).where(
            CalendarReceipt.actor_id == ctx.user.id, CalendarReceipt.key_hash == key_hash
        )
    )
    if prior and prior.fingerprint != fingerprint:
        raise HTTPException(409, "Idempotency-Key já usada com outra operação")
    return prior, key_hash, fingerprint


def authorize(ctx, item, revision):
    if ctx.membership.role == "tecnico" and ctx.user.id not in (item.author_id, item.assignee_id):
        raise HTTPException(403, "Somente autor, responsável ou gestão pode alterar o evento")
    if item.revision != revision:
        raise HTTPException(409, "Evento alterado. Recarregue antes de salvar")
    if item.status != "ativo":
        raise HTTPException(409, "Evento cancelado não pode ser alterado")


def save_content(ctx, item, body):
    assignee = body.assignee_id or item.assignee_id or ctx.user.id
    active_member(ctx, assignee)
    participants = set(body.participant_ids)
    for user_id in participants:
        active_member(ctx, user_id)
    if body.client_id:
        ctx.get(Client, body.client_id)
    start = body.inicio_em.astimezone(UTC) if body.inicio_em else None
    end = body.fim_em.astimezone(UTC) if body.fim_em else None
    if end and (not start or end <= start):
        raise HTTPException(422, "O fim deve ser posterior ao início do evento")
    day = start.astimezone(zone(ctx)).date() if start else body.data
    if day is None or (start and body.data and body.data != day):
        raise HTTPException(422, "Informe a data correspondente ao evento no fuso da empresa")
    for field in ("title", "description", "client_id"):
        setattr(item, field, getattr(body, field))
    item.assignee_id, item.data, item.inicio_em, item.fim_em = assignee, day, start, end
    ctx.db.add(item)
    ctx.db.flush()
    existing = list(
        ctx.db.scalars(
            ctx.query(CalendarParticipant).where(CalendarParticipant.event_id == item.id)
        )
    )
    for member in existing:
        member.active = member.user_id in participants
    previous = {m.user_id for m in existing}
    for user_id in participants - previous:
        ctx.db.add(
            CalendarParticipant(
                organization_id=ctx.organization_id, event_id=item.id, user_id=user_id
            )
        )


def finish(ctx, request, item, action, before, reason, key_hash, fingerprint):
    ctx.db.flush()
    after = snapshot(ctx, item)
    ctx.db.add(
        CalendarVersion(
            organization_id=ctx.organization_id,
            event_id=item.id,
            actor_id=ctx.user.id,
            revision=item.revision,
            action=action,
            reason=reason,
            before=before,
            after=after,
        )
    )
    ctx.db.add(
        CalendarReceipt(
            organization_id=ctx.organization_id,
            event_id=item.id,
            actor_id=ctx.user.id,
            key_hash=key_hash,
            fingerprint=fingerprint,
            snapshot=after,
        )
    )
    ctx.audit(request, "agenda_" + action, "CalendarEvent", item.id, before, after)
    ctx.db.flush()
    return after


@router.post("/events", status_code=201)
def create(body: EventContent, request: Request, key: Key, ctx=Depends(context, scope="function")):
    prior, key_hash, fingerprint = replay(ctx, key, "create", body)
    if prior:
        return prior.snapshot
    item = CalendarEvent(organization_id=ctx.organization_id, author_id=ctx.user.id)
    save_content(ctx, item, body)
    return finish(ctx, request, item, "criado", {}, "", key_hash, fingerprint)


@router.get("/events/{identifier}")
def detail(identifier: str, ctx=Depends(context, scope="function")):
    return snapshot(ctx, find(ctx, identifier))


@router.put("/events/{identifier}")
def edit(
    identifier: str,
    body: EventEdit,
    request: Request,
    key: Key,
    ctx=Depends(context, scope="function"),
):
    prior, key_hash, fingerprint = replay(ctx, key, "edit:" + identifier, body)
    if prior:
        return prior.snapshot
    item = find(ctx, identifier, lock=True)
    authorize(ctx, item, body.revision)
    before = snapshot(ctx, item)
    item.revision += 1
    item.atualizado_em = now()
    save_content(ctx, item, body)
    return finish(ctx, request, item, "editado", before, "", key_hash, fingerprint)


@router.post("/events/{identifier}/cancel")
def cancel(
    identifier: str,
    body: Cancellation,
    request: Request,
    key: Key,
    ctx=Depends(context, scope="function"),
):
    prior, key_hash, fingerprint = replay(ctx, key, "cancel:" + identifier, body)
    if prior:
        return prior.snapshot
    item = find(ctx, identifier, lock=True)
    authorize(ctx, item, body.revision)
    before = snapshot(ctx, item)
    item.status, item.cancelado_em = "cancelado", now()
    item.atualizado_em = now()
    item.revision += 1
    return finish(ctx, request, item, "cancelado", before, body.reason, key_hash, fingerprint)


@router.get("/events/{identifier}/history")
def history(
    identifier: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx=Depends(context, scope="function"),
):
    find(ctx, identifier)
    q = ctx.query(CalendarVersion).where(CalendarVersion.event_id == identifier)
    return {
        "total": ctx.db.scalar(select(text("count(*)")).select_from(q.subquery())),
        "items": [
            {
                "revision": v.revision,
                "actor_id": v.actor_id,
                "action": v.action,
                "reason": v.reason,
                "before": v.before,
                "after": v.after,
                "ocorrido_em": v.ocorrido_em,
            }
            for v in ctx.db.scalars(
                q.order_by(CalendarVersion.revision).offset(offset).limit(limit)
            )
        ],
    }
