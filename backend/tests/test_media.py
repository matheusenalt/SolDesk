import io
import secrets
import subprocess
import wave
from datetime import timedelta
from urllib.parse import quote

import pytest
import test_identity as identity
import test_work as work_tests
from botocore.stub import Stubber
from rq import Queue, SimpleWorker
from rq.serializers import JSONSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import media_worker
from app.access import set_context
from app.media_models import Attachment, AudioJob
from app.models import AuditEvent, now
from app.storage import S3Storage, identify, storage
from app.transcription import RulesOrganizer, default_fields, normalize_terms, validate_grounding

pg_settings = identity.pg_settings
world = identity.world
login = identity.login
mutate = identity.mutate


def wav(seconds=0.1):
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * int(16000 * seconds))
    return output.getvalue()


def prepare(
    world,
    kind="finalizacao",
    content=(
        "Problema: exemplo fictício no fire bird. Resultado: CFOP 5102 informado; conferir senha."
    ),
):
    client_id = work_tests.prepare(world)
    record = work_tests.create(
        world,
        client_id,
        kind,
        texto_original=content,
        priority="urgente" if kind == "chamado" else "normal",
    )
    return client_id, record


def upload(world, record, data=None, name="exemplo.wav", mime="audio/wav"):
    csrf = world.client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return world.client.post(
        f"/api/v1/records/{record['id']}/audio?revision={record['revision']}",
        content=wav() if data is None else data,
        headers={"X-CSRF-Token": csrf, "X-Filename": quote(name), "Content-Type": mime},
    )


def file_upload(world, client_id, data=b"Relato ficticio.", name="anexo.txt", mime="text/plain"):
    csrf = world.client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return world.client.post(
        f"/api/v1/files/client/{client_id}",
        content=data,
        headers={"X-CSRF-Token": csrf, "X-Filename": quote(name), "Content-Type": mime},
    )


def run(world, job):
    media_worker.process_audio(world.a, job["id"], world.app.state.settings)
    return world.client.get(f"/api/v1/records/{job['record_id']}/processing").json()


def test_rules_preserve_free_description_codes_and_reject_ungrounded_output():
    original = "Descrição sem marcadores: fire bird, CFOP 5102 e R$ 123,45."
    normalized = normalize_terms(original, [{"term": "Firebird", "aliases": ["fire bird"]}])
    assert "CFOP 5102 e R$ 123,45" in normalized
    assert (
        RulesOrganizer().organize(normalized, default_fields("finalizacao"))["text"] == normalized
    )
    source = "Problema: relato fictício. Resultado: CFOP 5102 informado."
    result = RulesOrganizer().organize(source, default_fields("finalizacao"))
    assert result["sections"] and "5102" in result["text"]
    with pytest.raises(ValueError):
        validate_grounding(
            source,
            default_fields("finalizacao"),
            {"sections": [{"field": "result", "text": "CFOP 6102", "start": 0, "end": 9}]},
        )
    with pytest.raises(ValueError):
        normalize_terms("5102", [{"term": "6102", "aliases": ["5102"]}])


def test_mock_async_review_times_uncertainties_and_no_auto_confirmation(world):
    client_id, record = prepare(world)
    response = upload(world, record)
    assert response.status_code == 202, response.text
    job = response.json()["job"]
    assert job["status"] == "aguardando" and job["raw_text"] is None
    result = run(world, job)
    current, completed = result["record"], result["jobs"][0]
    assert completed["status"] == "concluido", completed
    assert completed["provider_metadata"]["simulado"]
    assert completed["raw_text"] == record["texto_original"]
    assert "Firebird" in completed["normalized_text"] and "5102" in completed["normalized_text"]
    assert completed["segments"][0]["uncertain"] and completed["warnings"]
    assert (
        current["ocorrido_em"] == record["ocorrido_em"]
        and current["enviado_em"] == record["enviado_em"]
    )
    assert current["processado_em"] and current["status"] == "aguardando_revisao"
    assert world.client.get(f"/api/v1/clients/{client_id}/history").json()["confirmed_total"] == 0
    assert work_tests.action(world.client, current, "confirmar").status_code == 409
    confirmed = work_tests.action(world.client, current, "confirmar", audio_reviewed=True)
    assert confirmed.status_code == 200
    # Reentrega do mesmo job não processa nem incrementa a revisão.
    assert run(world, job)["record"]["revision"] == confirmed.json()["revision"]


def test_attachments_private_links_expire_cross_organization_and_access_audit(world, monkeypatch):
    client_id, _ = prepare(world)
    response = file_upload(world, client_id)
    assert response.status_code == 201, response.text
    asset = response.json()
    assert "object_key" not in asset
    same = file_upload(world, client_id)
    assert same.json()["id"] == asset["id"]
    link = mutate(world.client, f"/attachments/{asset['id']}/link").json()["url"]
    content = world.client.get(link)
    assert content.status_code == 200 and content.content == b"Relato ficticio."
    with Session(world.admin_engine) as db:
        stored = db.get(Attachment, asset["id"])
        assert stored.object_key.startswith(world.a + "/") and "anexo" not in stored.object_key
        assert db.scalar(
            select(AuditEvent.id).where(
                AuditEvent.entity_id == asset["id"], AuditEvent.action == "arquivo_acessado"
            )
        )
    from app import media

    before = media.time.time()
    monkeypatch.setattr(media.time, "time", lambda: before + 400)
    assert world.client.get(link).status_code == 403
    monkeypatch.undo()
    login(world.client, world.admin_b, world.password)
    assert world.client.get(link).status_code == 404
    assert mutate(world.client, f"/attachments/{asset['id']}/link").status_code == 404
    assert world.client.get(f"/api/v1/files/client/{client_id}").status_code == 404
    with Session(world.runtime_engine) as db:
        set_context(db, world.b)
        assert db.get(Attachment, asset["id"]) is None


def test_upload_signature_wrong_extension_empty_size_and_disabled_provider(world):
    client_id, record = prepare(world)
    assert upload(world, record, "texto disfarçado".encode(), "exemplo.wav").status_code == 422
    assert upload(world, record, wav(), "exemplo.mp3", "audio/mpeg").status_code == 422
    assert upload(world, record, b"").status_code == 422
    assert (
        file_upload(
            world, client_id, b"<html>nao e imagem</html>", "foto.png", "image/png"
        ).status_code
        == 422
    )
    world.app.state.settings = world.app.state.settings.model_copy(
        update={"upload_max_bytes": 1024}
    )
    assert upload(world, record, wav()).status_code == 413
    world.app.state.settings = world.app.state.settings.model_copy(
        update={"transcription_provider": "disabled"}
    )
    assert upload(world, record).status_code == 503
    assert work_tests.create(world, client_id, "chamado", priority="urgente")["ticket_id"]


@pytest.mark.parametrize(
    "extension,codec,mime",
    [
        ("webm", "libopus", "audio/webm"),
        ("ogg", "libopus", "audio/ogg"),
        ("m4a", "aac", "audio/mp4"),
        ("aac", "aac", "audio/aac"),
        ("mp3", "libmp3lame", "audio/mpeg"),
        ("wav", "pcm_s16le", "audio/wav"),
    ],
)
def test_real_audio_containers_normalize_in_worker(world, tmp_path, extension, codec, mime):
    _, record = prepare(world, "conhecimento")
    source = tmp_path / ("audio." + extension)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=16000:cl=mono",
            "-t",
            "0.2",
            "-c:a",
            codec,
            str(source),
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )
    response = upload(world, record, source.read_bytes(), source.name, mime)
    assert response.status_code == 202, response.text
    data = run(world, response.json()["job"])
    assert data["jobs"][0]["status"] == "concluido", data["jobs"][0]
    assert data["record"]["article_status"] == "rascunho"
    assert data["record"]["publicado_em"] is None


def test_audio_duration_excessive_is_rejected_by_worker(world):
    _, record = prepare(world)
    world.app.state.settings = world.app.state.settings.model_copy(update={"audio_max_seconds": 1})
    response = upload(world, record, wav(2))
    assert response.status_code == 202
    result = run(world, response.json()["job"])
    assert result["jobs"][0]["status"] == "erro"
    assert "duração" in result["jobs"][0]["error"]
    assert result["record"]["status"] == "erro"


def test_timeout_retry_backoff_manual_retry_and_discard_do_not_overwrite(world, monkeypatch):
    _, record = prepare(world)
    settings = world.app.state.settings.model_copy(update={"audio_max_attempts": 2})
    world.app.state.settings = settings
    response = upload(world, record)
    job = response.json()["job"]

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("ffmpeg", 1)

    monkeypatch.setattr(media_worker, "normalize_audio", timeout)
    result = run(world, job)
    assert result["jobs"][0]["status"] == "aguardando"
    assert result["jobs"][0]["proxima_tentativa_em"]
    with Session(world.admin_engine) as db, db.begin():
        db.get(AudioJob, job["id"]).proxima_tentativa_em = now() - timedelta(seconds=1)
    result = run(world, job)
    assert result["jobs"][0]["status"] == "erro" and result["jobs"][0]["attempts"] == 2
    retried = mutate(
        world.client, f"/audio-jobs/{job['id']}/retry", {"revision": result["record"]["revision"]}
    )
    assert retried.status_code == 202
    assert retried.json()["id"] != job["id"]
    current = world.client.get(f"/api/v1/records/{record['id']}").json()
    discarded = mutate(
        world.client,
        f"/audio-jobs/{retried.json()['id']}/discard",
        {"revision": current["revision"]},
    )
    assert discarded.status_code == 200
    assert run(world, retried.json())["record"]["revision"] == discarded.json()["revision"]
    assert discarded.json()["status"] == "aguardando_revisao"


def test_real_rq_urgent_ticket_can_resolve_before_audio_with_worker_stopped(world):
    _, record = prepare(world, "chamado")
    job = upload(world, record).json()["job"]
    settings = world.app.state.settings
    media_worker.dispatch_once(settings, organization_ids=[world.a])
    queued = world.client.get(f"/api/v1/records/{record['id']}/processing").json()
    assert queued["jobs"][0]["status"] == "aguardando"
    ticket = mutate(
        world.client,
        f"/tickets/{record['ticket_id']}",
        {
            "revision": 1,
            "priority": "urgente",
            "status": "resolvido",
            "completion_description": "Procedimento fictício executado",
        },
        "PATCH",
    )
    assert ticket.status_code == 200
    redis = media_worker.connection(settings)
    worker = SimpleWorker(
        [
            Queue("audio-urgente", connection=redis, serializer=JSONSerializer),
            Queue("audio-normal", connection=redis, serializer=JSONSerializer),
        ],
        connection=redis,
        serializer=JSONSerializer,
        log_job_description=False,
    )
    worker.work(burst=True, logging_level="WARNING")
    data = world.client.get(f"/api/v1/records/{record['id']}/processing").json()
    assert data["jobs"][0]["id"] == job["id"] and data["jobs"][0]["status"] == "concluido", data
    detail = world.client.get(f"/api/v1/tickets/{record['ticket_id']}").json()
    assert detail["status"] == "encerrado" and detail["comments"][-1]["kind"] == "transcricao_mock"


def test_template_versions_glossary_immutable_snapshot_and_retention_cleanup(world):
    _, record = prepare(world)
    job = upload(world, record).json()["job"]
    template = next(
        item
        for item in world.client.get("/api/v1/media/templates").json()
        if item["type"] == "finalizacao"
    )
    created = mutate(
        world.client,
        "/media/templates",
        {
            "type": "finalizacao",
            "expected_version": template["version"],
            "fields": [{"key": "description", "label": "Descrição", "markers": ["Relato"]}],
        },
    )
    assert created.status_code == 201
    assert (
        mutate(world.client, "/media/glossary", {"term": "CFOP 5102", "aliases": []}).status_code
        == 422
    )
    data = run(world, job)
    assert data["jobs"][0]["template_snapshot"]["version"] == template["version"]
    assert media_worker.cleanup_organization(world.app.state.settings, world.a) == 0
    confirmed = work_tests.action(world.client, data["record"], "confirmar", audio_reviewed=True)
    assert confirmed.status_code == 200
    changed = mutate(
        world.client,
        "/media/settings",
        {"retention": "apos_confirmacao", "retention_days": 30, "live_dictation_enabled": False},
        "PATCH",
    )
    assert changed.status_code == 200
    assert media_worker.cleanup_organization(world.app.state.settings, world.a) == 1
    assert media_worker.cleanup_organization(world.app.state.settings, world.a) == 0
    assert mutate(world.client, f"/attachments/{job['attachment_id']}/link").status_code == 404
    with Session(world.admin_engine) as db:
        assert db.scalar(
            select(AuditEvent.id).where(
                AuditEvent.entity_id == job["attachment_id"],
                AuditEvent.action == "audio_removido_retencao",
            )
        )


def test_s3_adapter_requests_private_objects_without_public_acl(world):
    settings = world.app.state.settings.model_copy(
        update={
            "s3_access_key": "ficticio",
            "s3_secret_key": secrets.token_hex(32),
            "s3_endpoint_url": "http://localhost:19000",
        }
    )
    backend = S3Storage(settings)
    key = world.a + "/" + str(__import__("uuid").uuid4())
    with Stubber(backend.client) as stub:
        stub.add_response(
            "put_object",
            {},
            {
                "Bucket": settings.s3_bucket,
                "Key": key,
                "Body": b"ficticio",
                "ContentType": "text/plain",
            },
        )
        stub.add_response(
            "get_object",
            {"Body": io.BytesIO(b"ficticio")},
            {"Bucket": settings.s3_bucket, "Key": key},
        )
        stub.add_response("delete_object", {}, {"Bucket": settings.s3_bucket, "Key": key})
        backend.put(key, b"ficticio", "text/plain")
        assert backend.get(key) == b"ficticio"
        backend.delete(key)
    with pytest.raises(ValueError):
        storage(settings).get("../fora")
    assert identify(wav(), "audio.wav", "audio/wav", True, "") == "audio/wav"


def test_audio_cross_tenant_session_link_and_late_discard_result(world, monkeypatch):
    _, record = prepare(world)
    job = upload(world, record).json()["job"]
    data = run(world, job)
    link = mutate(world.client, f"/attachments/{job['attachment_id']}/link").json()["url"]
    login(world.client, world.admin_b, world.password)
    assert world.client.get(link).status_code == 404
    assert world.client.get(f"/api/v1/records/{record['id']}/processing").status_code == 404
    assert (
        mutate(
            world.client, f"/audio-jobs/{job['id']}/retry", {"revision": data["record"]["revision"]}
        ).status_code
        == 404
    )
    with Session(world.runtime_engine) as db:
        set_context(db, world.b)
        assert db.get(AudioJob, job["id"]) is None
    login(world.client, world.admin_a, world.password)
    assert (
        work_tests.action(
            world.client, data["record"], "confirmar", audio_reviewed=True
        ).status_code
        == 200
    )
    login(world.client, world.technician, world.password)
    assert (
        world.client.get(link).status_code == 403
    )  # Visível após confirmação, assinatura de outra sessão.
    login(world.client, world.admin_a, world.password)
    client_id = record["client_id"]
    another = work_tests.create(world, client_id)
    pending = upload(world, another).json()["job"]
    original = media_worker.MockProvider.transcribe

    def discard_during_processing(provider, *args):
        current = world.client.get(f"/api/v1/records/{another['id']}").json()
        discarded = mutate(
            world.client, f"/audio-jobs/{pending['id']}/discard", {"revision": current["revision"]}
        )
        assert discarded.status_code == 200
        edited = mutate(
            world.client,
            f"/records/{another['id']}",
            {
                "revision": discarded.json()["revision"],
                "texto_organizado": "Digitação humana fictícia após descarte.",
            },
            "PATCH",
        )
        assert edited.status_code == 200
        return original(provider, *args)

    monkeypatch.setattr(media_worker.MockProvider, "transcribe", discard_during_processing)
    final = run(world, pending)
    assert final["jobs"][0]["status"] == "descartado"
    assert final["record"]["texto_organizado"] == "Digitação humana fictícia após descarte."
    assert final["record"]["processado_em"] is None


def test_stuck_worker_timeout_recovered_by_dispatcher(world, monkeypatch):
    _, record = prepare(world)
    world.app.state.settings = world.app.state.settings.model_copy(
        update={"audio_max_attempts": 1, "audio_job_timeout": 2}
    )
    job = upload(world, record).json()["job"]

    def interrupted(*args):
        raise SystemExit(1)

    monkeypatch.setattr(media_worker.MockProvider, "transcribe", interrupted)
    with pytest.raises(SystemExit):
        run(world, job)
    with Session(world.admin_engine) as db, db.begin():
        row = db.get(AudioJob, job["id"])
        assert row.status == "processando"
        row.iniciado_em = now() - timedelta(seconds=60)
    media_worker.dispatch_once(world.app.state.settings, organization_ids=[world.a])
    result = world.client.get(f"/api/v1/records/{record['id']}/processing").json()
    assert result["jobs"][0]["status"] == "erro"
    assert "tempo" in result["jobs"][0]["error"]


def test_retention_days_and_live_dictation_opt_in(world):
    client_id, record = prepare(world)
    rejected = mutate(
        world.client,
        "/records",
        {
            "client_id": client_id,
            "type": "finalizacao",
            "texto_original": "Relato fictício.",
            "ditado_texto": "Ditado fictício.",
        },
    )
    assert rejected.status_code == 403
    assert (
        mutate(
            world.client,
            "/media/settings",
            {"retention": "apos_dias", "retention_days": 1, "live_dictation_enabled": True},
            "PATCH",
        ).status_code
        == 200
    )
    accepted = mutate(
        world.client,
        "/records",
        {
            "client_id": client_id,
            "type": "finalizacao",
            "texto_original": "Relato fictício.",
            "ditado_texto": "Ditado fictício original.",
        },
    )
    assert (
        accepted.status_code == 201
        and accepted.json()["ditado_texto"] == "Ditado fictício original."
    )
    job = upload(world, record).json()["job"]
    run(world, job)
    with Session(world.admin_engine) as db, db.begin():
        db.get(Attachment, job["attachment_id"]).enviado_em = now() - timedelta(days=2)
    assert media_worker.cleanup_organization(world.app.state.settings, world.a) == 1


def test_antivirus_protocol_and_rejection(monkeypatch):
    from app import storage as module
    from app.config import Settings

    sent = []

    class Scanner:
        result = b"stream: OK\0"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def sendall(self, data):
            sent.append(data)

        def recv(self, size):
            return self.result

    scanner = Scanner()
    monkeypatch.setattr(module.socket, "create_connection", lambda *args, **kwargs: scanner)
    settings = Settings(clamav_enabled=True)
    module.scan_antivirus(settings, b"arquivo ficticio")
    assert sent[0] == b"zINSTREAM\0" and sent[-1] == b"\0\0\0\0"
    scanner.result = b"stream: Simulacao FOUND\0"
    with pytest.raises(ValueError):
        module.scan_antivirus(settings, b"arquivo ficticio")
