from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import func, select

from app.access import context
from app.models import Client, OrganizationMembership, User, now
from app.security import check_csrf
from app.work import (
    act_record,
    change_ticket,
    comment_ticket,
    create_record,
    edit_record,
    find_record,
    find_ticket,
    record_data,
    record_query,
    ticket_data,
    ticket_query,
)
from app.work_models import (
    Notification,
    Record,
    RecordVersion,
    Ticket,
    TicketComment,
    TicketEvent,
    TicketInterval,
)
from app.work_schemas import (
    BatchReview,
    CommentCreate,
    Derive,
    RecordAction,
    RecordCreate,
    RecordEdit,
    TicketCreate,
    TicketEdit,
    TicketState,
)

router = APIRouter(prefix="/api/v1", dependencies=[Depends(check_csrf)])


@router.get("/assignment-options", tags=["Registros e chamados"])
def assignment_options(ctx=Depends(context, scope="function")):
    rows = ctx.db.execute(
        ctx.query(OrganizationMembership)
        .add_columns(User.name)
        .join(
            User,
            User.id == OrganizationMembership.user_id,
        )
        .where(OrganizationMembership.situation == "ativo")
        .order_by(User.name, User.id)
    )
    return [{"id": member.user_id, "name": name} for member, name in rows]


@router.post("/records", status_code=201, tags=["Registros"])
def new_record(
    body: RecordCreate,
    request: Request,
    key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx=Depends(context, scope="function"),
):
    return record_data(ctx, create_record(ctx, request, body, key))


@router.get("/records", tags=["Registros"])
def records(
    mine: bool = True,
    status: str | None = Query(default=None, max_length=32),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx=Depends(context, scope="function"),
):
    query = record_query(ctx)
    if mine:
        query = query.where(Record.author_id == ctx.user.id)
    if status:
        query = query.where(Record.status == status)
    total = ctx.db.scalar(select(func.count()).select_from(query.subquery()))
    rows = ctx.db.scalars(
        query.order_by(Record.enviado_em.desc(), Record.id).offset(offset).limit(limit)
    )
    return {"items": [record_data(ctx, item) for item in rows], "total": total}


@router.get("/records/reviews", tags=["Registros"])
def reviews(ctx=Depends(context, scope="function"), offset: int = Query(default=0, ge=0)):
    query = record_query(ctx).where(
        Record.author_id == ctx.user.id,
        Record.type == "finalizacao",
        Record.status == "aguardando_revisao",
    )
    total = ctx.db.scalar(select(func.count()).select_from(query.subquery()))
    rows = ctx.db.scalars(query.order_by(Record.enviado_em, Record.id).offset(offset).limit(50))
    return {"items": [record_data(ctx, item) for item in rows], "total": total}


@router.post("/records/reviews/confirm", tags=["Registros"])
def batch_review(body: BatchReview, request: Request, ctx=Depends(context, scope="function")):
    from fastapi import HTTPException

    if len({item.id for item in body.items}) != len(body.items):
        raise HTTPException(422, "Não repita registros no mesmo lote")
    result = []
    for item in sorted(body.items, key=lambda entry: entry.id):
        record = find_record(ctx, item.id, item.revision)
        act_record(ctx, request, record, RecordAction(revision=item.revision, action="confirmar"))
        result.append(record_data(ctx, record))
    return {"items": result}


@router.get("/records/{identifier}", tags=["Registros"])
def record_detail(identifier: str, ctx=Depends(context, scope="function")):
    return record_data(ctx, find_record(ctx, identifier))


@router.patch("/records/{identifier}", tags=["Registros"])
def update_record(
    identifier: str, body: RecordEdit, request: Request, ctx=Depends(context, scope="function")
):
    item = find_record(ctx, identifier, body.revision)
    edit_record(ctx, request, item, body)
    return record_data(ctx, item)


@router.post("/records/{identifier}/actions", tags=["Registros"])
def record_action(
    identifier: str, body: RecordAction, request: Request, ctx=Depends(context, scope="function")
):
    item = find_record(ctx, identifier, body.revision)
    act_record(ctx, request, item, body)
    return record_data(ctx, item)


@router.get("/records/{identifier}/versions", tags=["Registros"])
def record_versions(identifier: str, ctx=Depends(context, scope="function")):
    find_record(ctx, identifier)
    rows = ctx.db.scalars(
        ctx.query(RecordVersion)
        .where(RecordVersion.record_id == identifier)
        .order_by(RecordVersion.revision)
    )
    return [
        {
            "id": item.id,
            "revision": item.revision,
            "actor_id": item.actor_id,
            "change": item.change,
            "snapshot": item.snapshot,
            "criado_em": item.criado_em,
        }
        for item in rows
    ]


@router.post("/records/{identifier}/derive", status_code=201, tags=["Registros"])
def derive_record(
    identifier: str,
    body: Derive,
    request: Request,
    key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx=Depends(context, scope="function"),
):
    source = find_record(ctx, identifier, body.revision)
    value = RecordCreate(
        client_id=source.client_id,
        type=body.type,
        texto_original=source.texto_organizado or source.texto_original,
        ocorrido_em=source.ocorrido_em,
        submit=False,
    )
    return record_data(
        ctx, create_record(ctx, request, value, key, scope=f"derive:{source.id}", source=source)
    )


@router.get("/clients/{identifier}/history", tags=["Histórico"])
def client_history(
    identifier: str,
    include_provisional: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx=Depends(context, scope="function"),
):
    ctx.get(Client, identifier)
    query = record_query(ctx).where(Record.client_id == identifier, Record.type == "finalizacao")
    confirmed = ctx.db.scalar(
        select(func.count()).select_from(query.where(Record.status == "confirmado").subquery())
    )
    if not include_provisional:
        query = query.where(Record.status == "confirmado")
    total = ctx.db.scalar(select(func.count()).select_from(query.subquery()))
    rows = ctx.db.scalars(
        query.order_by(Record.ocorrido_em.desc(), Record.id).offset(offset).limit(limit)
    )
    return {
        "confirmed_total": confirmed,
        "total": total,
        "items": [record_data(ctx, item) for item in rows],
    }


@router.post("/tickets", status_code=201, tags=["Chamados"])
def new_ticket(
    body: TicketCreate,
    request: Request,
    key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx=Depends(context, scope="function"),
):
    if not body.submit:
        from fastapi import HTTPException

        raise HTTPException(422, "Use /records para salvar rascunho sem abrir chamado")
    record = create_record(ctx, request, body, key, scope="records")
    return ticket_data(ctx, find_ticket(ctx, record.ticket_id))


@router.get("/tickets", tags=["Chamados"])
def tickets(
    status: TicketState | None = None,
    mine: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx=Depends(context, scope="function"),
):
    query = ticket_query(ctx)
    if status:
        query = query.where(Ticket.status == status)
    if mine:
        query = query.where(Ticket.assignee_id == ctx.user.id)
    total = ctx.db.scalar(select(func.count()).select_from(query.subquery()))
    rows = ctx.db.scalars(query.order_by(Ticket.aberto_em, Ticket.id).offset(offset).limit(limit))
    return {"items": [ticket_data(ctx, item) for item in rows], "total": total}


@router.get("/tickets/{identifier}", tags=["Chamados"])
def ticket_detail(identifier: str, ctx=Depends(context, scope="function")):
    item = find_ticket(ctx, identifier)
    result = ticket_data(ctx, item)
    comments = ctx.db.scalars(
        ctx.query(TicketComment)
        .where(TicketComment.ticket_id == identifier)
        .order_by(TicketComment.criado_em, TicketComment.id)
    )
    events = ctx.db.scalars(
        ctx.query(TicketEvent)
        .where(TicketEvent.ticket_id == identifier)
        .order_by(TicketEvent.ocorrido_em, TicketEvent.id)
    )
    result["comments"] = [
        {
            "id": row.id,
            "author_id": row.author_id,
            "author_name": ctx.db.get(User, row.author_id).name,
            "text": row.text,
            "kind": row.kind,
            "mentioned_user_ids": row.mentioned_user_ids,
            "criado_em": row.criado_em,
        }
        for row in comments
    ]
    result["events"] = [
        {
            "id": row.id,
            "actor_id": row.actor_id,
            "change": row.change,
            "before": row.before,
            "after": row.after,
            "ocorrido_em": row.ocorrido_em,
        }
        for row in events
    ]
    result["intervals"] = [
        {"id": row.id, "status": row.status, "entrada_em": row.entrada_em, "saida_em": row.saida_em}
        for row in ctx.db.scalars(
            ctx.query(TicketInterval)
            .where(TicketInterval.ticket_id == identifier)
            .order_by(TicketInterval.entrada_em)
        )
    ]
    return result


@router.patch("/tickets/{identifier}", tags=["Chamados"])
def update_ticket(
    identifier: str, body: TicketEdit, request: Request, ctx=Depends(context, scope="function")
):
    item = find_ticket(ctx, identifier, body.revision)
    change_ticket(ctx, request, item, body)
    return ticket_data(ctx, item)


@router.post("/tickets/{identifier}/comments", status_code=201, tags=["Chamados"])
def new_comment(
    identifier: str, body: CommentCreate, request: Request, ctx=Depends(context, scope="function")
):
    item = find_ticket(ctx, identifier, body.revision)
    comment_ticket(ctx, request, item, body)
    return ticket_data(ctx, item)


@router.get("/notifications", tags=["Notificações"])
def notifications(offset: int = Query(default=0, ge=0), ctx=Depends(context, scope="function")):
    query = ctx.query(Notification).where(Notification.user_id == ctx.user.id)
    unread = ctx.db.scalar(
        select(func.count()).select_from(query.where(Notification.lida_em.is_(None)).subquery())
    )
    rows = ctx.db.scalars(
        query.order_by(Notification.criado_em.desc(), Notification.id).offset(offset).limit(30)
    )
    return {
        "unread": unread,
        "items": [
            {
                field: getattr(item, field)
                for field in (
                    "id",
                    "type",
                    "reference_type",
                    "reference_id",
                    "criado_em",
                    "lida_em",
                )
            }
            for item in rows
        ],
    }


@router.post("/notifications/{identifier}/read", tags=["Notificações"])
def read_notification(identifier: str, ctx=Depends(context, scope="function")):
    item = ctx.get(Notification, identifier)  # RLS exige tenant E destinatário.
    if item.user_id != ctx.user.id:
        from fastapi import HTTPException

        raise HTTPException(404, "Notificação não encontrada")
    item.lida_em = item.lida_em or now()
    return {"id": item.id, "lida_em": item.lida_em}
