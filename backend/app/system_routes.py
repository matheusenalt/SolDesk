"""Catálogo, vínculos e reconciliação exclusivamente humana do texto legado."""

import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import Field, StringConstraints
from sqlalchemy import func, select, text

from app.access import context
from app.models import Client
from app.schemas import Input
from app.security import check_csrf, digest
from app.system_models import ClientSystem, SoftwareSystem, SystemReconciliation

router = APIRouter(prefix="/api/v1", tags=["Sistemas"], dependencies=[Depends(check_csrf)])
SYSTEM_FIELDS = ("system_id", "system_name_snapshot", "legacy_system_snapshot")


def management(ctx):
    if ctx.membership.role == "tecnico":
        raise HTTPException(403, "Somente a gestão administra o catálogo e os vínculos")


def normalized(ctx, value):
    return ctx.db.scalar(
        text(r"SELECT regexp_replace(btrim(public.search_normalize(:value)), '\s+', ' ', 'g')"),
        {"value": value},
    )


def system(ctx, identifier):
    item = ctx.db.scalar(
        ctx.query(SoftwareSystem).where(SoftwareSystem.id == identifier).with_for_update(read=True)
    )
    if item is None:
        raise HTTPException(404, "Sistema não encontrado")
    return item


def select_system(ctx, item, identifier):
    if identifier == item.system_id:
        return
    if identifier is None:
        for field in SYSTEM_FIELDS:
            setattr(item, field, None)
        return
    selected = system(ctx, identifier)
    if selected.situation != "ativo":
        raise HTTPException(422, "Sistema inativo não pode ser escolhido em novo vínculo")
    item.system_id = selected.id
    item.system_name_snapshot = selected.name
    item.legacy_system_snapshot = item.system


def copy_system(source, target):
    for field in SYSTEM_FIELDS:
        setattr(target, field, getattr(source, field))


def data(item):
    return {
        field: getattr(item, field)
        for field in (
            "id",
            "name",
            "description",
            "manufacturer",
            "category",
            "notes",
            "situation",
            "revision",
        )
    }


class SystemCreate(Input):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=20000)
    manufacturer: str = Field(default="", max_length=160)
    category: str = Field(default="", max_length=80)
    notes: str = Field(default="", max_length=20000)
    situation: Literal["ativo", "inativo"] = "ativo"


class SystemEdit(SystemCreate):
    revision: int = Field(ge=1)


class ClientLink(Input):
    revision: int | None = Field(default=None, ge=1)
    version_in_use: str = Field(default="", max_length=160)
    notes: str = Field(default="", max_length=20000)


def save(ctx, request, body, identifier=None):
    management(ctx)
    key = normalized(ctx, body.name)
    if not key:
        raise HTTPException(422, "Informe um nome de sistema")
    ctx.db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"{ctx.organization_id}:system:{key}"},
    )
    existing = ctx.db.scalar(ctx.query(SoftwareSystem).where(SoftwareSystem.name_key == key))
    if existing and existing.id != identifier:
        raise HTTPException(409, "Já existe sistema com esse nome na organização")
    if identifier:
        item = ctx.db.scalar(
            ctx.query(SoftwareSystem)
            .where(SoftwareSystem.id == identifier)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if item is None:
            raise HTTPException(404, "Sistema não encontrado")
        if item.revision != body.revision:
            raise HTTPException(409, "Sistema alterado. Recarregue antes de salvar")
        before = data(item)
        item.revision += 1
    else:
        item = SoftwareSystem(organization_id=ctx.organization_id)
        before = {}
        ctx.db.add(item)
    for field in SystemCreate.model_fields:
        setattr(item, field, getattr(body, field))
    item.name = " ".join(item.name.split())
    ctx.db.flush()
    ctx.audit(
        request,
        "sistema_editado" if identifier else "sistema_criado",
        "SoftwareSystem",
        item.id,
        before,
        data(item),
    )
    return data(item)


@router.post("/systems", status_code=201)
def create(body: SystemCreate, request: Request, ctx=Depends(context, scope="function")):
    return save(ctx, request, body)


@router.get("/systems")
def systems(
    q: str = Query(default="", max_length=200),
    include_inactive: bool = False,
    client_id: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx=Depends(context, scope="function"),
):
    query = ctx.query(SoftwareSystem)
    if not include_inactive:
        query = query.where(SoftwareSystem.situation == "ativo")
    if q:
        query = query.where(SoftwareSystem.name_key.contains(normalized(ctx, q), autoescape=True))
    if client_id:
        ctx.get(Client, client_id)
        query = query.where(
            SoftwareSystem.id.in_(
                ctx.query(ClientSystem)
                .with_only_columns(ClientSystem.system_id)
                .where(ClientSystem.client_id == client_id)
            )
        )
    total = ctx.db.scalar(select(func.count()).select_from(query.subquery()))
    rows = ctx.db.scalars(
        query.order_by(SoftwareSystem.name_key, SoftwareSystem.id).offset(offset).limit(limit)
    )
    return {"total": total, "items": [data(item) for item in rows]}


@router.put("/clients/{client_id}/systems/{system_id}")
def link(
    client_id: str,
    system_id: str,
    body: ClientLink,
    request: Request,
    ctx=Depends(context, scope="function"),
):
    management(ctx)
    ctx.get(Client, client_id)
    selected = system(ctx, system_id)
    ctx.db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"{ctx.organization_id}:{client_id}:{system_id}"},
    )
    item = ctx.db.scalar(
        ctx.query(ClientSystem)
        .where(ClientSystem.client_id == client_id, ClientSystem.system_id == system_id)
        .with_for_update()
    )
    if item:
        if item.version_in_use == body.version_in_use and item.notes == body.notes:
            return link_data(item)
        if item.revision != body.revision:
            raise HTTPException(409, "Vínculo alterado. Informe a revisão atual")
        before = link_data(item)
        item.revision += 1
    else:
        if selected.situation != "ativo":
            raise HTTPException(422, "Sistema inativo não aceita novo vínculo")
        if body.revision is not None:
            raise HTTPException(409, "Vínculo não existe; recarregue os dados")
        item = ClientSystem(
            organization_id=ctx.organization_id, client_id=client_id, system_id=system_id
        )
        ctx.db.add(item)
        before = {}
    item.version_in_use, item.notes = body.version_in_use, body.notes
    ctx.db.flush()
    ctx.audit(
        request, "cliente_sistema_vinculado", "ClientSystem", item.id, before, link_data(item)
    )
    return link_data(item)


def link_data(item):
    return {
        field: getattr(item, field)
        for field in ("id", "client_id", "system_id", "version_in_use", "notes", "revision")
    }


@router.get("/clients/{client_id}/systems")
def links(
    client_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx=Depends(context, scope="function"),
):
    ctx.get(Client, client_id)
    query = ctx.query(ClientSystem).where(ClientSystem.client_id == client_id)
    total = ctx.db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "total": total,
        "items": [
            link_data(item)
            for item in ctx.db.scalars(query.order_by(ClientSystem.id).offset(offset).limit(limit))
        ],
    }


def entity_model(kind):
    from app.work_models import KnowledgeArticle, Record, Ticket

    return {"record": Record, "ticket": Ticket, "article": KnowledgeArticle}[kind]


Kind = Literal["record", "ticket", "article"]


@router.get("/systems/reconciliation/values")
def legacy_values(
    kind: Kind = "record",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx=Depends(context, scope="function"),
):
    management(ctx)
    model = entity_model(kind)
    query = ctx.query(model).with_only_columns(model.system, func.count().label("count"))
    query = query.where(model.system_id.is_(None)).group_by(model.system)
    total = ctx.db.scalar(select(func.count()).select_from(query.subquery()))
    rows = ctx.db.execute(query.order_by(model.system).offset(offset).limit(limit))
    values = []
    for raw, count in rows:
        key = normalized(ctx, raw)
        suggestions = []
        if key:
            candidates = ctx.db.scalars(
                ctx.query(SoftwareSystem)
                .where(
                    SoftwareSystem.situation == "ativo",
                    func.similarity(SoftwareSystem.name_key, key) >= 0.3,
                )
                .order_by(func.similarity(SoftwareSystem.name_key, key).desc(), SoftwareSystem.id)
                .limit(5)
            )
            suggestions = [
                {**data(item), "exact_normalized": item.name_key == key} for item in candidates
            ]
        values.append({"legacy_text": raw, "count": count, "suggestions": suggestions})
    return {"total": total, "items": values}


@router.get("/systems/reconciliation/records")
def legacy_records(
    kind: Kind = "record",
    legacy_text: str = Query(default="", max_length=80),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx=Depends(context, scope="function"),
):
    management(ctx)
    model = entity_model(kind)
    query = ctx.query(model).where(model.system == legacy_text, model.system_id.is_(None))
    total = ctx.db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "total": total,
        "items": [
            {"id": item.id, "revision": item.revision, "legacy_text": item.system}
            for item in ctx.db.scalars(query.order_by(model.id).offset(offset).limit(limit))
        ],
    }


class Reconcile(Input):
    kind: Kind
    entity_id: str = Field(min_length=36, max_length=36)
    revision: int = Field(ge=1)
    legacy_text: Annotated[str, StringConstraints(strip_whitespace=False)] = Field(max_length=80)
    decision: Literal["aceitar", "rejeitar"]
    system_id: str | None = Field(default=None, min_length=36, max_length=36)
    reviewed: Literal[True]


@router.get("/systems/reconciliation/history")
def decisions(
    kind: Kind,
    entity_id: str,
    offset: int = Query(default=0, ge=0),
    ctx=Depends(context, scope="function"),
):
    management(ctx)
    ctx.get(entity_model(kind), entity_id)
    return [
        {
            "id": item.id,
            "actor_id": item.actor_id,
            "decision": item.decision,
            "snapshot": item.snapshot,
            "criado_em": item.criado_em,
        }
        for item in ctx.db.scalars(
            ctx.query(SystemReconciliation)
            .where(SystemReconciliation.kind == kind, SystemReconciliation.entity_id == entity_id)
            .order_by(SystemReconciliation.criado_em, SystemReconciliation.id)
            .offset(offset)
            .limit(50)
        )
    ]


@router.post("/systems/reconciliation")
def reconcile(
    body: Reconcile,
    request: Request,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ctx=Depends(context, scope="function"),
):
    management(ctx)
    fingerprint = digest(json.dumps(body.model_dump(mode="json"), sort_keys=True))
    key_hash = digest(key)
    ctx.db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"{ctx.organization_id}:{ctx.user.id}:reconcile:{key_hash}"},
    )
    prior = ctx.db.scalar(
        ctx.query(SystemReconciliation).where(
            SystemReconciliation.actor_id == ctx.user.id, SystemReconciliation.key_hash == key_hash
        )
    )
    if prior:
        if prior.fingerprint != fingerprint:
            raise HTTPException(409, "Idempotency-Key já usada com outra decisão")
        return prior.snapshot
    model = entity_model(body.kind)
    item = ctx.db.scalar(ctx.query(model).where(model.id == body.entity_id).with_for_update())
    if item is None:
        raise HTTPException(404, "Registro não encontrado")
    if item.revision != body.revision or item.system != body.legacy_text:
        raise HTTPException(409, "Registro ou texto legado alterado. Recarregue antes de decidir")
    if (body.decision == "aceitar") != (body.system_id is not None):
        raise HTTPException(422, "Escolha um sistema somente ao aceitar a reconciliação")
    if item.system_id:
        raise HTTPException(409, "Este registro já possui vínculo estruturado")
    if body.decision == "aceitar":
        select_system(ctx, item, body.system_id)
        item.revision += 1
        if body.kind == "record":
            from app.work import record_event

            record_event(ctx, request, item, "sistema_reconciliado")
        elif body.kind == "ticket":
            from app.work import ticket_event

            ticket_event(ctx, request, item, "sistema_reconciliado")
        else:
            from app.knowledge import article_event

            article_event(ctx, request, item, "sistema_reconciliado")
    snapshot = {
        "kind": body.kind,
        "entity_id": item.id,
        "revision": item.revision,
        "decision": body.decision,
        "legacy_text": item.system,
        **{field: getattr(item, field) for field in SYSTEM_FIELDS},
    }
    ctx.db.add(
        SystemReconciliation(
            organization_id=ctx.organization_id,
            actor_id=ctx.user.id,
            kind=body.kind,
            entity_id=item.id,
            decision=body.decision,
            legacy_text=body.legacy_text,
            system_id=body.system_id,
            key_hash=key_hash,
            fingerprint=fingerprint,
            snapshot=snapshot,
        )
    )
    ctx.audit(
        request, "sistema_reconciliacao_decidida", "SystemReconciliation", item.id, {}, snapshot
    )
    ctx.db.flush()
    return snapshot


@router.get("/systems/{identifier}")
def detail(identifier: str, ctx=Depends(context, scope="function")):
    return data(system(ctx, identifier))


@router.patch("/systems/{identifier}")
def edit(
    identifier: str, body: SystemEdit, request: Request, ctx=Depends(context, scope="function")
):
    return save(ctx, request, body, identifier)
