from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
import test_identity as identity
import test_work as work
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app import ticket_workflow
from app.models import Organization
from app.work_models import Ticket

pg_settings = identity.pg_settings
world = identity.world


def opened(world, assigned=True):
    client = work.prepare(world)
    record = work.create(
        world, client, "chamado", **({"assignee_id": world.technician_id} if assigned else {})
    )
    return world.client.get(f"/api/v1/tickets/{record['ticket_id']}").json()


def action(client, item, name, key=None, **fields):
    return work.send(
        client,
        f"/tickets/{item['id']}/actions",
        {"revision": item["revision"], "action": name, **fields},
        key or str(uuid4()),
    )


def test_completion_accept_return_history_and_idempotence(world):
    item = opened(world)
    identity.login(world.client, world.technician, world.password)
    assert action(world.client, item, "concluir").status_code == 422
    key = str(uuid4())
    done = action(world.client, item, "concluir", key=key, description="Ação fictícia executada")
    assert done.status_code == 200, done.text
    assert done.json()["workflow_state"] == "aguardando_validacao"
    assert (
        action(
            world.client, item, "concluir", key=key, description="Ação fictícia executada"
        ).json()
        == done.json()
    )
    assert action(world.client, done.json(), "aceitar").status_code == 403
    identity.login(world.client, world.admin_a, world.password)
    assert action(world.client, done.json(), "devolver").status_code == 422
    returned = action(world.client, done.json(), "devolver", reason="Persistiu o aviso fictício")
    assert returned.status_code == 200 and returned.json()["workflow_state"] == "em_andamento"
    identity.login(world.client, world.technician, world.password)
    done = action(
        world.client, returned.json(), "concluir", description="Nova ação fictícia executada"
    ).json()
    identity.login(world.client, world.admin_a, world.password)
    accepted = action(world.client, done, "aceitar")
    assert accepted.status_code == 200 and accepted.json()["workflow_state"] == "concluido"
    detail = world.client.get(f"/api/v1/tickets/{item['id']}").json()
    assert len(detail["events"]) >= 5
    assert detail["aberto_em"] == item["aberto_em"]
    assert any(e["before"].get("reason") == "Persistiu o aviso fictício" for e in detail["events"])
    assert world.client.get("/api/v1/notifications").json()["items"]


def test_self_accept_default_config_and_management_reopen(world):
    item = opened(world, assigned=False)
    result = action(world.client, item, "concluir", description="Ação interna fictícia executada")
    assert result.status_code == 200, result.text
    assert result.json()["workflow_state"] == "concluido" and result.json()["auto_accept"]
    reopened = action(world.client, result.json(), "reabrir", reason="Gestão solicita nova análise")
    assert reopened.status_code == 200 and not reopened.json()["auto_accept"]
    with Session(world.admin_engine) as db, db.begin():
        org = db.get(Organization, world.a)
        org.settings = {**org.settings, "ticket_self_accept": False}
    pending = action(world.client, reopened.json(), "concluir", description="Outra ação fictícia")
    assert pending.status_code == 200 and pending.json()["workflow_state"] == "aguardando_validacao"
    assert not pending.json()["auto_accept"]


@pytest.mark.parametrize("hours", [24, 48, 72])
def test_stale_boundary_running_hours_waiting_excluded_and_due(world, monkeypatch, hours):
    item = opened(world)
    instant = datetime(2030, 1, 10, 12, tzinfo=UTC)
    monkeypatch.setattr(ticket_workflow, "now", lambda: instant)
    with Session(world.admin_engine) as db, db.begin():
        row = db.get(Ticket, item["id"])
        row.ultima_interacao_em = instant - timedelta(hours=hours)
        row.prazo_em = instant - timedelta(seconds=1)
    response = world.client.get(f"/api/v1/ticket-monitoring?stale_hours={hours}&overdue=true")
    assert response.status_code == 200 and response.json()["total"] == 1
    with Session(world.admin_engine) as db, db.begin():
        db.get(Ticket, item["id"]).ultima_interacao_em += timedelta(microseconds=1)
    assert world.client.get(f"/api/v1/ticket-monitoring?stale_hours={hours}").json()["total"] == 0
    waiting = action(world.client, item, "aguardar_retorno")
    assert waiting.status_code == 200, waiting.text
    rows = world.client.get("/api/v1/ticket-monitoring").json()["items"]
    assert rows[0]["aguardando_desde_em"] and rows[0]["sem_atualizacao_horas"] is None
    assert world.client.get("/api/v1/ticket-monitoring?stale_hours=24").json()["total"] == 0
    with Session(world.admin_engine) as db, db.begin():
        db.get(Ticket, item["id"]).prazo_em = instant + timedelta(hours=2)
    assert (
        world.client.get("/api/v1/ticket-monitoring?due_soon=true&due_within_hours=2").json()[
            "total"
        ]
        == 1
    )
    assert (
        world.client.get("/api/v1/ticket-monitoring?due_soon=true&due_within_hours=1").json()[
            "total"
        ]
        == 0
    )


def test_two_tenants_permissions_and_cancellation(world):
    item = opened(world)
    identity.login(world.client, world.admin_b, world.password)
    assert action(world.client, item, "concluir", description="Sem acesso").status_code == 404
    assert world.client.get("/api/v1/ticket-monitoring").json()["total"] == 0
    identity.login(world.client, world.admin_a, world.password)
    canceled = action(world.client, item, "cancelar", reason="Pedido fictício retirado")
    assert canceled.status_code == 200 and canceled.json()["workflow_state"] == "cancelado"
    assert action(world.client, canceled.json(), "iniciar").status_code == 409
    with pytest.raises(DBAPIError), Session(world.admin_engine) as db, db.begin():
        db.execute(text("DELETE FROM ticket_receipt WHERE ticket_id=:id"), {"id": item["id"]})


def test_accept_return_concurrently_only_one_wins(world):
    item = opened(world)
    identity.login(world.client, world.technician, world.password)
    done = action(world.client, item, "concluir", description="Ação fictícia executada").json()
    barrier = Barrier(2)

    def run(name):
        with TestClient(world.app, client=(uuid4().hex, 1234)) as client:
            identity.login(client, world.admin_a, world.password)
            barrier.wait(timeout=10)
            return action(client, done, name, reason="Resultado fictício conferido").status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, ["aceitar", "devolver"])) == [200, 409]
