"""Atendimentos contínuos: o registro é estável e cada atualização é outro registro."""

import json
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import AwareDatetime, Field
from sqlalchemy import func, or_, select, text

from app.access import context
from app.models import AuditEvent, now
from app.security import check_csrf, digest
from app.work import active_member, create_record, find_record, record_data
from app.work_models import Attendance, Record, RequestReceipt
from app.work_schemas import Occurrence, RecordCreate

router = APIRouter(prefix="/api/v1/attendances", dependencies=[Depends(check_csrf)])


class AttendanceCreate(RecordCreate):
    type: Literal["finalizacao"] = "finalizacao"
    submit: Literal[True] = True
    texto_original: str = Field(default="", max_length=20000)


class AttendanceUpdate(Occurrence):
    revision: int = Field(ge=1)
    texto_original: str = Field(default="", max_length=20000)
    next_action: str = Field(default="", max_length=20000)
    retomada_em: AwareDatetime | None = None
    action: Literal["atualizar", "transferir", "finalizar"] = "atualizar"
    assignee_id: str | None = Field(default=None, min_length=36, max_length=36)
    result: str = Field(default="", max_length=20000)


def query(ctx):
    q = ctx.query(Attendance).join(Record, Record.id == Attendance.id)
    if ctx.membership.role == "tecnico":
        q = q.where(or_(Attendance.assignee_id == ctx.user.id, Record.author_id == ctx.user.id))
    return q


def data(ctx, item):
    return {
        "id": item.id,
        "revision": item.revision,
        "assignee_id": item.assignee_id,
        "status": item.status,
        "next_action": item.next_action,
        "retomada_em": item.retomada_em,
        "finalizado_em": item.finalizado_em,
        "result": item.result,
        "pending": item.status != "finalizado"
        and (item.retomada_em is None or item.retomada_em <= now()),
        "record": record_data(ctx, find_record(ctx, item.id)),
    }


@router.post("", status_code=201)
def open_attendance(
    body: AttendanceCreate,
    request: Request,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ctx=Depends(context, scope="function"),
):
    assignee = body.assignee_id or ctx.user.id
    active_member(ctx, assignee)
    record = create_record(ctx, request, body, key, scope="attendance", allow_assignee=True)
    item = ctx.db.scalar(ctx.query(Attendance).where(Attendance.id == record.id))
    if item is None:
        item = Attendance(id=record.id, organization_id=ctx.organization_id, assignee_id=assignee)
        ctx.db.add(item)
        ctx.db.flush()
        ctx.audit(
            request,
            "atendimento_aberto",
            "Attendance",
            item.id,
            None,
            {"assignee_id": assignee, "revision": 1},
        )
    return data(ctx, item)


@router.get("")
def list_attendances(
    mine: bool = False,
    system_id: str | None = Query(default=None, min_length=36, max_length=36),
    pending: bool = False,
    status: Literal["em_andamento", "aguardando_retomada", "finalizado"] | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx=Depends(context, scope="function"),
):
    q = query(ctx)
    if system_id:
        from app.system_models import SoftwareSystem

        ctx.get(SoftwareSystem, system_id)
        q = q.where(Record.system_id == system_id)
    if mine:
        q = q.where(Attendance.assignee_id == ctx.user.id)
    if status:
        q = q.where(Attendance.status == status)
    if pending:
        q = q.where(
            Attendance.status != "finalizado",
            or_(Attendance.retomada_em.is_(None), Attendance.retomada_em <= now()),
        )
    total = ctx.db.scalar(select(func.count()).select_from(q.subquery()))
    rows = ctx.db.scalars(
        q.order_by(Record.ocorrido_em.desc(), Attendance.id).offset(offset).limit(limit)
    )
    return {"total": total, "items": [data(ctx, row) for row in rows]}


@router.get("/{identifier}")
def detail(
    identifier: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx=Depends(context, scope="function"),
):
    item = ctx.db.scalar(query(ctx).where(Attendance.id == identifier))
    if item is None:
        raise HTTPException(404, "Atendimento não encontrado")
    result = data(ctx, item)
    updates = ctx.query(Record).where(Record.origem_record_id == identifier)
    result["updates_total"] = ctx.db.scalar(select(func.count()).select_from(updates.subquery()))
    result["updates"] = [
        record_data(ctx, row)
        for row in ctx.db.scalars(
            updates.order_by(Record.enviado_em, Record.id).offset(offset).limit(limit)
        )
    ]
    events = ctx.query(AuditEvent).where(
        AuditEvent.entity == "Attendance", AuditEvent.entity_id == identifier
    )
    result["events_total"] = ctx.db.scalar(select(func.count()).select_from(events.subquery()))
    result["events"] = [
        {
            "action": event.action,
            "actor_id": event.actor_id,
            "before": event.before,
            "after": event.after,
            "ocorrido_em": event.ocorrido_em,
        }
        for event in ctx.db.scalars(
            events.order_by(AuditEvent.ocorrido_em, AuditEvent.id).offset(offset).limit(limit)
        )
    ]
    return result


@router.post("/{identifier}/updates", status_code=201)
def update(
    identifier: str,
    body: AttendanceUpdate,
    request: Request,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ctx=Depends(context, scope="function"),
):
    scope = f"attendance:{identifier}"
    key_hash = digest(key)
    fingerprint = digest(json.dumps(body.model_dump(mode="json"), sort_keys=True))
    ctx.db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"{ctx.organization_id}:{ctx.user.id}:{scope}:{key_hash}"},
    )
    item = ctx.db.scalar(
        query(ctx).where(Attendance.id == identifier).with_for_update(of=Attendance)
    )
    if item is None:
        raise HTTPException(404, "Atendimento não encontrado")
    receipt = ctx.db.scalar(
        ctx.query(RequestReceipt).where(
            RequestReceipt.user_id == ctx.user.id,
            RequestReceipt.scope == scope,
            RequestReceipt.key_hash == key_hash,
        )
    )
    if receipt:
        if receipt.fingerprint != fingerprint:
            raise HTTPException(409, "Idempotency-Key já usada com outro conteúdo")
        return {
            "attendance": data(ctx, item),
            "update": record_data(ctx, find_record(ctx, receipt.record_id)),
        }
    if ctx.membership.role == "tecnico" and item.assignee_id != ctx.user.id:
        raise HTTPException(403, "Somente responsável ou gestão pode atualizar o atendimento")
    if item.revision != body.revision:
        raise HTTPException(409, "Atendimento alterado. Recarregue antes de salvar")
    if item.status == "finalizado":
        raise HTTPException(409, "Atendimento já finalizado")
    if body.retomada_em and body.retomada_em <= now():
        raise HTTPException(422, "A retomada deve estar no futuro")
    if body.action == "finalizar" and (not body.result.strip() or body.retomada_em):
        raise HTTPException(422, "Informe o resultado e remova a retomada para finalizar")
    if body.action != "finalizar" and body.result:
        raise HTTPException(422, "Informe resultado somente ao finalizar")
    if (body.action == "transferir") != (body.assignee_id is not None):
        raise HTTPException(422, "Informe responsável somente na transferência")
    before = {
        field: getattr(item, field)
        for field in ("assignee_id", "status", "revision", "next_action", "result")
    }
    before["retomada_em"] = item.retomada_em.isoformat() if item.retomada_em else None
    source = find_record(ctx, item.id)
    child = create_record(
        ctx,
        request,
        AttendanceCreate(
            type="finalizacao",
            client_id=source.client_id,
            internal_activity=source.internal_activity,
            texto_original=body.texto_original,
            ocorrido_em=body.ocorrido_em,
            category=source.category,
            system=source.system,
        ),
        parent=source,
    )
    if body.assignee_id:
        active_member(ctx, body.assignee_id)
        item.assignee_id = body.assignee_id
    item.next_action = body.next_action
    item.retomada_em = body.retomada_em
    item.status = "aguardando_retomada" if body.retomada_em else "em_andamento"
    if body.action == "finalizar":
        item.status, item.result, item.finalizado_em = "finalizado", body.result, now()
    item.revision += 1
    ctx.db.add(
        RequestReceipt(
            organization_id=ctx.organization_id,
            user_id=ctx.user.id,
            scope=scope,
            key_hash=key_hash,
            fingerprint=fingerprint,
            record_id=child.id,
        )
    )
    after = {field: getattr(item, field) for field in before if field != "retomada_em"}
    after.update(
        {
            "retomada_em": item.retomada_em.isoformat() if item.retomada_em else None,
            "finalizado_em": item.finalizado_em.isoformat() if item.finalizado_em else None,
            "update_record_id": child.id,
        }
    )
    ctx.audit(request, f"atendimento_{body.action}", "Attendance", item.id, before, after)
    ctx.db.flush()
    return {"attendance": data(ctx, item), "update": record_data(ctx, child)}
