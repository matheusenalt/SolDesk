from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field, field_validator
from sqlalchemy import func, select

from app.access import context
from app.insight_models import ArticleVersion
from app.knowledge import (
    CONTENT,
    act_article,
    article_data,
    consultation,
    edit_article,
    find_article,
    new_article,
    policy,
    reviewer,
    search_articles,
)
from app.models import Organization, User
from app.schemas import Input
from app.security import check_csrf
from app.work import find_record, find_ticket
from app.work_models import KnowledgeArticle, Record

router = APIRouter(prefix="/api/v1", tags=["Conhecimento"], dependencies=[Depends(check_csrf)])


class KnowledgePolicy(Input):
    publisher_roles: list[Literal["administrador", "gestor", "tecnico"]] = Field(
        min_length=1, max_length=3
    )
    allow_self_publish: bool = False


class ArticleSearch(Input):
    q: str = Field(default="", max_length=200)
    category: str = Field(default="", max_length=80)
    system: str = Field(default="", max_length=80)
    client_id: str | None = Field(default=None, min_length=36, max_length=36)
    status: Literal["publicado", "arquivado"] = "publicado"
    start_date: date | None = None
    end_date: date | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class ArticleCreate(Input):
    record_id: str = Field(min_length=36, max_length=36)


class ArticleEdit(Input):
    revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    problem: str = Field(default="", max_length=10000)
    context: str = Field(default="", max_length=10000)
    confirmed_cause: str = Field(default="", max_length=5000)
    procedure: str = Field(default="", max_length=15000)
    result: str = Field(default="", max_length=10000)
    text: str = Field(default="", max_length=20000)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    category: str = Field(default="", max_length=80)
    system: str = Field(default="", max_length=80)
    client_id: str | None = Field(default=None, min_length=36, max_length=36)

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, values):
        if any(not value.strip() or len(value) > 80 for value in values):
            raise ValueError("Palavra-chave deve ter entre 1 e 80 caracteres")
        return values


class ArticleAction(Input):
    revision: int = Field(ge=1)
    action: Literal["enviar", "publicar", "devolver", "arquivar", "reabrir"]
    comment: str = Field(default="", max_length=3000)
    human_reviewed: bool = False
    warnings_reviewed: bool = False


@router.get("/knowledge/policy")
def get_policy(ctx=Depends(context, scope="function")):
    return {**policy(ctx), "can_review": reviewer(ctx)}


@router.patch("/knowledge/policy")
def update_policy(body: KnowledgePolicy, request: Request, ctx=Depends(context, scope="function")):
    ctx.require_admin()
    org = ctx.db.scalar(
        select(Organization).where(Organization.id == ctx.organization_id).with_for_update()
    )
    before = policy(ctx)
    saved = {**body.model_dump(), "publisher_roles": sorted(set(body.publisher_roles))}
    org.settings = {**org.settings, "knowledge": saved}
    ctx.audit(request, "politica_conhecimento_alterada", "Organization", org.id, before, saved)
    return {**saved, "can_review": ctx.membership.role in saved["publisher_roles"]}


@router.get("/knowledge/search")
def search(filters: Annotated[ArticleSearch, Query()], ctx=Depends(context, scope="function")):
    return search_articles(ctx, filters)


@router.get("/knowledge/drafts")
def drafts(
    queue: bool = False,
    offset: int = Query(default=0, ge=0),
    ctx=Depends(context, scope="function"),
):
    query = ctx.query(KnowledgeArticle)
    if queue:
        if not reviewer(ctx):
            raise HTTPException(403, "A fila editorial exige papel de revisor autorizado")
        query = query.where(KnowledgeArticle.status == "aguardando_revisao")
    else:
        query = query.where(KnowledgeArticle.author_id == ctx.user.id)
    total = ctx.db.scalar(select(func.count()).select_from(query.subquery()))
    rows = ctx.db.scalars(
        query.order_by(KnowledgeArticle.atualizado_em.desc(), KnowledgeArticle.id)
        .offset(offset)
        .limit(20)
    )
    return {"total": total, "items": [article_data(ctx, item) for item in rows]}


@router.post("/knowledge/articles", status_code=201)
def create(body: ArticleCreate, request: Request, ctx=Depends(context, scope="function")):
    source = find_record(ctx, body.record_id)
    ctx.db.scalar(ctx.query(Record).where(Record.id == source.id).with_for_update())
    existing = ctx.db.scalar(
        ctx.query(KnowledgeArticle).where(KnowledgeArticle.record_id == source.id)
    )
    if existing:
        return article_data(ctx, find_article(ctx, existing.id), True)
    if source.status == "cancelado":
        raise HTTPException(409, "A origem está cancelada")
    item = new_article(ctx, request, source)
    source.article_id = item.id
    source.revision += 1
    from app.work import record_event

    record_event(ctx, request, source, "registro_artigo_criado")
    return article_data(ctx, item, True)


@router.get("/knowledge/articles/{identifier}")
def detail(identifier: str, ctx=Depends(context, scope="function")):
    item = find_article(ctx, identifier)
    consultation(ctx, item)
    return article_data(ctx, item, True)


@router.patch("/knowledge/articles/{identifier}")
def edit(
    identifier: str, body: ArticleEdit, request: Request, ctx=Depends(context, scope="function")
):
    item = find_article(ctx, identifier, body.revision)
    edit_article(ctx, request, item, body)
    return article_data(ctx, item, True)


@router.post("/knowledge/articles/{identifier}/actions")
def action(
    identifier: str, body: ArticleAction, request: Request, ctx=Depends(context, scope="function")
):
    item = find_article(ctx, identifier, body.revision)
    act_article(ctx, request, item, body)
    return article_data(ctx, item, True)


@router.get("/knowledge/articles/{identifier}/versions")
def versions(identifier: str, ctx=Depends(context, scope="function")):
    find_article(ctx, identifier)
    rows = ctx.db.scalars(
        ctx.query(ArticleVersion)
        .where(ArticleVersion.article_id == identifier)
        .order_by(ArticleVersion.revision)
    )
    result, before = [], {}
    for row in rows:
        changes = [
            {"field": field, "before": before.get(field), "after": row.snapshot.get(field)}
            for field in (*CONTENT, "status", "review_comment")
            if before.get(field) != row.snapshot.get(field)
        ]
        result.append(
            {
                "revision": row.revision,
                "actor_name": ctx.db.get(User, row.actor_id).name if row.actor_id else None,
                "change": row.change,
                "criado_em": row.criado_em,
                "snapshot": row.snapshot,
                "diff": changes,
            }
        )
        before = row.snapshot
    return result


@router.get("/tickets/{identifier}/suggestions")
def suggestions(identifier: str, ctx=Depends(context, scope="function")):
    ticket = find_ticket(ctx, identifier)
    # Sempre o cliente real do ticket, não um ID de cliente fornecido pelo chamador.
    tokens = re_terms(ticket.description)
    filters = ArticleSearch(q=" ".join(tokens[:8]), client_id=ticket.client_id, limit=5)
    if not tokens:
        return {"label": "Sugestão, não diagnóstico", "items": []}
    result = search_articles(ctx, filters)
    if not result["items"] and ticket.category:
        result = search_articles(
            ctx, ArticleSearch(category=ticket.category, client_id=ticket.client_id, limit=5)
        )
    return {"label": "Sugestão, não diagnóstico", "items": result["items"]}


def re_terms(value):
    import re

    return [word for word in re.findall(r"[\w]+", value) if len(word) >= 4]
