from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

import pytest
import test_attendance as attendance
import test_identity as identity
import test_work as work
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app import task_routes
from app.access import set_context
from app.models import Organization
from app.task_models import Task, TaskEvent, TaskReceipt

pg_settings = identity.pg_settings
world = identity.world


def create(world, key=None, **values):
    return work.send(
        world.client,
        "/tasks",
        {"title": "Retorno fictício", "prevista_para": "2026-11-18", **values},
        key or str(uuid4()),
    )


def action(world, item, name, key=None, **values):
    return work.send(
        world.client,
        f"/tasks/{item['id']}/actions",
        {"revision": item["revision"], "action": name, **values},
        key or str(uuid4()),
    )


def team(world, members):
    response = identity.mutate(
        world.client, "/teams", {"name": "Equipe fictícia", "member_ids": members}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_dates_assignment_and_validation(world):
    client = work.prepare(world)
    item = create(world)
    assert item.status_code == 201, item.text
    assert item.json()["dia_inteiro"] and item.json()["client_id"] is None
    assert item.json()["assignee_id"] == world.client.get("/api/v1/me").json()["id"]
    scheduled = create(world, client_id=client, agendado_em="2026-11-18T09:00:00-03:00")
    assert scheduled.status_code == 201, scheduled.text
    assert scheduled.json()["agendado_em"] == "2026-11-18T12:00:00+00:00"
    assert not scheduled.json()["dia_inteiro"]
    assert create(world, agendado_em="2026-11-18T09:00:00").status_code == 422
    assert create(world, agendado_em="2026-11-19T09:00:00Z").status_code == 422
    assert create(world, prevista_para=None).status_code == 422
    assert create(world, title="   ").status_code == 422
    assert create(world, organization_id=world.b).status_code == 422
    assert create(world, assignee_id=world.technician_id, team_id=str(uuid4())).status_code == 422


def test_lifecycle_transfer_history_and_single_request_completion(world):
    work.prepare(world)
    item = create(world).json()
    item = action(world, item, "iniciar").json()
    assert item["status"] == "em_andamento"
    moved = action(world, item, "transferir", assignee_id=world.technician_id)
    assert moved.status_code == 200, moved.text
    item = moved.json()
    identity.login(world.client, world.technician, world.password)
    complete = action(world, item, "concluir")
    assert complete.status_code == 200, complete.text
    assert complete.json()["status"] == "concluida" and complete.json()["concluido_em"]
    assert action(world, complete.json(), "iniciar").status_code == 409
    events = world.client.get(f"/api/v1/tasks/{item['id']}/history").json()
    assert events["total"] == 4
    assert [e["action"] for e in events["items"]] == ["criada", "iniciar", "transferir", "concluir"]
    assert events["items"][2]["before"]["assignee_id"] != world.technician_id
    assert events["items"][2]["after"]["assignee_id"] == world.technician_id
    assert len({e["actor_id"] for e in events["items"]}) == 2
    assert (
        world.client.get(f"/api/v1/tasks/{item['id']}/history?limit=1&offset=1").json()["total"]
        == 4
    )


def test_cancel_requires_reason_and_edits_preserve_versions(world):
    work.prepare(world)
    item = create(world).json()
    assert action(world, item, "cancelar").status_code == 422
    updated = action(
        world,
        item,
        "editar",
        title="Treinamento fictício",
        priority="alta",
        agendado_em="2026-11-19T15:00:00-03:00",
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["prevista_para"] == "2026-11-19"
    assert action(world, item, "concluir").status_code == 409
    updated = action(world, updated.json(), "editar", agendado_em=None).json()
    assert updated["dia_inteiro"]
    result = action(world, updated, "cancelar", reason="Solicitação fictícia retirada")
    assert result.status_code == 200 and result.json()["cancelado_em"]
    history = world.client.get(f"/api/v1/tasks/{item['id']}/history").json()["items"]
    assert history[0]["after"]["title"] == "Retorno fictício"
    assert history[-1]["reason"] == "Solicitação fictícia retirada"
    assert action(world, result.json(), "concluir").status_code == 409


def test_team_scope_claim_and_responsibility(world):
    work.prepare(world)
    group = team(world, [world.technician_id])
    item = create(world, team_id=group["id"]).json()
    private = create(world).json()
    identity.login(world.client, world.technician, world.password)
    assert world.client.get(f"/api/v1/tasks/{private['id']}").status_code == 404
    assert world.client.get("/api/v1/tasks").json()["total"] == 1
    assert action(world, item, "concluir").status_code == 403
    assert world.client.get("/api/v1/tasks/options").json()["teams"][0]["id"] == group["id"]
    owned = action(world, item, "assumir")
    assert owned.status_code == 200, owned.text
    assert owned.json()["assignee_id"] == world.technician_id and owned.json()["team_id"] is None
    assert world.client.get("/api/v1/tasks?mine=true").json()["total"] == 1
    assert action(world, owned.json(), "concluir").status_code == 200


def test_creator_keeps_read_only_after_transfer(world):
    work.prepare(world)
    manager_id = world.client.get("/api/v1/me").json()["id"]
    identity.login(world.client, world.technician, world.password)
    item = create(world).json()
    moved = action(world, item, "transferir", assignee_id=manager_id).json()
    assert world.client.get(f"/api/v1/tasks/{item['id']}").status_code == 200
    assert action(world, moved, "concluir").status_code == 403


def test_two_organizations_rls_foreign_ids_and_immutable_history(world):
    client = work.prepare(world)
    item = create(world, client_id=client).json()
    identity.login(world.client, world.admin_b, world.password)
    assert world.client.get(f"/api/v1/tasks/{item['id']}").status_code == 404
    assert world.client.get(f"/api/v1/tasks/{item['id']}/history").status_code == 404
    assert action(world, item, "concluir").status_code == 404
    assert create(world, client_id=client).status_code == 404
    assert create(world, assignee_id=world.technician_id).status_code == 404
    other = create(world).json()
    with Session(world.runtime_engine) as db, db.begin():
        set_context(db, world.b)
        assert [t.id for t in db.scalars(select(Task))] == [other["id"]]
        assert len(list(db.scalars(select(TaskEvent)))) == 1
        assert len(list(db.scalars(select(TaskReceipt)))) == 1
    with pytest.raises(DBAPIError), Session(world.runtime_engine) as db, db.begin():
        set_context(db, world.b)
        db.execute(
            text("UPDATE task SET client_id=:id WHERE id=:task"),
            {"id": client, "task": other["id"]},
        )
    for table in ("task_event", "task_receipt"):
        with pytest.raises(DBAPIError), Session(world.admin_engine) as db, db.begin():
            db.execute(text(f"DELETE FROM {table} WHERE task_id=:id"), {"id": other["id"]})


def test_idempotent_create_and_actions_have_single_history(world):
    work.prepare(world)
    key = str(uuid4())
    item = create(world, key=key)
    assert create(world, key=key).json() == item.json()
    assert create(world, key=key, title="Outra fictícia").status_code == 409
    key = str(uuid4())
    done = action(world, item.json(), "concluir", key=key)
    assert action(world, item.json(), "concluir", key=key).json() == done.json()
    assert action(world, item.json(), "cancelar", key=key, reason="Teste").status_code == 409
    assert world.client.get(f"/api/v1/tasks/{item.json()['id']}/history").json()["total"] == 2


def test_timezone_midnight_and_date_filters(world, monkeypatch):
    work.prepare(world)
    instant = datetime(2026, 11, 18, 1, tzinfo=UTC)  # Ainda dia 17 em São Paulo.
    monkeypatch.setattr(task_routes, "now", lambda: instant)
    today = create(world, prevista_para="2026-11-17").json()
    overdue = create(world, prevista_para="2026-11-16", priority="alta").json()
    timed = create(world, prevista_para=None, agendado_em="2026-11-18T00:30:00Z").json()
    future = create(world).json()
    assert today["periodo"] == "hoje" and not today["atrasada"]
    assert timed["data_local"] == "2026-11-17" and timed["atrasada"]
    assert overdue["atrasada"] and future["periodo"] == "futura"
    for period, count in (("hoje", 2), ("atrasadas", 2), ("futuras", 1)):
        assert world.client.get(f"/api/v1/tasks?period={period}").json()["total"] == count
    assert world.client.get("/api/v1/tasks?priority=alta").json()["total"] == 1
    assert (
        world.client.get("/api/v1/tasks?date_from=2026-11-18&date_until=2026-11-18").json()["total"]
        == 1
    )
    assert world.client.get("/api/v1/tasks?limit=1&offset=1").json()["total"] == 4
    with Session(world.admin_engine) as db, db.begin():
        db.get(Organization, world.a).timezone = "Asia/Tokyo"
    assert world.client.get(f"/api/v1/tasks/{today['id']}").json()["data_local"] == "2026-11-17"
    assert world.client.get(f"/api/v1/tasks/{timed['id']}").json()["data_local"] == "2026-11-18"


@pytest.mark.parametrize(
    "shortcut,day", [("hoje", "17"), ("amanha", "18"), ("proxima_semana", "24")]
)
def test_quick_return_from_attendance_has_no_side_effects(world, monkeypatch, shortcut, day):
    source = attendance.opened(world)
    monkeypatch.setattr(task_routes, "now", lambda: datetime(2026, 11, 18, 1, tzinfo=UTC))
    body = {"attendance_id": source["id"], "shortcut": shortcut, "horario": "09:30:00"}
    key = str(uuid4())
    result = work.send(world.client, "/tasks/quick", body, key)
    assert result.status_code == 201, result.text
    assert result.json()["prevista_para"] == "2026-11-" + day
    assert result.json()["agendado_em"] == f"2026-11-{day}T12:30:00+00:00"
    assert result.json()["client_id"] is None
    assert work.send(world.client, "/tasks/quick", body, key).json() == result.json()
    assert (
        world.client.get(f"/api/v1/attendances/{source['id']}").json()["revision"]
        == source["revision"]
    )
    action(world, result.json(), "concluir")
    assert (
        world.client.get(f"/api/v1/attendances/{source['id']}").json()["status"] == "em_andamento"
    )


def test_quick_ticket_inherits_context_and_checks_access(world):
    client = work.prepare(world)
    system = identity.mutate(world.client, "/systems", {"name": "ERP fictício"}).json()
    record = work.create(world, client, kind="chamado", system_id=system["id"])
    body = {"ticket_id": record["ticket_id"], "shortcut": "amanha"}
    result = work.send(world.client, "/tasks/quick", body, str(uuid4()))
    assert result.status_code == 201, result.text
    assert result.json()["client_id"] == client and result.json()["system_id"] == system["id"]
    assert result.json()["dia_inteiro"]
    assert create(world, ticket_id=record["ticket_id"], client_id=str(uuid4())).status_code == 422
    identity.login(world.client, world.technician, world.password)
    assert work.send(world.client, "/tasks/quick", body, str(uuid4())).status_code == 404


@pytest.mark.parametrize("action_name", ["assumir", "concluir"])
def test_concurrent_claim_or_completion_has_one_conflict(world, action_name):
    work.prepare(world)
    admin_id = world.client.get("/api/v1/me").json()["id"]
    group = team(world, [admin_id, world.technician_id])
    item = create(
        world,
        **(
            {"team_id": group["id"]}
            if action_name == "assumir"
            else {"assignee_id": world.technician_id}
        ),
    ).json()
    barrier = Barrier(2)

    def run(email):
        with TestClient(world.app, client=(uuid4().hex, 1234)) as client:
            identity.login(client, email, world.password)
            barrier.wait(timeout=10)
            return work.send(
                client,
                f"/tasks/{item['id']}/actions",
                {"revision": 1, "action": action_name},
                str(uuid4()),
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(run, [world.admin_a, world.technician]))
    # Quem perde a equipe após outro assumir deixa de enxergar a tarefa (404).
    # Se ainda puder consultá-la, recebe conflito de revisão (409).
    assert results in ([200, 409], [200, 404])
    history = world.client.get(f"/api/v1/tasks/{item['id']}/history").json()
    assert history["total"] == 2
    assert history["items"][-1]["revision"] == 2


def test_concurrent_same_key_creates_once(world):
    work.prepare(world)
    barrier, key = Barrier(2), str(uuid4())

    def run(_):
        with TestClient(world.app, client=(uuid4().hex, 1234)) as client:
            identity.login(client, world.admin_a, world.password)
            barrier.wait(timeout=10)
            response = work.send(
                client, "/tasks", {"title": "Ação fictícia", "prevista_para": "2026-11-18"}, key
            )
            assert response.status_code == 201, response.text
            return response.json()["id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert len(set(pool.map(run, [0, 1]))) == 1
    assert world.client.get("/api/v1/tasks").json()["total"] == 1


@pytest.mark.parametrize(
    "stamp,clock", [("2026-03-08T12:00:00Z", "02:30:00"), ("2026-11-01T12:00:00Z", "01:30:00")]
)
def test_quick_rejects_nonexistent_or_ambiguous_local_time(world, monkeypatch, stamp, clock):
    source = attendance.opened(world)
    with Session(world.admin_engine) as db, db.begin():
        db.get(Organization, world.a).timezone = "America/New_York"
    monkeypatch.setattr(task_routes, "now", lambda: datetime.fromisoformat(stamp))
    result = work.send(
        world.client,
        "/tasks/quick",
        {"attendance_id": source["id"], "shortcut": "hoje", "horario": clock},
        str(uuid4()),
    )
    assert result.status_code == 422, result.text
    assert result.headers["content-type"] == "application/problem+json"
    assert world.client.get("/api/v1/tasks").json()["total"] == 0


def test_team_assignment_requires_membership_and_active_assignee(world):
    from app.models import OrganizationMembership

    work.prepare(world)
    group = team(world, [])
    identity.login(world.client, world.technician, world.password)
    assert create(world, team_id=group["id"]).status_code == 403
    identity.login(world.client, world.admin_a, world.password)
    with Session(world.admin_engine) as db, db.begin():
        db.get(OrganizationMembership, world.membership).situation = "inativo"
    assert create(world, assignee_id=world.technician_id).status_code == 404


def test_manager_can_operate_and_technician_cannot_read_unrelated_team(world):
    from app.models import OrganizationMembership

    work.prepare(world)
    group = team(world, [])
    item = create(world, team_id=group["id"]).json()
    identity.login(world.client, world.technician, world.password)
    assert world.client.get(f"/api/v1/tasks/{item['id']}").status_code == 404
    with Session(world.admin_engine) as db, db.begin():
        db.get(OrganizationMembership, world.membership).role = "gestor"
    assert world.client.get(f"/api/v1/tasks/{item['id']}").status_code == 200
    assert action(world, item, "concluir").status_code == 200


def test_system_inactivation_new_selection_and_historical_quick_link(world):
    source = attendance.opened(world)
    system = identity.mutate(world.client, "/systems", {"name": "Sistema fictício"}).json()
    # Reconciliação explícita apenas acrescenta contexto ao atendimento salvo.
    decision = work.send(
        world.client,
        "/systems/reconciliation",
        {
            "kind": "record",
            "entity_id": source["id"],
            "revision": 1,
            "legacy_text": "",
            "decision": "aceitar",
            "system_id": system["id"],
            "reviewed": True,
        },
        str(uuid4()),
    )
    assert decision.status_code == 200, decision.text
    changed = identity.mutate(
        world.client,
        f"/systems/{system['id']}",
        {"revision": 1, "name": system["name"], "situation": "inativo"},
        "PATCH",
    )
    assert changed.status_code == 200
    assert create(world, system_id=system["id"]).status_code == 422
    result = work.send(world.client, "/tasks/quick", {"attendance_id": source["id"]}, str(uuid4()))
    assert result.status_code == 201 and result.json()["system_id"] == system["id"]
    identity.login(world.client, world.admin_b, world.password)
    assert create(world, system_id=system["id"]).status_code == 404
