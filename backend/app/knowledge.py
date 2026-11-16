"""Fluxo editorial humano e pesquisa tenant-aware, sem inferência de conteúdo."""

import json
import re
import unicodedata

from fastapi import HTTPException
from sqlalchemy import func, or_, select, text

from app.insight_models import ArticleConsultation, ArticleVersion
from app.media_models import AudioJob, TemplateVersion
from app.models import Client, Organization, User, now
from app.transcription import sensitive_warnings
from app.work import check_revision, record_event, record_query
from app.work_models import KnowledgeArticle, Record

CONTENT = (
    "title",
    "problem",
    "context",
    "confirmed_cause",
    "procedure",
    "result",
    "keywords",
    "category",
    "system",
    "client_id",
    "text",
)
SNAPSHOT = (
    *CONTENT,
    "status",
    "template_version_id",
    "review_comment",
    "reviewer_id",
    "enviado_revisao_em",
    "publicado_em",
    "arquivado_em",
)


def policy(ctx):
    saved = ctx.db.get(Organization, ctx.organization_id).settings.get("knowledge", {})
    return {
        "publisher_roles": saved.get("publisher_roles", ["administrador", "gestor"]),
        "allow_self_publish": saved.get("allow_self_publish", False),
    }


def reviewer(ctx):
    return ctx.membership.role in policy(ctx)["publisher_roles"]


def can_publish(ctx, article):
    return reviewer(ctx) and (article.author_id != ctx.user.id or policy(ctx)["allow_self_publish"])


def visible(ctx, article):
    if article.status not in {"publicado", "arquivado"} and (
        article.author_id != ctx.user.id and not reviewer(ctx)
    ):
        raise HTTPException(404, "Artigo não encontrado")
    return article


def find_article(ctx, identifier, revision=None):
    item = ctx.get(KnowledgeArticle, identifier)
    visible(ctx, item)
    if revision is not None:
        # Mesma ordem de locks do worker/edição do relato: Record antes de artigo.
        ctx.db.scalar(ctx.query(Record).where(Record.id == item.record_id).with_for_update())
        item = ctx.db.scalar(
            ctx.query(KnowledgeArticle)
            .where(KnowledgeArticle.id == identifier)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        check_revision(item, revision)
        visible(ctx, item)
    return item


def snapshot(item):
    return json.loads(
        json.dumps(
            {key: getattr(item, key) for key in SNAPSHOT}, default=lambda value: value.isoformat()
        )
    )


def article_event(ctx, request, item, change):
    ctx.db.add(
        ArticleVersion(
            organization_id=ctx.organization_id,
            article_id=item.id,
            revision=item.revision,
            actor_id=ctx.user.id,
            change=change,
            snapshot=snapshot(item),
        )
    )
    ctx.audit(
        request,
        change,
        "KnowledgeArticle",
        item.id,
        {},
        {"status": item.status, "revision": item.revision},
    )


def new_article(ctx, request, record):
    item = KnowledgeArticle(
        organization_id=ctx.organization_id,
        record_id=record.id,
        author_id=ctx.user.id,
        text=record.texto_organizado or record.texto_original,
        template_version_id=record.template_version_id,
        category=record.category,
        system=record.system,
    )
    ctx.db.add(item)
    ctx.db.flush()
    article_event(ctx, request, item, "artigo_criado")
    return item


def sync_source(ctx, request, article, value):
    """Só o rascunho intocado acompanha o relato; edição editorial é independente."""
    if article.status == "rascunho" and not article.title and article.text != value:
        article.text = value
        article.revision += 1
        article.atualizado_em = now()
        article_event(ctx, request, article, "origem_atualizada")


def warnings(ctx, item):
    combined = "\n".join(str(getattr(item, key) or "") for key in CONTENT if key != "client_id")
    result = [{"kind": row["kind"]} for row in sensitive_warnings(combined)]
    if re.search(r"\b(?:CFOP\s*[:\-]?\s*\d+|\d{4})\b", combined, re.IGNORECASE):
        result.append({"kind": "codigo_fiscal_nao_verificado"})
    job = ctx.db.scalar(
        ctx.query(AudioJob)
        .where(AudioJob.record_id == item.record_id)
        .order_by(AudioJob.criado_em.desc())
        .limit(1)
    )
    if job and any(s.get("uncertain") for s in job.segments):
        result.append({"kind": "trecho_incerto_na_origem"})
    if not item.confirmed_cause.strip():
        result.append({"kind": "causa_nao_informada"})
    return result


def article_data(ctx, item, detail=False):
    result = {
        key: getattr(item, key)
        for key in (
            "id",
            "record_id",
            "author_id",
            "revision",
            *SNAPSHOT,
            "criado_em",
            "atualizado_em",
        )
    }
    result["author_name"] = ctx.db.get(User, item.author_id).name
    result["reviewer_name"] = ctx.db.get(User, item.reviewer_id).name if item.reviewer_id else None
    result["client_name"] = ctx.get(Client, item.client_id).name if item.client_id else None
    result["template_version"] = (
        ctx.get(TemplateVersion, item.template_version_id).version
        if item.template_version_id
        else None
    )
    source = ctx.db.scalar(record_query(ctx).where(Record.id == item.record_id))
    result["source_accessible"] = bool(source)
    result["source_ticket_id"] = source.ticket_id if source else None
    result["can_publish"] = can_publish(ctx, item)
    result["can_review"] = reviewer(ctx) and (
        item.author_id != ctx.user.id or policy(ctx)["allow_self_publish"]
    )
    if detail:
        result["warnings"] = warnings(ctx, item)
        result["source_text"] = (
            (source.texto_organizado or source.texto_original) if source else None
        )
    return result


def edit_article(ctx, request, item, body):
    if item.author_id != ctx.user.id:
        raise HTTPException(403, "Somente o autor edita o rascunho; devolva com um comentário")
    if item.status not in {"rascunho", "devolvido"}:
        raise HTTPException(409, "Devolva ou reabra o artigo antes de editar")
    if body.client_id:
        ctx.get(Client, body.client_id)
    for key in CONTENT:
        setattr(item, key, getattr(body, key))
    item.revision += 1
    item.atualizado_em = now()
    article_event(ctx, request, item, "artigo_editado")
    ctx.db.flush()


def act_article(ctx, request, item, body):
    source = ctx.get(Record, item.record_id)
    if body.action == "enviar":
        if item.author_id != ctx.user.id:
            raise HTTPException(403, "Somente o autor envia o artigo para revisão")
        if item.status not in {"rascunho", "devolvido"}:
            raise HTTPException(409, "Este artigo não está em edição")
        if not item.title.strip() or not item.problem.strip() or not item.procedure.strip():
            raise HTTPException(422, "Informe título, problema e procedimento para revisar")
        if source.status == "cancelado":
            raise HTTPException(409, "A origem está cancelada; use outro registro válido")
        from app.media import latest_job

        job = latest_job(ctx, source.id)
        if job and job.status in {"aguardando", "processando"}:
            raise HTTPException(
                409, "Conclua ou descarte o processamento antes da revisão editorial"
            )
        item.status, item.enviado_revisao_em = "aguardando_revisao", now()
    elif body.action in {"publicar", "devolver"}:
        if not can_publish(ctx, item):
            raise HTTPException(403, "A política da organização exige outro revisor autorizado")
        if item.status != "aguardando_revisao":
            raise HTTPException(409, "Este artigo não aguarda revisão")
        if body.action == "devolver":
            if not body.comment.strip():
                raise HTTPException(422, "Informe o comentário de devolução")
            item.status, item.review_comment = "devolvido", body.comment
        else:
            if not body.human_reviewed or not body.warnings_reviewed:
                raise HTTPException(
                    409, "Confira o conteúdo, as incertezas, códigos e possíveis credenciais"
                )
            if source.status == "cancelado":
                raise HTTPException(409, "A origem está cancelada")
            item.status, item.publicado_em, item.reviewer_id = "publicado", now(), ctx.user.id
            if source.type == "conhecimento":
                source.status, source.publicado_em = "publicado", item.publicado_em
                source.revision += 1
                record_event(ctx, request, source, "conhecimento_publicado")
    elif body.action == "arquivar":
        if not reviewer(ctx) or item.status != "publicado":
            raise HTTPException(403, "Somente revisor autorizado arquiva artigo publicado")
        if not body.comment.strip():
            raise HTTPException(422, "Informe o motivo do arquivamento")
        item.status, item.arquivado_em, item.review_comment = "arquivado", now(), body.comment
    else:  # Nova rodada editorial; a versão publicada continua no histórico.
        if item.author_id != ctx.user.id or item.status != "arquivado":
            raise HTTPException(403, "Somente o autor reabre artigo arquivado para edição")
        item.status, item.reviewer_id = "rascunho", None
    item.revision += 1
    item.atualizado_em = now()
    article_event(ctx, request, item, "artigo_" + body.action)
    ctx.db.flush()


def fold(value):
    return "".join(
        c for c in unicodedata.normalize("NFD", value.lower()) if not unicodedata.combining(c)
    )


def snippet(item, query):
    source = " · ".join(
        value for value in (item.title, item.problem, item.procedure, item.text) if value
    )
    # Os offsets são calculados em caracteres originais; nunca retornar HTML do banco.
    normalized, offsets = [], []
    for index, character in enumerate(source):
        for normalized_char in fold(character):
            normalized.append(normalized_char)
            offsets.append(index)
    normalized = "".join(normalized)
    needle = fold(query.strip())
    at = normalized.find(needle) if needle else -1
    if at < 0 and needle:
        for token in needle.split():
            at = normalized.find(token)
            if at >= 0:
                needle = token
                break
    start = max(0, offsets[at] - 60) if at >= 0 else 0
    end = min(len(source), start + 300)
    highlights = []
    if at >= 0 and at + len(needle) <= len(offsets):
        left, right = offsets[at] - start, offsets[at + len(needle) - 1] + 1 - start
        if right <= end - start:
            highlights = [{"start": left, "end": right}]
    return {"snippet": source[start:end], "highlights": highlights}


def search_articles(ctx, filters):
    query = ctx.query(KnowledgeArticle).where(KnowledgeArticle.status == filters.status)
    if filters.client_id:
        ctx.get(Client, filters.client_id)
        query = query.where(
            or_(
                KnowledgeArticle.client_id.is_(None),
                KnowledgeArticle.client_id == filters.client_id,
            )
        )
    else:
        query = query.where(KnowledgeArticle.client_id.is_(None))
    for field in ("category", "system"):
        if getattr(filters, field):
            query = query.where(getattr(KnowledgeArticle, field) == getattr(filters, field))
    from app.reports import date_bounds

    org = ctx.db.get(Organization, ctx.organization_id)
    if filters.start_date:
        lower, _ = date_bounds(filters.start_date, filters.start_date, org.timezone)
        query = query.where(KnowledgeArticle.publicado_em >= lower)
    if filters.end_date:
        _, upper = date_bounds(filters.end_date, filters.end_date, org.timezone)
        query = query.where(KnowledgeArticle.publicado_em < upper)
    if filters.start_date and filters.end_date and filters.start_date > filters.end_date:
        raise HTTPException(422, "O período da busca está invertido")
    q = filters.q.strip()
    if q:
        escaped = fold(q).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            text("""(search_vector @@ websearch_to_tsquery('portuguese',public.unaccent(:q))
            OR search_text ILIKE :pattern ESCAPE '\\' OR search_text % :folded)""")
        )
        query = query.params(q=q, pattern="%" + escaped + "%", folded=fold(q))
    total = ctx.db.scalar(select(func.count()).select_from(query.subquery()))
    if q:
        query = query.order_by(
            text("(strpos(search_text,:folded)>0) DESC"),
            text(
                "ts_rank(search_vector,websearch_to_tsquery('portuguese',public.unaccent(:q))) DESC"
            ),
        )
        query = query.params(q=q, pattern="%" + escaped + "%", folded=fold(q))
    rows = ctx.db.scalars(
        query.order_by(KnowledgeArticle.publicado_em.desc(), KnowledgeArticle.id)
        .offset(filters.offset)
        .limit(filters.limit)
    )
    return {
        "total": total,
        "items": [{**article_data(ctx, item), **snippet(item, q)} for item in rows],
    }


def consultation(ctx, item):
    if item.status in {"publicado", "arquivado"}:
        ctx.db.add(ArticleConsultation(organization_id=ctx.organization_id, article_id=item.id))
