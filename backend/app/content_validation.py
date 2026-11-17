"""Snapshots materiais e conferência humana sob o mesmo lock da edição."""

import hashlib
import json

from fastapi import HTTPException

from app.media_models import AudioJob
from app.validation_models import ContentValidation, RecordContentVersion
from app.work_models import Record, RecordVersion

RECORD_FIELDS = (
    "client_id",
    "type",
    "texto_original",
    "texto_organizado",
    "ditado_texto",
    "ocorrido_em",
    "category",
    "system",
)
AUDIO_FIELDS = (
    "id",
    "raw_text",
    "normalized_text",
    "organized_text",
    "segments",
    "warnings",
    "sections",
)


def latest_version(ctx, identifier):
    return ctx.db.scalar(
        ctx.query(RecordContentVersion)
        .where(RecordContentVersion.record_id == identifier)
        .order_by(RecordContentVersion.record_revision.desc())
        .limit(1)
    )


def capture_version(ctx, record, event):
    job = ctx.db.scalar(
        ctx.query(AudioJob)
        .where(AudioJob.record_id == record.id)
        .order_by(AudioJob.criado_em.desc(), AudioJob.id.desc())
        .limit(1)
    )
    content = {
        "record": {key: event.snapshot.get(key) for key in RECORD_FIELDS},
        "transcription": (
            {key: getattr(job, key) for key in AUDIO_FIELDS}
            if job and job.raw_text is not None and job.status != "descartado"
            else None
        ),
    }
    canonical = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    previous = latest_version(ctx, record.id)
    if previous and previous.canonical_snapshot == canonical:
        return
    ctx.db.add(
        RecordContentVersion(
            organization_id=ctx.organization_id,
            record_id=record.id,
            record_revision=record.revision,
            source_version_id=event.id,
            canonical_snapshot=canonical,
            content_hash=hashlib.sha256(canonical.encode()).hexdigest(),
        )
    )
    ctx.db.flush()


def validation_data(ctx, record):
    version = latest_version(ctx, record.id)
    history = list(
        ctx.db.scalars(
            ctx.query(ContentValidation)
            .where(ContentValidation.record_id == record.id)
            .order_by(ContentValidation.validado_em, ContentValidation.id)
        )
    )
    source = ctx.get(RecordVersion, version.source_version_id) if version else None
    return {
        "status": "validado"
        if version and any(v.version_id == version.id for v in history)
        else "nao_validado",
        "version": {
            "id": version.id,
            "record_revision": version.record_revision,
            "content_hash": version.content_hash,
            "content": json.loads(version.canonical_snapshot),
            "criado_em": version.criado_em,
            "source_version_id": version.source_version_id,
            "source_actor_id": source.actor_id,
            "source_change": source.change,
        }
        if version
        else None,
        "validations": [
            {
                "id": v.id,
                "version_id": v.version_id,
                "content_hash": v.content_hash,
                "validated_by": v.validated_by,
                "validado_em": v.validado_em,
            }
            for v in history
        ],
    }


def validate_content(ctx, request, identifier, body):
    from app.work import record_query

    # Mesma ordem da edição e do worker: registro antes de qualquer versão/job.
    record = ctx.db.scalar(record_query(ctx).where(Record.id == identifier).with_for_update())
    if record is None:
        raise HTTPException(404, "Registro não encontrado")
    version = latest_version(ctx, identifier)
    if not version or version.id != body.version_id or version.content_hash != body.content_hash:
        raise HTTPException(
            409, "O conteúdo mudou. Recarregue e confira a versão atual antes de validar"
        )
    existing = ctx.db.scalar(
        ctx.query(ContentValidation).where(
            ContentValidation.version_id == version.id,
            ContentValidation.validated_by == ctx.user.id,
        )
    )
    if existing is None:
        value = ContentValidation(
            organization_id=ctx.organization_id,
            record_id=identifier,
            version_id=version.id,
            content_hash=version.content_hash,
            validated_by=ctx.user.id,
        )
        ctx.db.add(value)
        ctx.db.flush()
        ctx.audit(
            request,
            "fidelidade_validada",
            "Record",
            identifier,
            after={
                "version_id": version.id,
                "content_hash": version.content_hash,
            },
        )
    return validation_data(ctx, record)
