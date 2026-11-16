from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import test_identity as identity
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app import work
from app.access import set_context
from app.models import AuditEvent
from app.work_models import Notification, Record, Ticket

login = identity.login
mutate = identity.mutate
pg_settings = identity.pg_settings
world = identity.world


def send(client, path, body, key):
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return client.post(
        "/api/v1" + path, json=body, headers={"X-CSRF-Token": token, "Idempotency-Key": key}
    )


def prepare(world):
    login(world.client, world.admin_a, world.password)
    result = mutate(world.client, "/clients", {"name": "Cliente fictício de atendimento"})
    assert result.status_code == 201, result.text
    return result.json()["id"]


def create(world, client_id, kind="finalizacao", **values):
    response = send(
        world.client,
        "/records",
        {
            "client_id": client_id,
            "type": kind,
            "texto_original": "Relato fictício informado pelo técnico, sem conclusão adicionada.",
            **values,
        },
        str(uuid4()),
    )
    assert response.status_code == 201, response.text
    return response.json()


def action(client, item, name, **values):
    return mutate(
        client,
        f"/records/{item['id']}/actions",
        {"revision": item["revision"], "action": name, **values},
    )


def test_occurrence_review_time_history_and_immutable_versions(world, monkeypatch):
    client = world.client
    client_id = prepare(world)
    sent = datetime(2026, 11, 15, 14, 35, tzinfo=UTC)
    monkeypatch.setattr(work, "now", lambda: sent)
    item = create(world, client_id, ocorrido_em=sent.isoformat())
    assert item["status"] == "aguardando_revisao"
    assert item["revisado_em"] is None and item["processado_em"] is None
    history = client.get(f"/api/v1/clients/{client_id}/history").json()
    assert history["confirmed_total"] == 0 and history["items"] == []
    provisional = client.get(f"/api/v1/clients/{client_id}/history?include_provisional=true").json()
    assert provisional["items"][0]["provisional"] is True
    adjusted = sent - timedelta(hours=1)
    response = mutate(
        client,
        f"/records/{item['id']}",
        {
            "revision": item["revision"],
            "texto_organizado": "Correção humana fictícia.",
            "ocorrido_em": adjusted.isoformat(),
        },
        "PATCH",
    )
    assert response.status_code == 200, response.text
    item = response.json()
    reviewed = sent.replace(hour=17, minute=50)
    monkeypatch.setattr(work, "now", lambda: reviewed)
    confirmed = action(client, item, "confirmar")
    assert confirmed.status_code == 200, confirmed.text
    item = confirmed.json()
    assert datetime.fromisoformat(item["ocorrido_em"]) == adjusted
    assert datetime.fromisoformat(item["enviado_em"]) == sent
    assert datetime.fromisoformat(item["revisado_em"]) == reviewed
    assert item["texto_original"].startswith("Relato fictício")
    assert client.get(f"/api/v1/clients/{client_id}/history").json()["confirmed_total"] == 1
    assert (
        mutate(
            client,
            f"/records/{item['id']}",
            {"revision": item["revision"], "texto_organizado": "Substituição indevida"},
            "PATCH",
        ).status_code
        == 409
    )
    assert client.delete(f"/api/v1/records/{item['id']}").status_code == 405
    versions = client.get(f"/api/v1/records/{item['id']}/versions").json()
    assert [v["revision"] for v in versions] == [1, 2, 3]
    assert versions[0]["snapshot"]["texto_organizado"] is None
    with Session(world.admin_engine) as db:
        events = db.scalars(
            select(AuditEvent).where(
                AuditEvent.entity_id == item["id"], AuditEvent.action == "horario_ajustado"
            )
        ).all()
        assert len(events) == 1
        assert datetime.fromisoformat(events[0].before["ocorrido_em"]) == sent
        assert datetime.fromisoformat(events[0].after["ocorrido_em"]) == adjusted
    with Session(world.runtime_engine) as db:
        set_context(db, world.a)
        with pytest.raises(DBAPIError):
            db.execute(
                text("UPDATE record_version SET change='tentativa' WHERE record_id=:id"),
                {"id": item["id"]},
            )
        db.rollback()
        set_context(db, world.a)
        with pytest.raises(DBAPIError):
            db.execute(text("UPDATE record SET enviado_em=now() WHERE id=:id"), {"id": item["id"]})
        db.rollback()


def test_future_capture_and_author_only_review_including_batch(world):
    client_id = prepare(world)
    login(world.client, world.technician, world.password)
    item = create(world, client_id, capturado_em="2099-01-01T00:00:00Z")
    assert item["capturado_em"].startswith("2099")  # Dado não confiável, não usado como envio.
    assert not item["enviado_em"].startswith("2099")
    future = send(
        world.client,
        "/records",
        {
            "client_id": client_id,
            "type": "finalizacao",
            "texto_original": "Relato",
            "ocorrido_em": "2099-01-01T00:00:00Z",
        },
        str(uuid4()),
    )
    assert future.status_code == 422
    login(world.client, world.admin_a, world.password)
    assert action(world.client, item, "confirmar").status_code == 403
    assert (
        mutate(
            world.client,
            "/records/reviews/confirm",
            {"items": [{"id": item["id"], "revision": item["revision"]}]},
        ).status_code
        == 403
    )
    login(world.client, world.technician, world.password)
    other = create(world, client_id)
    batch = mutate(
        world.client,
        "/records/reviews/confirm",
        {
            "items": [
                {"id": item["id"], "revision": item["revision"]},
                {"id": other["id"], "revision": other["revision"] + 1},
            ]
        },
    )
    assert batch.status_code == 409
    assert (
        world.client.get(f"/api/v1/records/{item['id']}").json()["status"] == "aguardando_revisao"
    )
    batch = mutate(
        world.client,
        "/records/reviews/confirm",
        {
            "items": [
                {"id": item["id"], "revision": item["revision"]},
                {"id": other["id"], "revision": other["revision"]},
            ]
        },
    )
    assert batch.status_code == 200
    assert all(row["status"] == "confirmado" for row in batch.json()["items"])


def test_normal_and_urgent_tickets_bypass_review_and_resolve_close_reopen(world):
    client_id = prepare(world)
    client = world.client
    normal = create(world, client_id, "chamado", assignee_id=world.technician_id)
    urgent = create(
        world, client_id, "chamado", assignee_id=world.technician_id, priority="urgente"
    )
    assert normal["status"] == urgent["status"] == "enviado"
    assert normal["ticket_id"] != urgent["ticket_id"]
    assert normal["revisado_em"] is None
    ticket_id = urgent["ticket_id"]
    login(client, world.technician, world.password)
    ticket = client.get(f"/api/v1/tickets/{ticket_id}").json()
    assert ticket["status"] == "aberto" and ticket["priority"] == "urgente"
    assert mutate(
        client,
        f"/tickets/{ticket_id}",
        {"revision": ticket["revision"], "status": "encerrado"},
        "PATCH",
    ).status_code in {403, 409}
    resolved = mutate(
        client,
        f"/tickets/{ticket_id}",
        {"revision": ticket["revision"], "status": "resolvido"},
        "PATCH",
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["closed_by"] is None
    assert resolved.json()["status"] == "resolvido"
    login(client, world.admin_a, world.password)
    closed = mutate(
        client,
        f"/tickets/{ticket_id}",
        {"revision": resolved.json()["revision"], "status": "encerrado"},
        "PATCH",
    )
    assert closed.status_code == 200
    assert closed.json()["resolved_by"] != closed.json()["closed_by"]
    reopened = mutate(
        client,
        f"/tickets/{ticket_id}",
        {"revision": closed.json()["revision"], "status": "reaberto"},
        "PATCH",
    )
    assert reopened.status_code == 200
    assert reopened.json()["id"] == ticket_id and reopened.json()["reopen_count"] == 1


def test_opener_may_close_but_cannot_transfer_while_closing(world):
    client_id = prepare(world)
    client = world.client
    admin_id = client.get("/api/v1/me").json()["id"]
    login(client, world.technician, world.password)
    item = create(world, client_id, "chamado", assignee_id=admin_id)
    identifier = item["ticket_id"]
    login(client, world.admin_a, world.password)
    resolved = mutate(
        client, f"/tickets/{identifier}", {"revision": 1, "status": "resolvido"}, "PATCH"
    )
    assert resolved.status_code == 200
    login(client, world.technician, world.password)
    assert (
        mutate(
            client,
            f"/tickets/{identifier}",
            {"revision": 2, "status": "encerrado", "assignee_id": world.technician_id},
            "PATCH",
        ).status_code
        == 403
    )
    closed = mutate(
        client, f"/tickets/{identifier}", {"revision": 2, "status": "encerrado"}, "PATCH"
    )
    assert closed.status_code == 200
    assert closed.json()["assignee_id"] == admin_id


def test_clarification_comments_mentions_wait_intervals_and_transfer(world):
    client_id = prepare(world)
    item = create(world, client_id, "chamado", assignee_id=world.technician_id)
    client = world.client
    login(client, world.technician, world.password)
    identifier = item["ticket_id"]
    ticket = client.get(f"/api/v1/tickets/{identifier}").json()
    response = mutate(
        client,
        f"/tickets/{identifier}/comments",
        {
            "revision": ticket["revision"],
            "kind": "esclarecimento",
            "text": "Informe o detalhe que falta no relato fictício.",
            "mentioned_user_ids": [client.get("/api/v1/assignment-options").json()[0]["id"]],
        },
    )
    assert response.status_code == 201, response.text
    login(client, world.admin_a, world.password)
    assert any(
        n["type"] == "esclarecimento_solicitado"
        for n in client.get("/api/v1/notifications").json()["items"]
    )
    answer = mutate(
        client,
        f"/tickets/{identifier}/comments",
        {
            "revision": response.json()["revision"],
            "kind": "resposta",
            "text": "Complemento fictício, preservando a solicitação anterior.",
        },
    )
    assert answer.status_code == 201 and answer.json()["status"] == "em_andamento"
    detail = client.get(f"/api/v1/tickets/{identifier}").json()
    assert len(detail["comments"]) == 2
    assert detail["comments"][0]["kind"] == "esclarecimento"
    interval = detail["intervals"][0]
    assert interval["status"] == "aguardando_esclarecimento"
    assert interval["saida_em"] >= interval["entrada_em"]
    waiting = mutate(
        client,
        f"/tickets/{identifier}",
        {"revision": detail["revision"], "status": "aguardando_terceiros"},
        "PATCH",
    ).json()
    resumed = mutate(
        client,
        f"/tickets/{identifier}",
        {
            "revision": waiting["revision"],
            "status": "em_andamento",
            "assignee_id": client.get("/api/v1/me").json()["id"],
            "priority": "alta",
        },
        "PATCH",
    )
    assert resumed.status_code == 200
    assert resumed.json()["priority"] == "alta"
    assert len(client.get(f"/api/v1/tickets/{identifier}").json()["intervals"]) == 2


def test_idempotency_revision_conflict_and_derived_draft_preserves_fact(world):
    client_id = prepare(world)
    client = world.client
    key = str(uuid4())
    body = {"client_id": client_id, "type": "chamado", "texto_original": "Reenvio fictício"}
    first = send(client, "/records", body, key)
    second = send(client, "/tickets", body, key)
    assert first.status_code == second.status_code == 201
    assert first.json()["ticket_id"] == second.json()["id"]
    assert send(client, "/records", {**body, "texto_original": "Diferente"}, key).status_code == 409
    item = create(world, client_id, ocorrido_em="2026-11-14T10:24:00-03:00")
    edited = mutate(
        client,
        f"/records/{item['id']}",
        {"revision": 1, "texto_organizado": "Edição humana"},
        "PATCH",
    )
    assert edited.status_code == 200
    assert (
        mutate(
            client,
            f"/records/{item['id']}",
            {"revision": 1, "texto_organizado": "Conflito"},
            "PATCH",
        ).status_code
        == 409
    )
    confirmed = action(client, edited.json(), "confirmar").json()
    derived = send(
        client,
        f"/records/{item['id']}/derive",
        {
            "revision": confirmed["revision"],
            "type": "conhecimento",
        },
        str(uuid4()),
    )
    assert derived.status_code == 201
    assert derived.json()["status"] == "rascunho"
    assert derived.json()["ocorrido_em"] == confirmed["ocorrido_em"]
    assert derived.json()["origem_record_id"] == item["id"]
    unchanged = client.get(f"/api/v1/records/{item['id']}").json()
    assert {key: value for key, value in unchanged.items() if key != "age_seconds"} == {
        key: value for key, value in confirmed.items() if key != "age_seconds"
    }
    submitted = action(client, derived.json(), "enviar")
    assert submitted.status_code == 200 and submitted.json()["article_status"] == "rascunho"
    assert action(client, submitted.json(), "publicar").status_code == 409
    assert action(client, submitted.json(), "confirmar").status_code == 409
    returned = action(client, submitted.json(), "devolver")
    assert returned.status_code == 200 and returned.json()["status"] == "rascunho"


def test_cross_organization_records_tickets_notifications_and_rls(world):
    client_id = prepare(world)
    client = world.client
    record = create(world, client_id)
    ticket_record = create(world, client_id, "chamado", assignee_id=world.technician_id)
    with Session(world.admin_engine) as db:
        notification = db.scalar(
            select(Notification).where(
                Notification.organization_id == world.a, Notification.user_id == world.technician_id
            )
        )
        notice_id = notification.id
    assert (
        mutate(client, f"/notifications/{notice_id}/read").status_code == 404
    )  # Mesmo tenant, outro destinatário.
    login(client, world.admin_b, world.password)
    for path in (
        f"/records/{record['id']}",
        f"/records/{record['id']}/versions",
        f"/tickets/{ticket_record['ticket_id']}",
    ):
        assert client.get("/api/v1" + path).status_code == 404
    assert mutate(client, f"/notifications/{notice_id}/read").status_code == 404
    assert (
        send(
            client,
            "/records",
            {"client_id": client_id, "type": "finalizacao", "texto_original": "Tentativa"},
            str(uuid4()),
        ).status_code
        == 404
    )
    with Session(world.runtime_engine) as db:
        set_context(db, world.b, "")
        assert not db.scalars(select(Record).where(Record.id == record["id"])).all()
        assert not db.scalars(select(Ticket).where(Ticket.id == ticket_record["ticket_id"])).all()
        assert not db.scalars(select(Notification).where(Notification.id == notice_id)).all()
        db.commit()
    login(client, world.technician, world.password)
    assert mutate(client, f"/notifications/{notice_id}/read").status_code == 200
    assert (
        client.get(f"/api/v1/records/{record['id']}").status_code == 404
    )  # Provisório de outro autor.


def test_concurrent_record_creation_and_edit_retries(world):
    client_id = prepare(world)
    token = world.client.cookies.get("soldesk_session")
    key = str(uuid4())
    body = {
        "client_id": client_id,
        "type": "finalizacao",
        "texto_original": "Concorrência fictícia",
    }

    def request_once():
        with TestClient(world.app) as client:
            client.cookies.set("soldesk_session", token)
            response = send(client, "/records", body, key)
            assert response.status_code == 201, response.text
            return response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: request_once(), range(2)))
    assert results[0]["id"] == results[1]["id"]
    identifier = results[0]["id"]

    def edit_once(value):
        with TestClient(world.app) as client:
            client.cookies.set("soldesk_session", token)
            return mutate(
                client,
                f"/records/{identifier}",
                {"revision": 1, "texto_organizado": value},
                "PATCH",
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(edit_once, ["Primeira edição", "Segunda edição"])) == [200, 409]


def test_cancel_reason_history_and_no_automatic_confirmation(world):
    client_id = prepare(world)
    item = create(world, client_id)
    assert action(world.client, item, "processar").status_code == 409
    assert action(world.client, item, "cancelar").status_code == 422
    confirmed = action(world.client, item, "confirmar").json()
    cancelled = action(
        world.client, confirmed, "cancelar", reason="Cancelamento fictício justificado"
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelado"
    assert cancelled.json()["revisado_em"] == confirmed["revisado_em"]
    assert world.client.get(f"/api/v1/clients/{client_id}/history").json()["confirmed_total"] == 0
    assert len(world.client.get(f"/api/v1/records/{item['id']}/versions").json()) == 3
