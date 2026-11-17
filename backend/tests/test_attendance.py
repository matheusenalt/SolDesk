from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
import test_content_validation as validation
import test_identity as identity
import test_media as media
import test_work as work
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.access import set_context
from app.models import now
from app.work_models import Attendance, Record

pg_settings = identity.pg_settings
world = identity.world


def opened(world, **fields):
    work.prepare(world)
    response = work.send(
        world.client,
        "/attendances",
        {
            "internal_activity": True,
            "texto_original": "Atividade interna fictícia",
            **fields,
        },
        str(uuid4()),
    )
    assert response.status_code == 201, response.text
    return response.json()


def update(world, attendance, **fields):
    return work.send(
        world.client,
        f"/attendances/{attendance['id']}/updates",
        {
            "revision": attendance["revision"],
            "texto_original": "Atualização fictícia",
            **fields,
        },
        str(uuid4()),
    )


def test_cycle_history_dates_audio_validation_and_finalization(world, monkeypatch):
    item = opened(world)
    identifier = item["id"]
    occurred = (now() - timedelta(days=2)).isoformat()
    response = update(
        world,
        item,
        ocorrido_em=occurred,
        next_action="Conferir retorno",
        retomada_em=(now() + timedelta(days=1)).isoformat(),
    )
    assert response.status_code == 201, response.text
    child = response.json()["update"]
    item = response.json()["attendance"]
    assert item["status"] == "aguardando_retomada" and not item["pending"]
    assert child["origem_record_id"] == identifier
    assert child["ocorrido_em"] != item["record"]["ocorrido_em"]
    assert validation.validate(world.client, child).status_code == 200
    audio = media.upload(world, child)
    assert audio.status_code == 202, audio.text
    assert validation.current(world.client, child)["status"] == "processando"
    media.run(world, audio.json()["job"])
    assert validation.current(world.client, child)["status"] == "nao_validado"
    assert (
        world.client.get(f"/api/v1/attendances/{identifier}").json()["status"]
        == "aguardando_retomada"
    )
    import app.attendance_routes as routes

    monkeypatch.setattr(routes, "now", lambda: now() + timedelta(days=2))
    pending = world.client.get("/api/v1/attendances?pending=true").json()
    assert identifier in [row["id"] for row in pending["items"]]
    assert pending["items"][0]["status"] == "aguardando_retomada"
    monkeypatch.undo()
    finished = update(world, item, action="finalizar", result="Retorno conferido pelo técnico")
    assert finished.status_code == 201, finished.text
    item = finished.json()["attendance"]
    assert item["id"] == identifier and item["status"] == "finalizado"
    assert update(world, item).status_code == 409
    for record in (item["record"], child):
        fresh = world.client.get(f"/api/v1/records/{record['id']}").json()
        assert (
            identity.mutate(
                world.client,
                f"/records/{fresh['id']}/derive",
                {"revision": fresh["revision"], "type": "finalizacao"},
            ).status_code
            == 409
        )
    detail = world.client.get(f"/api/v1/attendances/{identifier}").json()
    assert detail["updates_total"] == 2 and detail["events_total"] == 3
    assert detail["updates"][0]["texto_original"] == "Atualização fictícia"
    assert detail["record"]["ocorrido_em"] == item["record"]["ocorrido_em"]


def test_internal_finalization_and_database_constraint(world):
    work.prepare(world)
    body = {"type": "finalizacao", "texto_original": "Manutenção interna fictícia"}
    denied = work.send(world.client, "/records", body, str(uuid4()))
    assert denied.status_code == 422
    created = work.send(world.client, "/records", {**body, "internal_activity": True}, str(uuid4()))
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["client_id"] is None and record["client_name"] is None
    assert work.action(world.client, record, "confirmar").status_code == 200
    report = world.client.get("/api/v1/reports?preset=inicio")
    assert report.status_code == 200, report.text
    assert report.json()["internal_activities"] == 1
    assert report.json()["clients"] == []
    report = world.client.get("/api/v1/reports?preset=inicio")
    assert report.status_code == 200, report.text
    with Session(world.admin_engine) as db, db.begin():
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(
                text("""INSERT INTO record
                (id,organization_id,author_id,type,texto_original,status,revision,ocorrido_em,enviado_em,category,system)
                SELECT :id,organization_id,author_id,type,'Fato fictício',status,1,now(),now(),'',''
                FROM record WHERE id=:source"""),
                {"id": str(uuid4()), "source": record["id"]},
            )


def test_transfer_permissions_tenant_and_rls(world):
    item = opened(world)
    transferred = update(
        world,
        item,
        action="transferir",
        assignee_id=world.technician_id,
        next_action="Conferir pendência fictícia",
    )
    assert transferred.status_code == 201, transferred.text
    item = transferred.json()["attendance"]
    identity.login(world.client, world.technician, world.password)
    assert world.client.get(f"/api/v1/attendances/{item['id']}").status_code == 200
    assert update(world, item).status_code == 201
    identity.login(world.client, world.admin_b, world.password)
    assert world.client.get(f"/api/v1/attendances/{item['id']}").status_code == 404
    assert update(world, item).status_code == 404
    with Session(world.runtime_engine) as db, db.begin():
        set_context(db, world.b)
        assert db.scalar(select(Attendance).where(Attendance.id == item["id"])) is None
    identity.login(world.client, world.admin_a, world.password)
    detail = world.client.get(f"/api/v1/attendances/{item['id']}").json()
    assert any(event["action"] == "atendimento_transferir" for event in detail["events"])


def test_unassigned_technician_cannot_read_even_confirmed_content(world):
    item = opened(world)
    assert work.action(world.client, item["record"], "confirmar").status_code == 200
    identity.login(world.client, world.technician, world.password)
    assert world.client.get(f"/api/v1/attendances/{item['id']}").status_code == 404
    assert world.client.get(f"/api/v1/records/{item['id']}").status_code == 404
    assert update(world, item).status_code == 404


def test_concurrent_updates_conflict_and_retry_idempotence(world):
    item = opened(world)
    barrier = Barrier(2)
    key = str(uuid4())
    body = {"revision": item["revision"], "texto_original": "Atualização concorrente fictícia"}

    def send(index):
        with TestClient(world.app, client=(uuid4().hex, 1234)) as client:
            identity.login(client, world.admin_a, world.password)
            barrier.wait(timeout=10)
            return work.send(
                client,
                f"/attendances/{item['id']}/updates",
                body,
                key if index == 0 else str(uuid4()),
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, [0, 1]))
    assert sorted(results) == [201, 409]
    detail = world.client.get(f"/api/v1/attendances/{item['id']}").json()
    assert detail["updates_total"] == 1
    # Reenvio da requisição vencedora permanece idempotente mesmo com revisão antiga.
    if results[0] == 201:
        assert (
            work.send(world.client, f"/attendances/{item['id']}/updates", body, key).status_code
            == 201
        )
    else:
        body["revision"] = detail["revision"]
        assert (
            work.send(world.client, f"/attendances/{item['id']}/updates", body, key).status_code
            == 201
        )
        assert (
            work.send(world.client, f"/attendances/{item['id']}/updates", body, key).status_code
            == 201
        )
    with Session(world.admin_engine) as db:
        rows = db.scalars(select(Record).where(Record.origem_record_id == item["id"])).all()
        assert len(rows) == (1 if results[0] == 201 else 2)


def test_open_idempotency_rejects_different_assignee_and_missing_context(world):
    client_id = work.prepare(world)
    key = str(uuid4())
    body = {"client_id": client_id, "texto_original": "Descrição fictícia"}
    first = work.send(world.client, "/attendances", body, key)
    assert first.status_code == 201, first.text
    assert work.send(world.client, "/attendances", body, key).json()["id"] == first.json()["id"]
    assert (
        work.send(
            world.client, "/attendances", {**body, "assignee_id": world.technician_id}, key
        ).status_code
        == 409
    )
    assert (
        work.send(
            world.client, "/attendances", {"texto_original": "Sem contexto"}, str(uuid4())
        ).status_code
        == 422
    )
    assert first.json()["record"]["client_id"] == client_id


def test_invalid_transitions_dates_and_client_context_do_not_append_history(world):
    item = opened(world)
    assert update(world, item, action="finalizar", result=" ").status_code == 422
    assert update(world, item, result="Resultado fora da finalização").status_code == 422
    assert (
        update(world, item, ocorrido_em=(now() + timedelta(days=1)).isoformat()).status_code == 422
    )
    assert (
        update(world, item, retomada_em=(now() - timedelta(days=1)).isoformat()).status_code == 422
    )
    assert update(world, item, organization_id=world.b).status_code == 422
    assert update(world, item, action="transferir").status_code == 422
    assert world.client.get(f"/api/v1/attendances/{item['id']}").json()["updates_total"] == 0


def test_audio_first_saves_empty_source_without_inventing_text(world, monkeypatch):
    item = opened(world, texto_original="")
    assert item["record"]["texto_original"] == ""
    response = update(world, item, texto_original="")
    assert response.status_code == 201, response.text
    child = response.json()["update"]
    uploaded = media.upload(world, child)
    assert uploaded.status_code == 202, uploaded.text
    assert validation.current(world.client, child)["status"] == "processando"
    assert media.run(world, uploaded.json()["job"])["jobs"][0]["status"] == "erro"
    # Provedor mock não reconhece fala e não inventa texto para preencher o vazio.
    assert validation.current(world.client, child)["status"] == "nao_validado"
    assert world.client.get(f"/api/v1/records/{child['id']}").json()["texto_original"] == ""
    # Provedor de teste controlado: testa o contrato, sem afirmar reconhecimento real.
    monkeypatch.setattr(
        media.media_worker.MockProvider,
        "transcribe",
        lambda *_: {
            "text": "Procedimento fictício narrado",
            "segments": [],
            "metadata": {"simulado": True},
        },
    )
    fresh = world.client.get(f"/api/v1/records/{child['id']}").json()
    retried = identity.mutate(
        world.client,
        f"/audio-jobs/{uploaded.json()['job']['id']}/retry",
        {"revision": fresh["revision"]},
    )
    assert retried.status_code == 202, retried.text
    assert media.run(world, retried.json())["jobs"][0]["status"] == "concluido"
    assert validation.current(world.client, fresh)["status"] == "nao_validado"


def test_author_after_transfer_reads_updates_but_cannot_write(world):
    work.prepare(world)
    identity.login(world.client, world.technician, world.password)
    response = work.send(
        world.client,
        "/attendances",
        {"internal_activity": True, "texto_original": "Atividade fictícia"},
        str(uuid4()),
    )
    assert response.status_code == 201, response.text
    item = response.json()
    with Session(world.admin_engine) as db:
        from app.models import User

        admin_id = db.scalar(select(User.id).where(User.email == world.admin_a))
    moved = update(world, item, action="transferir", assignee_id=admin_id)
    assert moved.status_code == 201, moved.text
    item = moved.json()["attendance"]
    assert update(world, item).status_code == 403
    identity.login(world.client, world.admin_a, world.password)
    added = update(world, item)
    assert added.status_code == 201, added.text
    child = added.json()["update"]
    identity.login(world.client, world.technician, world.password)
    assert world.client.get(f"/api/v1/records/{child['id']}").status_code == 200
    assert validation.validate(world.client, child).status_code == 200


def test_simultaneous_duplicate_resend_creates_only_one_update(world):
    item = opened(world)
    barrier = Barrier(2)
    key = str(uuid4())
    body = {"revision": item["revision"], "texto_original": "Mesmo fato fictício"}

    def send(_):
        with TestClient(world.app, client=(uuid4().hex, 1234)) as client:
            identity.login(client, world.admin_a, world.password)
            barrier.wait(timeout=10)
            result = work.send(client, f"/attendances/{item['id']}/updates", body, key)
            assert result.status_code == 201, result.text
            return result.json()["update"]["id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(send, [0, 1]))
    assert ids[0] == ids[1]
    assert world.client.get(f"/api/v1/attendances/{item['id']}").json()["updates_total"] == 1
