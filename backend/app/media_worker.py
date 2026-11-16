"""Worker RQ e dispatcher durável: payload de fila contém somente IDs opacos."""

import argparse
import json
import logging
import subprocess
import tempfile
import time
import wave
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from redis import Redis
from rq import Queue, Worker
from rq.serializers import JSONSerializer
from rq.timeouts import JobTimeoutException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.access import set_context
from app.config import Settings
from app.media import worker_context
from app.media_models import Attachment, AudioJob
from app.models import AuditEvent, Organization, new_id, now
from app.storage import storage
from app.transcription import (
    FasterWhisperProvider,
    MockProvider,
    RulesOrganizer,
    normalize_terms,
    sensitive_warnings,
)
from app.work import record_event, ticket_event
from app.work_models import KnowledgeArticle, Notification, Record, Ticket, TicketComment

REQUEST = SimpleNamespace(client=SimpleNamespace(host="worker"))


class InvalidAudio(Exception):
    def __init__(self, code="formato_invalido"):
        self.code = code


def connection(settings, blocking=False):
    return Redis.from_url(
        settings.redis_url, socket_connect_timeout=1, socket_timeout=None if blocking else 2
    )


def queue_health(settings):
    try:
        redis = connection(settings)
        redis.ping()
        workers = Worker.all(connection=redis)
        alive = any(
            worker.last_heartbeat and worker.last_heartbeat > now() - timedelta(seconds=120)
            for worker in workers
        )
        dispatcher = redis.get("soldesk:dispatcher:heartbeat")
        return {
            "redis": True,
            "worker": alive,
            "dispatcher": bool(dispatcher),
            "provider": settings.transcription_provider,
        }
    except Exception:
        return {
            "redis": False,
            "worker": False,
            "dispatcher": False,
            "provider": settings.transcription_provider,
        }


def normalize_audio(source, output, max_seconds, timeout):
    # ffmpeg/ffprobe existem exclusivamente na imagem do worker.
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(source),
        ],
        capture_output=True,
        timeout=min(30, timeout),
        check=False,
    )
    if probe.returncode:
        raise InvalidAudio()
    info = json.loads(probe.stdout)
    streams = info.get("streams", [])
    if not streams or any(stream.get("codec_type") != "audio" for stream in streams):
        raise InvalidAudio()
    duration = info.get("format", {}).get("duration")
    if duration and float(duration) > max_seconds + 0.05:
        raise InvalidAudio("duracao_excessiva")
    result = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(source),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            "-t",
            str(max_seconds + 1),
            "-threads",
            "1",
            "-y",
            str(output),
        ],
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise InvalidAudio()
    with wave.open(str(output), "rb") as audio:
        duration = audio.getnframes() / audio.getframerate()
    if duration <= 0:
        raise InvalidAudio()
    if duration > max_seconds + 0.05:
        raise InvalidAudio("duracao_excessiva")
    return duration


def locked(db, organization_id, identifier):
    set_context(db, organization_id)
    summary = db.scalar(select(AudioJob).where(AudioJob.id == identifier))
    if summary is None:
        return None, None
    # Ordem igual às rotas: registro antes do job, evitando inversão de locks.
    record = db.scalar(select(Record).where(Record.id == summary.record_id).with_for_update())
    job = db.scalar(select(AudioJob).where(AudioJob.id == identifier).with_for_update())
    set_context(db, organization_id, record.author_id)
    return record, job


def fail_job(settings, organization_id, identifier, lease, code, permanent=False):
    engine = create_engine(settings.database_url)
    try:
        with Session(engine) as db, db.begin():
            record, job = locked(db, organization_id, identifier)
            if job is None or job.lease != lease or job.status != "processando":
                return
            job.error_code, job.lease = code, None
            retry = not permanent and job.attempts < settings.audio_max_attempts
            job.status = "aguardando" if retry else "erro"
            job.enfileirado_em = None
            job.proxima_tentativa_em = (
                now() + timedelta(seconds=5 * 2**job.attempts) if retry else None
            )
            job.finalizado_em = None if retry else now()
            if record.status not in {"confirmado", "publicado", "cancelado"}:
                if record.type != "chamado":
                    record.status = "enviado" if retry else "erro"
                record.revision += 1
                record_event(
                    worker_context(db, organization_id, record.author_id),
                    REQUEST,
                    record,
                    "audio_tentativa" if retry else "audio_erro",
                )
    finally:
        engine.dispose()


def process_audio(organization_id, identifier, settings=None):
    settings = settings or Settings()
    engine = create_engine(settings.database_url)
    lease = None
    try:
        with Session(engine) as db, db.begin():
            record, job = locked(db, organization_id, identifier)
            if job is None or job.status != "aguardando":
                return
            if job.proxima_tentativa_em and job.proxima_tentativa_em > now():
                return
            if record.status in {"confirmado", "publicado", "cancelado"}:
                job.status, job.finalizado_em = "descartado", now()
                return
            lease = new_id()
            job.status, job.lease, job.iniciado_em = "processando", lease, now()
            job.attempts += 1
            job.error_code = None
            if record.type != "chamado":
                record.status = "processando"
            record.revision += 1
            ctx = worker_context(db, organization_id, record.author_id)
            record_event(ctx, REQUEST, record, "audio_processando")
            asset = db.get(Attachment, job.attachment_id)
            key, backend, purged = asset.object_key, asset.storage_backend, asset.purgado_em
            original, glossary, template = (
                record.texto_original,
                job.glossary_snapshot,
                job.template_snapshot,
            )
        if purged:
            raise InvalidAudio()
        source_data = storage(settings, backend).get(key)
        with tempfile.TemporaryDirectory(prefix="soldesk-audio-") as folder:
            source, output = Path(folder) / "input", Path(folder) / "audio.wav"
            source.write_bytes(source_data)
            duration = normalize_audio(
                source, output, settings.audio_max_seconds, settings.audio_job_timeout
            )
            if settings.transcription_provider == "disabled":
                raise RuntimeError("disabled")
            provider = (
                MockProvider(original)
                if settings.transcription_provider == "mock"
                else FasterWhisperProvider(settings)
            )
            result = provider.transcribe(str(output), "pt", glossary)
        if not result["text"].strip() or len(result["text"]) > 20000:
            raise InvalidAudio()
        normalized = normalize_terms(result["text"], glossary)
        draft = RulesOrganizer().organize(normalized, template["fields"])
        with Session(engine) as db, db.begin():
            record, job = locked(db, organization_id, identifier)
            if job is None or job.lease != lease or job.status != "processando":
                return
            if record.status in {"confirmado", "publicado", "cancelado"}:
                job.status, job.lease, job.finalizado_em = "descartado", None, now()
                return
            job.raw_text, job.normalized_text, job.organized_text = (
                result["text"],
                normalized,
                draft["text"],
            )
            job.segments, job.sections = result["segments"], draft["sections"]
            job.warnings, job.provider_metadata = (
                sensitive_warnings(result["text"]),
                {**result["metadata"], "organizer": "rules", "mode": draft["mode"]},
            )
            job.status, job.lease, job.finalizado_em = "concluido", None, now()
            asset = db.get(Attachment, job.attachment_id)
            asset.validated, asset.duration_seconds = True, duration
            record.processado_em = job.finalizado_em
            ctx = worker_context(db, organization_id, record.author_id)
            if record.type == "chamado":
                ticket = db.scalar(
                    select(Ticket).where(Ticket.id == record.ticket_id).with_for_update()
                )
                before = {"status": ticket.status, "revision": ticket.revision}
                db.add(
                    TicketComment(
                        organization_id=organization_id,
                        ticket_id=ticket.id,
                        author_id=record.author_id,
                        text=result["text"],
                        kind="transcricao_mock"
                        if result["metadata"].get("simulado")
                        else "transcricao",
                        mentioned_user_ids=[],
                    )
                )
                ticket.revision += 1
                ticket_event(ctx, REQUEST, ticket, "audio_anexado", before)
            else:
                record.status, record.texto_organizado = "aguardando_revisao", draft["text"]
                if record.article_id:
                    db.get(KnowledgeArticle, record.article_id).text = draft["text"]
            record.revision += 1
            record_event(ctx, REQUEST, record, "audio_processado")
            db.add(
                Notification(
                    organization_id=organization_id,
                    user_id=record.author_id,
                    type="registro_pronto_revisao",
                    reference_type="record",
                    reference_id=record.id,
                )
            )
    except InvalidAudio as exc:
        if lease:
            fail_job(settings, organization_id, identifier, lease, exc.code, permanent=True)
    except (subprocess.TimeoutExpired, TimeoutError, JobTimeoutException):
        if lease:
            fail_job(settings, organization_id, identifier, lease, "timeout")
    except Exception:
        if lease:
            fail_job(settings, organization_id, identifier, lease, "provedor_indisponivel")
        logging.getLogger("soldesk.worker").warning('{"event":"audio_failure"}')
    finally:
        engine.dispose()


def cleanup_organization(settings, organization_id):
    engine = create_engine(settings.database_url)
    try:
        with Session(engine) as db, db.begin():
            set_context(db, organization_id)
            org = db.get(Organization, organization_id)
            policy = org.settings.get("media", {})
            mode = policy.get("retention", "manter")
            if mode == "manter":
                return 0
            assets = list(
                db.scalars(
                    select(Attachment)
                    .where(Attachment.kind == "audio", Attachment.purgado_em.is_(None))
                    .with_for_update(skip_locked=True)
                )
            )
            count = 0
            for asset in assets:
                record = db.get(Record, asset.record_id)
                expired = mode == "apos_dias" and asset.enviado_em <= now() - timedelta(
                    days=policy.get("retention_days", 30)
                )
                confirmed = mode == "apos_confirmacao" and record.status == "confirmado"
                active = db.scalar(
                    select(AudioJob.id)
                    .where(
                        AudioJob.attachment_id == asset.id,
                        AudioJob.status.in_(["aguardando", "processando"]),
                    )
                    .limit(1)
                )
                if active or not (expired or confirmed):
                    continue
                storage(settings, asset.storage_backend).delete(asset.object_key)
                asset.purgado_em = now()
                db.add(
                    AuditEvent(
                        organization_id=organization_id,
                        actor_id=None,
                        action="audio_removido_retencao",
                        entity="Attachment",
                        entity_id=asset.id,
                        before={},
                        after={"policy": mode},
                        origin="worker",
                    )
                )
                count += 1
            return count
    finally:
        engine.dispose()


def dispatch_once(settings, cleanup=False, organization_ids=None):
    redis = connection(settings)
    redis.ping()
    engine = create_engine(settings.database_url)
    try:
        with Session(engine) as db:
            organizations = (
                organization_ids
                if organization_ids is not None
                else list(db.scalars(text("SELECT public.media_organizations()")))
            )
        for org_id in organizations:
            with Session(engine) as db, db.begin():
                set_context(db, org_id)
                rows = list(
                    db.scalars(
                        select(AudioJob).where(AudioJob.status.in_(["aguardando", "processando"]))
                    )
                )
                pending = [(job.id, job.status, job.lease, job.iniciado_em) for job in rows]
            for identifier, status, lease, started in pending:
                if status == "processando":
                    if started and started < now() - timedelta(
                        seconds=settings.audio_job_timeout + 30
                    ):
                        fail_job(settings, org_id, identifier, lease, "timeout")
                    continue
                with Session(engine) as db, db.begin():
                    set_context(db, org_id)
                    job = db.scalar(
                        select(AudioJob).where(AudioJob.id == identifier).with_for_update()
                    )
                    if (
                        job.status != "aguardando"
                        or job.proxima_tentativa_em
                        and job.proxima_tentativa_em > now()
                    ):
                        continue
                    queue = Queue(
                        "audio-urgente" if job.priority == "urgente" else "audio-normal",
                        connection=redis,
                        serializer=JSONSerializer,
                    )
                    rq_id = f"audio-{job.id}-{job.attempts}-{job.priority}"
                    existing = queue.fetch_job(rq_id)
                    if existing and str(existing.get_status()) in {
                        "JobStatus.QUEUED",
                        "JobStatus.STARTED",
                        "queued",
                        "started",
                    }:
                        continue
                    queue.enqueue_call(
                        "app.media_worker.process_audio",
                        args=(org_id, job.id),
                        job_id=rq_id,
                        timeout=settings.audio_job_timeout,
                        result_ttl=0,
                        failure_ttl=0,
                        description="Processamento privado de áudio",
                        unique=True,
                    )
                    job.enfileirado_em = now()
            if cleanup:
                cleanup_organization(settings, org_id)
        redis.set("soldesk:dispatcher:heartbeat", "ok", ex=30)
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=["worker", "dispatcher", "health", "cleanup", "storage-init", "storage-check"],
        default="worker",
        nargs="?",
    )
    args = parser.parse_args()
    settings = Settings()
    if args.mode in {"storage-init", "storage-check"}:
        backend = storage(settings)
        if args.mode == "storage-init":
            if settings.storage_backend == "s3":
                from botocore.exceptions import ClientError

                try:
                    backend.client.head_bucket(Bucket=backend.bucket)
                except ClientError as exc:
                    if str(exc.response["Error"]["Code"]) not in {
                        "404",
                        "NoSuchBucket",
                        "NotFound",
                    }:
                        raise RuntimeError("Não foi possível verificar o bucket privado") from None
                    options = {"Bucket": backend.bucket}
                    if settings.s3_region != "us-east-1":
                        options["CreateBucketConfiguration"] = {
                            "LocationConstraint": settings.s3_region
                        }
                    backend.client.create_bucket(**options)
            print("Armazenamento privado inicializado; nenhuma política pública foi criada.")
        else:
            key = f"{new_id()}/{new_id()}"
            payload = b"Verificacao ficticia do SolDesk."
            try:
                backend.put(key, payload, "text/plain")
                if backend.get(key) != payload:
                    raise RuntimeError("Arquivo de teste divergente")
            finally:
                backend.delete(key)
            print("APROVADO: escrita, leitura e remoção exclusiva do objeto fictício de teste.")
        return
    if args.mode == "health":
        health = queue_health(settings)
        raise SystemExit(0 if health["worker"] else 1)
    if args.mode in {"dispatcher", "cleanup"}:
        cycles = 0
        while True:
            try:
                dispatch_once(settings, cleanup=args.mode == "cleanup" or cycles % 30 == 0)
            except Exception:
                logging.getLogger("soldesk.worker").warning('{"event":"dispatcher_unavailable"}')
            if args.mode == "cleanup":
                return
            cycles += 1
            time.sleep(2)
    else:
        redis = connection(settings, blocking=True)
        worker = Worker(
            ["audio-urgente", "audio-normal"],
            connection=redis,
            serializer=JSONSerializer,
            log_job_description=False,
            disable_default_exception_handler=True,
            job_monitoring_interval=10,
        )
        worker.work(logging_level="WARNING")


if __name__ == "__main__":
    main()
