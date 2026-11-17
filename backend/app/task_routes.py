"""Tarefas simples, com datas da empresa e decisões transacionais idempotentes."""

import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import AwareDatetime, Field
from sqlalchemy import case, func, or_, select, text

from app.access import context
from app.insight_models import Team
from app.models import Client, Organization, now
from app.schemas import Input
from app.security import check_csrf, digest
from app.system_models import SoftwareSystem
from app.task_models import Task, TaskEvent, TaskReceipt
from app.work import active_member, find_record, find_ticket
from app.work_models import Attendance
from app.work_schemas import Priority

router = APIRouter(prefix="/api/v1/tasks", tags=["Tarefas"], dependencies=[Depends(check_csrf)])
Identifier = Annotated[str, Field(min_length=36, max_length=36)]
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]
State = Literal["pendente", "em_andamento", "concluida", "cancelada"]
OPEN = ("pendente", "em_andamento")


class Assignment(Input):
    assignee_id: Identifier | None = None
    team_id: Identifier | None = None


class TaskCreate(Assignment):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)
    prevista_para: date | None = None
    agendado_em: AwareDatetime | None = None
    priority: Priority = "normal"
    client_id: Identifier | None = None
    system_id: Identifier | None = None
    attendance_id: Identifier | None = None
    ticket_id: Identifier | None = None


class QuickCreate(Assignment):
    attendance_id: Identifier | None = None
    ticket_id: Identifier | None = None
    shortcut: Literal["hoje", "amanha", "proxima_semana"] = "hoje"
    horario: time | None = None
    priority: Priority = "normal"


class TaskChange(Assignment):
    revision: int = Field(ge=1)
    action: Literal["iniciar", "concluir", "cancelar", "transferir", "assumir", "editar"]
    reason: str = Field(default="", max_length=2000)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    prevista_para: date | None = None
    agendado_em: AwareDatetime | None = None
    priority: Priority | None = None


def zone(ctx):
    return ZoneInfo(ctx.db.get(Organization, ctx.organization_id).timezone)


def own_teams(ctx):
    return [t.id for t in ctx.db.scalars(ctx.query(Team)) if ctx.user.id in t.member_ids]


def query(ctx):
    q = ctx.query(Task)
    if ctx.membership.role == "tecnico":
        q = q.where(
            or_(
                Task.author_id == ctx.user.id,
                Task.assignee_id == ctx.user.id,
                Task.team_id.in_(own_teams(ctx)),
            )
        )
    return q


def assignment(ctx, body, default=False):
    person, team_id = body.assignee_id, body.team_id
    if default and person is None and team_id is None:
        person = ctx.user.id
    if (person is None) == (team_id is None):
        raise HTTPException(422, "Escolha um responsável ou uma equipe")
    if person:
        active_member(ctx, person)
    if team_id:
        team = ctx.db.scalar(ctx.query(Team).where(Team.id == team_id).with_for_update(read=True))
        if team is None:
            raise HTTPException(404, "Equipe não encontrada")
        if ctx.membership.role == "tecnico" and ctx.user.id not in team.member_ids:
            raise HTTPException(403, "Escolha uma equipe da qual você participa")
    return person, team_id


def schedule(ctx, day, instant):
    if instant:
        instant = instant.astimezone(UTC)
        local_day = instant.astimezone(zone(ctx)).date()
        if day and day != local_day:
            raise HTTPException(422, "Data e horário não correspondem no fuso da empresa")
        return local_day, instant
    if day is None:
        raise HTTPException(422, "Informe a data prevista ou um horário com fuso")
    return day, None


def snapshot(item):
    fields = (
        "id",
        "author_id",
        "title",
        "description",
        "assignee_id",
        "team_id",
        "client_id",
        "system_id",
        "attendance_id",
        "ticket_id",
        "prevista_para",
        "agendado_em",
        "priority",
        "status",
        "revision",
        "criado_em",
        "atualizado_em",
        "concluido_em",
        "cancelado_em",
    )
    return {
        f: getattr(item, f).isoformat()
        if isinstance(getattr(item, f), (date, datetime))
        else getattr(item, f)
        for f in fields
    }


def data(ctx, item):
    result = snapshot(item)
    instant, timezone = now(), zone(ctx)
    day = item.agendado_em.astimezone(timezone).date() if item.agendado_em else item.prevista_para
    overdue = (
        item.agendado_em < instant
        if item.agendado_em
        else day < instant.astimezone(timezone).date()
    )
    today = instant.astimezone(timezone).date()
    result.update(
        timezone=str(timezone),
        data_local=day.isoformat(),
        dia_inteiro=item.agendado_em is None,
        atrasada=item.status in OPEN and overdue,
        periodo="hoje" if day == today else "passada" if day < today else "futura",
    )
    return result


def replay(ctx, key, operation, body):
    fingerprint = digest(json.dumps([operation, body.model_dump(mode="json")], sort_keys=True))
    key_hash = digest(key)
    ctx.db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"{ctx.organization_id}:{ctx.user.id}:task:{key_hash}"},
    )
    prior = ctx.db.scalar(
        ctx.query(TaskReceipt).where(
            TaskReceipt.actor_id == ctx.user.id, TaskReceipt.key_hash == key_hash
        )
    )
    if prior and prior.fingerprint != fingerprint:
        raise HTTPException(409, "Idempotency-Key já usada com outra ação")
    return prior, key_hash, fingerprint


def finish(ctx, request, item, action, before, reason, key_hash, fingerprint):
    ctx.db.flush()
    after = snapshot(item)
    ctx.db.add(
        TaskEvent(
            organization_id=ctx.organization_id,
            task_id=item.id,
            actor_id=ctx.user.id,
            revision=item.revision,
            action=action,
            reason=reason,
            before=before,
            after=after,
        )
    )
    ctx.audit(request, "tarefa_" + action, "Task", item.id, before, after)
    result = data(ctx, item)
    ctx.db.add(
        TaskReceipt(
            organization_id=ctx.organization_id,
            actor_id=ctx.user.id,
            task_id=item.id,
            key_hash=key_hash,
            fingerprint=fingerprint,
            snapshot=result,
        )
    )
    ctx.db.flush()
    return result


def create_task(ctx, request, body, key_hash, fingerprint):
    if body.attendance_id and body.ticket_id:
        raise HTTPException(422, "Vincule um atendimento ou um chamado")
    source = None
    if body.attendance_id:
        from app.attendance_routes import query as attendance_query

        if ctx.db.scalar(attendance_query(ctx).where(Attendance.id == body.attendance_id)) is None:
            raise HTTPException(404, "Atendimento não encontrado")
        source = find_record(ctx, body.attendance_id)
    if body.ticket_id:
        source = find_ticket(ctx, body.ticket_id)
    client_id, system_id = body.client_id, body.system_id
    if source:
        if client_id and client_id != source.client_id:
            raise HTTPException(422, "Cliente não corresponde à origem")
        if system_id and system_id != source.system_id:
            raise HTTPException(422, "Sistema não corresponde à origem")
        client_id, system_id = source.client_id, source.system_id
    if client_id:
        ctx.get(Client, client_id)
    if system_id:
        selected = ctx.db.scalar(
            ctx.query(SoftwareSystem)
            .where(SoftwareSystem.id == system_id)
            .with_for_update(read=True)
        )
        if selected is None:
            raise HTTPException(404, "Sistema não encontrado")
        if selected.situation != "ativo" and not source:
            raise HTTPException(422, "Selecione um sistema ativo")
    person, team = assignment(ctx, body, default=True)
    day, instant = schedule(ctx, body.prevista_para, body.agendado_em)
    item = Task(
        organization_id=ctx.organization_id,
        author_id=ctx.user.id,
        title=body.title,
        description=body.description,
        assignee_id=person,
        team_id=team,
        client_id=client_id,
        system_id=system_id,
        attendance_id=body.attendance_id,
        ticket_id=body.ticket_id,
        prevista_para=day,
        agendado_em=instant,
        priority=body.priority,
    )
    ctx.db.add(item)
    return finish(ctx, request, item, "criada", {}, "", key_hash, fingerprint)


@router.post("", status_code=201)
def create(body: TaskCreate, request: Request, key: Key, ctx=Depends(context, scope="function")):
    prior, key_hash, fingerprint = replay(ctx, key, "create", body)
    return prior.snapshot if prior else create_task(ctx, request, body, key_hash, fingerprint)


@router.post("/quick", status_code=201)
def quick(body: QuickCreate, request: Request, key: Key, ctx=Depends(context, scope="function")):
    prior, key_hash, fingerprint = replay(ctx, key, "quick", body)
    if prior:
        return prior.snapshot
    if (body.attendance_id is None) == (body.ticket_id is None):
        raise HTTPException(422, "Escolha um atendimento ou um chamado de origem")
    day = now().astimezone(zone(ctx)).date() + timedelta(
        days={"hoje": 0, "amanha": 1, "proxima_semana": 7}[body.shortcut]
    )
    instant = None
    if body.horario:
        if body.horario.tzinfo:
            raise HTTPException(422, "Informe o horário local sem offset; a empresa define o fuso")
        naive = datetime.combine(day, body.horario)
        candidates = {
            naive.replace(tzinfo=zone(ctx), fold=fold).astimezone(UTC)
            for fold in (0, 1)
            if naive.replace(tzinfo=zone(ctx), fold=fold)
            .astimezone(UTC)
            .astimezone(zone(ctx))
            .replace(tzinfo=None)
            == naive
        }
        if len(candidates) != 1:
            raise HTTPException(
                422, "Horário inexistente ou ambíguo neste fuso; informe um instante explícito"
            )
        instant = candidates.pop()
    payload = body.model_dump(exclude={"shortcut", "horario"})
    return create_task(
        ctx,
        request,
        TaskCreate(title="Retornar ao cliente", prevista_para=day, agendado_em=instant, **payload),
        key_hash,
        fingerprint,
    )


@router.get("/options")
def options(ctx=Depends(context, scope="function")):
    from app.models import OrganizationMembership, User

    members = ctx.db.scalars(
        ctx.query(OrganizationMembership).where(OrganizationMembership.situation == "ativo")
    )
    return {
        "timezone": str(zone(ctx)),
        "people": [{"id": m.user_id, "name": ctx.db.get(User, m.user_id).name} for m in members],
        "teams": [
            {"id": t.id, "name": t.name}
            for t in ctx.db.scalars(ctx.query(Team))
            if ctx.membership.role != "tecnico" or ctx.user.id in t.member_ids
        ],
    }


@router.get("")
def listing(
    mine: bool = False,
    team_id: Identifier | None = None,
    assignee_id: Identifier | None = None,
    priority: Priority | None = None,
    status: State | None = None,
    period: Literal["hoje", "atrasadas", "futuras"] | None = None,
    date_from: date | None = None,
    date_until: date | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx=Depends(context, scope="function"),
):
    q = query(ctx)
    if mine:
        q = q.where(Task.assignee_id == ctx.user.id)
    for field, value in (
        (Task.team_id, team_id),
        (Task.assignee_id, assignee_id),
        (Task.priority, priority),
        (Task.status, status),
    ):
        if value:
            q = q.where(field == value)
    local_day = case(
        (Task.agendado_em.is_not(None), func.date(func.timezone(str(zone(ctx)), Task.agendado_em))),
        else_=Task.prevista_para,
    )
    today = now().astimezone(zone(ctx)).date()
    if period:
        q = q.where(Task.status.in_(OPEN))
        if period == "hoje":
            q = q.where(local_day == today)
        elif period == "futuras":
            q = q.where(local_day > today)
        else:
            q = q.where(
                or_(
                    Task.agendado_em < now(),
                    Task.agendado_em.is_(None) & (Task.prevista_para < today),
                )
            )
    if date_from and date_until and date_from > date_until:
        raise HTTPException(422, "O início do período deve anteceder o fim")
    if date_from:
        q = q.where(local_day >= date_from)
    if date_until:
        q = q.where(local_day <= date_until)
    total = ctx.db.scalar(select(func.count()).select_from(q.subquery()))
    rows = ctx.db.scalars(
        q.order_by(local_day, Task.criado_em, Task.id).offset(offset).limit(limit)
    )
    return {"total": total, "items": [data(ctx, item) for item in rows]}


def find(ctx, identifier, lock=False):
    q = query(ctx).where(Task.id == identifier)
    item = ctx.db.scalar(q.with_for_update() if lock else q)
    if item is None:
        raise HTTPException(404, "Tarefa não encontrada")
    return item


@router.get("/{identifier}")
def detail(identifier: str, ctx=Depends(context, scope="function")):
    return data(ctx, find(ctx, identifier))


@router.get("/{identifier}/history")
def history(
    identifier: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx=Depends(context, scope="function"),
):
    find(ctx, identifier)
    q = ctx.query(TaskEvent).where(TaskEvent.task_id == identifier)
    return {
        "total": ctx.db.scalar(select(func.count()).select_from(q.subquery())),
        "items": [
            {
                "id": e.id,
                "actor_id": e.actor_id,
                "action": e.action,
                "reason": e.reason,
                "revision": e.revision,
                "before": e.before,
                "after": e.after,
                "ocorrido_em": e.ocorrido_em,
            }
            for e in ctx.db.scalars(q.order_by(TaskEvent.revision).offset(offset).limit(limit))
        ],
    }


@router.post("/{identifier}/actions")
def change(
    identifier: str,
    body: TaskChange,
    request: Request,
    key: Key,
    ctx=Depends(context, scope="function"),
):
    prior, key_hash, fingerprint = replay(ctx, key, identifier, body)
    if prior:
        return prior.snapshot
    item = find(ctx, identifier, lock=True)
    if item.revision != body.revision:
        raise HTTPException(409, "Tarefa alterada. Recarregue antes de salvar")
    if item.status not in OPEN:
        raise HTTPException(409, "Tarefa já concluída ou cancelada")
    if body.action == "assumir":
        if item.team_id is None or item.team_id not in own_teams(ctx):
            raise HTTPException(403, "Somente um integrante da equipe pode assumir")
    elif ctx.membership.role == "tecnico" and item.assignee_id != ctx.user.id:
        raise HTTPException(403, "Somente responsável ou gestão pode alterar esta tarefa")
    provided = body.model_fields_set - {"revision", "action", "reason"}
    editable = {"title", "description", "prevista_para", "agendado_em", "priority"}
    allowed = (
        editable
        if body.action == "editar"
        else {"assignee_id", "team_id"}
        if body.action == "transferir"
        else set()
    )
    if provided - allowed:
        raise HTTPException(422, "Campos incompatíveis com a ação escolhida")
    before = snapshot(item)
    if body.action == "assumir":
        item.assignee_id, item.team_id = ctx.user.id, None
    elif body.action == "transferir":
        item.assignee_id, item.team_id = assignment(ctx, body)
    elif body.action == "iniciar":
        if item.status != "pendente":
            raise HTTPException(409, "Tarefa já está em andamento")
        item.status = "em_andamento"
    elif body.action == "concluir":
        item.status, item.concluido_em = "concluida", now()
    elif body.action == "cancelar":
        if not body.reason.strip():
            raise HTTPException(422, "Informe a justificativa do cancelamento")
        item.status, item.cancelado_em = "cancelada", now()
    else:
        if not provided or any(getattr(body, f) is None for f in provided - {"agendado_em"}):
            raise HTTPException(422, "Informe os campos que deseja editar")
        if provided & {"prevista_para", "agendado_em"}:
            day = (
                body.prevista_para
                if "prevista_para" in provided
                else None
                if body.agendado_em
                else item.prevista_para
            )
            instant = body.agendado_em if "agendado_em" in provided else item.agendado_em
            item.prevista_para, item.agendado_em = schedule(ctx, day, instant)
        for field in provided - {"prevista_para", "agendado_em"}:
            setattr(item, field, getattr(body, field))
    item.revision += 1
    item.atualizado_em = now()
    return finish(ctx, request, item, body.action, before, body.reason, key_hash, fingerprint)
