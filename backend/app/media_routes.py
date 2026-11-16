import hashlib
import secrets
from urllib.parse import quote, unquote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import Field
from sqlalchemy import select, text

from app.access import context
from app.media import (
    attachment_data,
    authorize_owner,
    check_signature,
    create_job,
    ensure_defaults,
    job_data,
    latest_job,
    media_preferences,
    owner_filter,
    require_processable,
    signed_path,
)
from app.media_models import Attachment, AudioJob, GlossaryTerm, TemplateVersion
from app.models import Organization, new_id, now
from app.schemas import Input
from app.security import check_csrf
from app.storage import identify, scan_antivirus, storage
from app.transcription import DEFAULT_GLOSSARY, GlossaryInput, TemplateField, default_fields
from app.work import author_only, find_record, record_data, record_event
from app.work_schemas import RecordType

router = APIRouter(prefix="/api/v1", tags=["Áudio e arquivos"], dependencies=[Depends(check_csrf)])


@router.get("/media/settings")
def settings(request: Request, ctx=Depends(context, scope="function")):
    config = request.app.state.settings
    return {
        **media_preferences(ctx),
        "provider": config.transcription_provider,
        "max_bytes": config.upload_max_bytes,
        "max_seconds": config.audio_max_seconds,
        "attachment_types": config.attachment_types.split(","),
    }


class Preferences(Input):
    retention: str = Field(pattern="^(manter|apos_confirmacao|apos_dias)$")
    retention_days: int = Field(default=30, ge=1, le=3650)
    live_dictation_enabled: bool = False


@router.patch("/media/settings")
def preferences(body: Preferences, request: Request, ctx=Depends(context, scope="function")):
    ctx.require_admin()
    org = ctx.db.scalar(
        select(Organization).where(Organization.id == ctx.organization_id).with_for_update()
    )
    before = media_preferences(ctx)
    org.settings = {**org.settings, "media": body.model_dump()}
    ctx.audit(
        request, "configuracao_audio_alterada", "Organization", org.id, before, body.model_dump()
    )
    return body.model_dump()


@router.get("/media/templates")
def templates(ctx=Depends(context, scope="function")):
    result = []
    for kind in ("finalizacao", "chamado", "conhecimento"):
        item = ctx.db.scalar(
            ctx.query(TemplateVersion)
            .where(TemplateVersion.type == kind)
            .order_by(TemplateVersion.version.desc())
            .limit(1)
        )
        result.append(
            {
                "id": item.id if item else None,
                "type": kind,
                "version": item.version if item else 0,
                "fields": item.fields if item else default_fields(kind),
            }
        )
    return result


class TemplateInput(Input):
    type: RecordType
    expected_version: int = Field(ge=0)
    fields: list[TemplateField] = Field(min_length=1, max_length=10)


@router.post("/media/templates", status_code=201)
def new_template(body: TemplateInput, request: Request, ctx=Depends(context, scope="function")):
    ctx.require_admin()
    ctx.db.scalar(
        select(Organization).where(Organization.id == ctx.organization_id).with_for_update()
    )
    latest = ctx.db.scalar(
        ctx.query(TemplateVersion)
        .where(TemplateVersion.type == body.type)
        .order_by(TemplateVersion.version.desc())
        .limit(1)
    )
    if body.expected_version != (latest.version if latest else 0):
        raise HTTPException(409, "O template foi alterado; recarregue antes de salvar")
    fields = [field.model_dump() for field in body.fields]
    keys = [f["key"] for f in fields]
    markers = [marker.casefold() for f in fields for marker in f["markers"]]
    if len(set(keys)) != len(keys) or len(set(markers)) != len(markers):
        raise HTTPException(422, "Não repita campos ou marcadores")
    item = TemplateVersion(
        organization_id=ctx.organization_id,
        type=body.type,
        version=body.expected_version + 1,
        fields=fields,
        created_by=ctx.user.id,
    )
    ctx.db.add(item)
    ctx.db.flush()
    ctx.audit(
        request,
        "template_versionado",
        "TemplateVersion",
        item.id,
        {},
        {"type": item.type, "version": item.version},
    )
    return {"id": item.id, "type": item.type, "version": item.version, "fields": fields}


@router.get("/media/glossary")
def glossary(ctx=Depends(context, scope="function")):
    rows = list(ctx.db.scalars(ctx.query(GlossaryTerm).order_by(GlossaryTerm.term)))
    return (
        [{"term": term.term, "aliases": term.aliases} for term in rows]
        if rows
        else DEFAULT_GLOSSARY
    )


@router.post("/media/glossary")
def glossary_term(body: GlossaryInput, request: Request, ctx=Depends(context, scope="function")):
    ctx.require_admin()
    ensure_defaults(ctx)
    item = ctx.db.scalar(ctx.query(GlossaryTerm).where(GlossaryTerm.term == body.term))
    before = {"term": item.term, "aliases": item.aliases} if item else {}
    if item:
        item.aliases = body.aliases
    else:
        item = GlossaryTerm(organization_id=ctx.organization_id, **body.model_dump())
        ctx.db.add(item)
    ctx.db.flush()
    ctx.audit(request, "glossario_atualizado", "GlossaryTerm", item.id, before, body.model_dump())
    return body.model_dump()


async def receive_file(request, ctx, owner_type, identifier, audio, revision=None):
    config = request.app.state.settings
    owner = (
        find_record(ctx, identifier, revision)
        if audio
        else authorize_owner(ctx, owner_type, identifier, write=True)
    )
    if audio:
        author_only(ctx, owner)
        if config.transcription_provider == "disabled":
            raise HTTPException(503, "Transcrição desabilitada. Continue digitando o relato")
    filename = unquote(request.headers.get("X-Filename", ""))
    if (
        not filename
        or len(filename) > 255
        or any(c in filename for c in "/\\\r\n\0")
        or any(ord(c) < 32 for c in filename)
    ):
        raise HTTPException(422, "Informe um nome de arquivo válido")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > config.upload_max_bytes:
            raise HTTPException(413, "Arquivo maior que o limite permitido")
        data.extend(chunk)
    if not data:
        raise HTTPException(422, "O arquivo está vazio")
    raw = bytes(data)
    try:
        mime = identify(
            raw, filename, request.headers.get("Content-Type", ""), audio, config.attachment_types
        )
        scan_antivirus(config, raw)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except OSError:
        raise HTTPException(503, "Verificação de arquivo temporariamente indisponível") from None
    sha = hashlib.sha256(raw).hexdigest()
    lock = f"upload:{ctx.organization_id}:{owner_type}:{identifier}:{sha}"
    ctx.db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key": lock})
    existing = ctx.db.scalar(
        ctx.query(Attachment).where(
            owner_filter(owner_type, identifier),
            Attachment.sha256 == sha,
            Attachment.purgado_em.is_(None),
        )
    )
    if existing:
        job = latest_job(ctx, identifier) if audio else None
        return existing, job, owner
    if audio:
        require_processable(ctx, owner)
    key = f"{ctx.organization_id}/{new_id()}"
    backend = storage(config)
    item = Attachment(
        organization_id=ctx.organization_id,
        owner_type=owner_type,
        **{owner_type + "_id": identifier},
        kind="audio" if audio else "arquivo",
        filename=filename,
        content_type=mime,
        size=len(raw),
        sha256=sha,
        object_key=key,
        storage_backend=config.storage_backend,
        uploaded_by=ctx.user.id,
        validated=not audio,
    )
    try:
        backend.put(key, raw, mime)
    except Exception:
        raise HTTPException(503, "Armazenamento temporariamente indisponível") from None
    try:
        ctx.db.add(item)
        ctx.db.flush()
        job = create_job(ctx, request, owner, item) if audio else None
        ctx.audit(
            request,
            "arquivo_enviado",
            "Attachment",
            item.id,
            {},
            {"owner_type": owner_type, "owner_id": identifier, "size": len(raw), "sha256": sha},
        )
        ctx.db.flush()
    except Exception:
        backend.delete(key)
        raise
    return item, job, owner


@router.post("/records/{identifier}/audio", status_code=202)
async def audio_upload(
    identifier: str,
    request: Request,
    revision: int = Query(ge=1),
    ctx=Depends(context, scope="function"),
):
    attachment, job, record = await receive_file(request, ctx, "record", identifier, True, revision)
    return {
        "attachment": attachment_data(attachment),
        "job": job_data(job),
        "record": record_data(ctx, record),
    }


@router.post("/files/{owner_type}/{identifier}", status_code=201)
async def upload(
    owner_type: str, identifier: str, request: Request, ctx=Depends(context, scope="function")
):
    if owner_type not in {"client", "ticket"}:
        raise HTTPException(404, "Destino não encontrado")
    attachment, _, _ = await receive_file(request, ctx, owner_type, identifier, False)
    return attachment_data(attachment)


@router.get("/files/{owner_type}/{identifier}")
def attachments(owner_type: str, identifier: str, ctx=Depends(context, scope="function")):
    authorize_owner(ctx, owner_type, identifier)
    return [
        attachment_data(item)
        for item in ctx.db.scalars(
            ctx.query(Attachment)
            .where(owner_filter(owner_type, identifier))
            .order_by(Attachment.enviado_em.desc())
            .limit(100)
        )
    ]


def accessible_attachment(ctx, identifier):
    item = ctx.get(Attachment, identifier)
    authorize_owner(ctx, item.owner_type, getattr(item, item.owner_type + "_id"))
    if item.purgado_em or not item.validated:
        raise HTTPException(404, "Arquivo removido ou ainda não validado")
    return item


@router.post("/attachments/{identifier}/link")
def download_link(identifier: str, request: Request, ctx=Depends(context, scope="function")):
    item = accessible_attachment(ctx, identifier)
    return {
        "url": signed_path(
            request.app.state.download_signing_key,
            request.app.state.settings.download_seconds,
            ctx,
            item,
        ),
        "expires_in": request.app.state.settings.download_seconds,
    }


@router.get("/attachments/{identifier}/content")
def download(
    identifier: str,
    request: Request,
    expires: int,
    signature: str = Query(max_length=64),
    ctx=Depends(context, scope="function"),
):
    item = accessible_attachment(ctx, identifier)
    check_signature(request.app.state.download_signing_key, ctx, item, expires, signature)
    try:
        data = storage(request.app.state.settings, item.storage_backend).get(item.object_key)
    except Exception:
        raise HTTPException(503, "Arquivo temporariamente indisponível") from None
    ctx.audit(
        request, "arquivo_acessado", "Attachment", item.id, {}, {"owner_type": item.owner_type}
    )
    mode = "inline" if item.kind == "audio" else "attachment"
    return Response(
        data,
        media_type=item.content_type,
        headers={
            "Content-Disposition": f"{mode}; filename*=UTF-8''{quote(item.filename, safe='')}",
            "Content-Security-Policy": "sandbox",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/records/{identifier}/processing")
def processing(identifier: str, ctx=Depends(context, scope="function")):
    item = find_record(ctx, identifier)
    jobs = list(
        ctx.db.scalars(
            ctx.query(AudioJob)
            .where(AudioJob.record_id == identifier)
            .order_by(AudioJob.criado_em.desc(), AudioJob.id.desc())
            .limit(20)
        )
    )
    return {
        "record": record_data(ctx, item),
        "jobs": [job_data(job) for job in jobs],
        "review_required": bool(jobs and jobs[0].status == "concluido"),
    }


class JobAction(Input):
    revision: int = Field(ge=1)


@router.post("/audio-jobs/{identifier}/retry", status_code=202)
def retry(
    identifier: str, body: JobAction, request: Request, ctx=Depends(context, scope="function")
):
    previous = ctx.get(AudioJob, identifier)
    item = find_record(ctx, previous.record_id, body.revision)
    if previous.status not in {"erro", "concluido"}:
        raise HTTPException(409, "Este áudio não pode ser reprocessado agora")
    attachment = ctx.get(Attachment, previous.attachment_id)
    if attachment.purgado_em:
        raise HTTPException(409, "O áudio foi removido pela retenção")
    job = create_job(ctx, request, item, attachment, previous)
    return job_data(job)


@router.post("/audio-jobs/{identifier}/discard")
def discard(
    identifier: str, body: JobAction, request: Request, ctx=Depends(context, scope="function")
):
    job = ctx.get(AudioJob, identifier)
    item = find_record(ctx, job.record_id, body.revision)
    author_only(ctx, item)
    if (
        item.status in {"confirmado", "publicado", "cancelado"}
        or latest_job(ctx, item.id).id != job.id
    ):
        raise HTTPException(409, "Este processamento não pode ser descartado")
    # Invalida o lease: resultado atrasado do worker não altera o registro.
    job.status, job.lease, job.finalizado_em = "descartado", None, now()
    attachment = ctx.get(Attachment, job.attachment_id)
    if not attachment.purgado_em:
        try:
            storage(request.app.state.settings, attachment.storage_backend).delete(
                attachment.object_key
            )
        except Exception:
            raise HTTPException(503, "Não foi possível remover o áudio. Tente novamente") from None
        attachment.purgado_em = now()
        ctx.audit(request, "audio_removido_autor", "Attachment", attachment.id)
    if item.type != "chamado":
        item.status = "aguardando_revisao"
    item.revision += 1
    record_event(ctx, request, item, "audio_descartado_para_digitacao")
    return record_data(ctx, item)


@router.get("/media/health")
def health(request: Request, ctx=Depends(context, scope="function")):
    from app.media_worker import queue_health

    return queue_health(request.app.state.settings)


def signing_key(settings):
    if settings.environment == "production" and len(settings.download_signing_key) < 32:
        raise ValueError("Configure DOWNLOAD_SIGNING_KEY com pelo menos 32 caracteres")
    return settings.download_signing_key or secrets.token_urlsafe(32)
