"""Autorização de arquivos e criação durável dos trabalhos de áudio."""

import hashlib
import hmac
import time
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select

from app.access import Context
from app.media_models import Attachment, AudioJob, GlossaryTerm, TemplateVersion
from app.models import Client, Organization, OrganizationMembership, User
from app.transcription import DEFAULT_GLOSSARY, default_fields
from app.work import author_only, find_record, find_ticket, record_event

ERRORS = {
    "formato_invalido": "Áudio inválido. Confira o formato e tente outro arquivo.",
    "duracao_excessiva": "O áudio ultrapassa o limite de duração da instalação.",
    "timeout": "O processamento excedeu o tempo permitido. Você pode tentar novamente ou digitar.",
    "provedor_indisponivel": "Não foi possível transcrever. Tente novamente ou digite o relato.",
}


def media_preferences(ctx):
    organization = ctx.db.get(Organization, ctx.organization_id)
    saved = organization.settings.get("media", {})
    return {
        "retention": saved.get("retention", "manter"),
        "retention_days": saved.get("retention_days", 30),
        "live_dictation_enabled": bool(saved.get("live_dictation_enabled", False)),
    }


def ensure_defaults(ctx):
    # O bloqueio da organização serializa a primeira semente e novas versões.
    ctx.db.scalar(
        select(Organization).where(Organization.id == ctx.organization_id).with_for_update()
    )
    for kind in ("finalizacao", "chamado", "conhecimento"):
        if (
            ctx.db.scalar(ctx.query(TemplateVersion).where(TemplateVersion.type == kind).limit(1))
            is None
        ):
            ctx.db.add(
                TemplateVersion(
                    organization_id=ctx.organization_id,
                    type=kind,
                    version=1,
                    fields=default_fields(kind),
                )
            )
    if ctx.db.scalar(ctx.query(GlossaryTerm).limit(1)) is None:
        for value in DEFAULT_GLOSSARY:
            ctx.db.add(GlossaryTerm(organization_id=ctx.organization_id, **value))
    ctx.db.flush()


def authorize_owner(ctx, owner_type, identifier, write=False):
    if owner_type == "record":
        item = find_record(ctx, identifier)
        if write:
            author_only(ctx, item)
        return item
    if owner_type == "ticket":
        return find_ticket(ctx, identifier)
    if owner_type == "client":
        return ctx.get(Client, identifier)
    raise HTTPException(404, "Destino não encontrado")


def owner_filter(owner_type, identifier):
    field = {
        "record": Attachment.record_id,
        "ticket": Attachment.ticket_id,
        "client": Attachment.client_id,
    }.get(owner_type)
    if field is None:
        raise HTTPException(404, "Destino não encontrado")
    return field == identifier


def attachment_data(item):
    return {
        field: getattr(item, field)
        for field in (
            "id",
            "owner_type",
            "kind",
            "filename",
            "content_type",
            "size",
            "sha256",
            "uploaded_by",
            "enviado_em",
            "validated",
            "duration_seconds",
            "purgado_em",
        )
    }


def latest_job(ctx, record_id):
    return ctx.db.scalar(
        ctx.query(AudioJob)
        .where(AudioJob.record_id == record_id)
        .order_by(AudioJob.criado_em.desc(), AudioJob.id.desc())
        .limit(1)
    )


def job_data(item):
    result = {
        field: getattr(item, field)
        for field in (
            "id",
            "attachment_id",
            "record_id",
            "status",
            "priority",
            "attempts",
            "raw_text",
            "normalized_text",
            "organized_text",
            "segments",
            "sections",
            "warnings",
            "provider_metadata",
            "template_snapshot",
            "criado_em",
            "iniciado_em",
            "finalizado_em",
            "proxima_tentativa_em",
        )
    }
    result["error"] = ERRORS.get(item.error_code) if item.error_code else None
    return result


def require_processable(ctx, item):
    author_only(ctx, item)
    if item.status in {"confirmado", "publicado", "cancelado"}:
        raise HTTPException(409, "Registro já revisado; use Derivar para outro relato")
    previous = latest_job(ctx, item.id)
    if previous and previous.status in {"aguardando", "processando"}:
        raise HTTPException(409, "Já existe um áudio aguardando ou em processamento")


def create_job(ctx, request, item, attachment, parent=None):
    require_processable(ctx, item)
    ensure_defaults(ctx)
    template = ctx.db.scalar(
        ctx.query(TemplateVersion)
        .where(TemplateVersion.type == item.type)
        .order_by(TemplateVersion.version.desc())
        .limit(1)
    )
    if item.template_version_id and parent is None:
        template = ctx.get(TemplateVersion, item.template_version_id)
    glossary = [
        {"term": term.term, "aliases": term.aliases}
        for term in ctx.db.scalars(ctx.query(GlossaryTerm).order_by(GlossaryTerm.term))
    ]
    priority = "normal"
    if item.ticket_id:
        priority = find_ticket(ctx, item.ticket_id).priority
    job = AudioJob(
        organization_id=ctx.organization_id,
        record_id=item.id,
        attachment_id=attachment.id,
        template_id=template.id,
        template_snapshot={
            "id": template.id,
            "version": template.version,
            "type": item.type,
            "fields": template.fields,
        },
        glossary_snapshot=glossary,
        priority=priority,
        parent_id=parent.id if parent else None,
    )
    ctx.db.add(job)
    item.template_version_id = template.id
    if item.type != "chamado":
        item.status = "enviado"
    item.revision += 1
    record_event(ctx, request, item, "audio_aguardando")
    ctx.db.flush()
    return job


def check_audio_review(ctx, item, acknowledged):
    latest = latest_job(ctx, item.id)
    if not latest or latest.status == "descartado":
        return
    if latest.status != "concluido":
        raise HTTPException(
            409, "Conclua ou descarte o processamento e confira o texto antes de confirmar"
        )
    if not acknowledged:
        raise HTTPException(
            409, "Confira a transcrição, os trechos incertos e os avisos antes de confirmar"
        )
    if (
        latest.provider_metadata.get("simulado")
        and item.texto_original == "Relato enviado por áudio."
        and (not item.texto_organizado or item.texto_organizado == item.texto_original)
    ):
        raise HTTPException(
            409, "O mock não reconhece fala. Digite o relato real antes de confirmar"
        )


def worker_context(db, organization_id, author_id):
    user = db.get(User, author_id)
    member = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == author_id,
        )
    )
    return Context(db, user, SimpleNamespace(organization_id=organization_id), member)


def signature(key, ctx, attachment, expires):
    message = (
        f"{ctx.organization_id}:{ctx.user.id}:{ctx.session.token_hash}:{attachment.id}:{expires}"
    )
    return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()


def signed_path(key, seconds, ctx, attachment):
    expires = int(time.time()) + seconds
    signed = signature(key, ctx, attachment, expires)
    return f"/api/v1/attachments/{attachment.id}/content?expires={expires}&signature={signed}"


def check_signature(key, ctx, attachment, expires, supplied):
    if (
        expires < int(time.time())
        or expires > int(time.time()) + 300
        or not hmac.compare_digest(signature(key, ctx, attachment, expires), supplied)
    ):
        raise HTTPException(403, "Link expirado ou inválido. Solicite outro acesso ao arquivo")
