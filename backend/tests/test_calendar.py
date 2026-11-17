import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
import test_attendance as attendance
import test_identity as identity
import test_tasks as tasks
import test_work as work
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.access import Context, set_context
from app.calendar import sources
from app.calendar_models import CalendarEvent, CalendarParticipant, CalendarReceipt, CalendarVersion
from app.models import Organization

pg_settings = identity.pg_settings
world = identity.world


def mutation(client, path, body, key=None, method="POST"):
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return client.request(
        method,
        "/api/v1" + path,
        json=body,
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": key or str(uuid4())},
    )


def create(world, key=None, **values):
    return mutation(
        world.client,
        "/calendar/events",
        {"title": "Evento fictício", "data": "2026-11-18", **values},
        key,
    )


def agenda(world, start="2026-11-01", end="2026-12-01", **params):
    return world.client.get(
        "/api/v1/calendar", params={"date_from": start, "date_until": end, **params}
    )


def ticket(world, client_id, deadline="2026-11-18T09:00:00-03:00"):
    record = work.create(world, client_id, kind="chamado")
    result = identity.mutate(
        world.client,
        f"/tickets/{record['ticket_id']}",
        {"revision": 1, "prazo_em": deadline},
        "PATCH",
    )
    assert result.status_code == 200, result.text
    return result.json()


def service(world):
    response = work.send(
        world.client,
        "/attendances",
        {"internal_activity": True, "texto_original": "Atividade interna fictícia"},
        str(uuid4()),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_unified_sources_are_unique_and_stay_linked(world):
    client = work.prepare(world)
    task = tasks.create(world).json()
    call = ticket(world, client)
    service_item = service(world)
    updated = attendance.update(world, service_item, retomada_em="2030-11-18T12:00:00Z")
    assert updated.status_code == 201, updated.text
    event = create(world).json()
    result = agenda(world)
    assert result.status_code == 200, result.text
    items = result.json()["items"]
    assert {i["id"] for i in items} == {
        "task:" + task["id"],
        "ticket:" + call["id"],
        "event:" + event["id"],
    }
    later = agenda(world, "2030-11-18", "2030-11-19").json()["items"]
    assert len(later) == 1 and later[0]["origin_id"] == service_item["id"]
    assert later[0]["type"] == "attendance"
    edited = tasks.action(world, task, "editar", title="Retorno alterado fictício").json()
    projected = next(i for i in agenda(world).json()["items"] if i["type"] == "task")
    assert projected["title"] == edited["title"] and projected["revision"] == 2
    with Session(world.admin_engine) as db:
        assert (
            db.scalar(
                select(text("count(*)"))
                .select_from(CalendarEvent)
                .where(CalendarEvent.organization_id == world.a)
            )
            == 1
        )


def test_event_edit_cancel_versions_and_replay(world):
    work.prepare(world)
    key = str(uuid4())
    result = create(world, key=key)
    assert result.status_code == 201, result.text
    item = result.json()
    assert create(world, key=key).json() == item
    assert create(world, key=key, title="Diferente").status_code == 409
    body = {"revision": 1, "title": "Treinamento fictício", "data": "2026-12-01"}
    key = str(uuid4())
    edited = mutation(world.client, f"/calendar/events/{item['id']}", body, key, "PUT")
    assert edited.status_code == 200, edited.text
    assert (
        mutation(world.client, f"/calendar/events/{item['id']}", body, key, "PUT").json()
        == edited.json()
    )
    assert agenda(world).json()["total"] == 0
    assert agenda(world, "2026-12-01", "2026-12-02").json()["total"] == 1
    canceled = mutation(
        world.client,
        f"/calendar/events/{item['id']}/cancel",
        {"revision": 2, "reason": "Evento fictício retirado"},
    )
    assert canceled.status_code == 200 and canceled.json()["cancelado_em"]
    assert agenda(world, "2026-12-01", "2026-12-02").json()["total"] == 0
    assert agenda(world, "2026-12-01", "2026-12-02", include_cancelled="true").json()["total"] == 1
    history = world.client.get(f"/api/v1/calendar/events/{item['id']}/history").json()
    assert history["total"] == 3
    assert [e["action"] for e in history["items"]] == ["criado", "editado", "cancelado"]
    assert history["items"][0]["after"]["data"] == "2026-11-18"
    assert (
        mutation(
            world.client, f"/calendar/events/{item['id']}", {**body, "revision": 3}, method="PUT"
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "start,end",
    [("2026-12-31", "2027-01-01"), ("2026-11-30", "2026-12-01"), ("2026-11-22", "2026-11-23")],
)
def test_date_intervals_use_exclusive_end_across_boundaries(world, start, end):
    work.prepare(world)
    item = create(world, data=start).json()
    tasks.create(world, prevista_para=end)
    response = agenda(world, start, end)
    assert response.status_code == 200, response.text
    assert [i["origin_id"] for i in response.json()["items"]] == [item["id"]]


def test_all_day_timed_overlap_offsets_and_validation(world):
    work.prepare(world)
    all_day = create(world, data="2026-11-17").json()
    span = create(
        world, data=None, inicio_em="2026-11-17T23:00:00-03:00", fim_em="2026-11-19T01:00:00-03:00"
    )
    assert span.status_code == 201, span.text
    point = create(world, data=None, inicio_em="2026-11-18T02:30:00Z").json()
    assert len(agenda(world, "2026-11-17", "2026-11-18").json()["items"]) == 3
    assert len(agenda(world, "2026-11-18", "2026-11-19").json()["items"]) == 1
    assert create(world, inicio_em="2026-11-18T12:00:00").status_code == 422
    assert create(world, fim_em="2026-11-18T12:00:00Z").status_code == 422
    assert (
        create(world, inicio_em="2026-11-18T12:00:00Z", fim_em="2026-11-18T11:00:00Z").status_code
        == 422
    )
    assert create(world, data="2026-11-19", inicio_em="2026-11-18T12:00:00Z").status_code == 422
    assert agenda(world, "2026-11-18", "2026-11-18").status_code == 422
    assert agenda(world, "2026-01-01", "2027-01-01").status_code == 422
    with Session(world.admin_engine) as db, db.begin():
        db.get(Organization, world.a).timezone = "Asia/Tokyo"
    assert {i["origin_id"] for i in agenda(world, "2026-11-18", "2026-11-19").json()["items"]} == {
        span.json()["id"],
        point["id"],
    }
    assert (
        agenda(world, "2026-11-17", "2026-11-18").json()["items"][0]["origin_id"] == all_day["id"]
    )


def test_participants_read_only_and_removal_revokes_access(world):
    work.prepare(world)
    item = create(world, participant_ids=[world.technician_id, world.technician_id]).json()
    identity.login(world.client, world.technician, world.password)
    assert agenda(world).json()["total"] == 1

    assert world.client.get(f"/api/v1/calendar/events/{item['id']}").status_code == 200
    assert (
        mutation(
            world.client,
            f"/calendar/events/{item['id']}/cancel",
            {"revision": 1, "reason": "Teste"},
        ).status_code
        == 403
    )
    identity.login(world.client, world.admin_a, world.password)
    result = mutation(
        world.client,
        f"/calendar/events/{item['id']}",
        {"title": item["title"], "data": item["data"], "revision": 1},
        method="PUT",
    )
    assert result.status_code == 200, result.text
    identity.login(world.client, world.technician, world.password)
    assert agenda(world).json()["total"] == 0
    assert world.client.get(f"/api/v1/calendar/events/{item['id']}/history").status_code == 404


def test_team_filter_and_linked_task_remain_distinct_facts(world):
    client = work.prepare(world)
    call = ticket(world, client)
    group = tasks.team(world, [world.technician_id])
    task = tasks.create(world, ticket_id=call["id"], team_id=group["id"]).json()
    result = agenda(world).json()
    assert result["total"] == 2
    assert len({i["id"] for i in result["items"]}) == 2
    assert agenda(world, team_id=group["id"]).json()["total"] == 1
    identity.login(world.client, world.technician, world.password)
    assert [i["origin_id"] for i in agenda(world).json()["items"]] == [task["id"]]
    assert agenda(world, assignee_id=world.technician_id).json()["total"] == 0


def test_thousands_of_items_pagination_and_real_explain(world):
    client_id = work.prepare(world)
    user_id = world.client.get("/api/v1/me").json()["id"]
    with world.admin_engine.begin() as db:
        db.execute(
            text("""INSERT INTO task
          (id,organization_id,author_id,assignee_id,title,prevista_para,agendado_em,
           criado_em,atualizado_em)
          SELECT gen_random_uuid()::text,:org,:user,:user,'Tarefa fictícia de volume',
            date '2030-01-01'+(g%1000),
            CASE WHEN g%2=0 THEN timestamptz '2030-01-01 12:00Z'+(g%1000)*interval '1 day' END,
            now(),now() FROM generate_series(1,4000) g"""),
            {"org": world.a, "user": user_id},
        )
        db.execute(
            text("""INSERT INTO calendar_event
          (id,organization_id,author_id,assignee_id,title,data,inicio_em,fim_em,
           criado_em,atualizado_em)
          SELECT gen_random_uuid()::text,:org,:user,:user,'Evento fictício de volume',
            date '2030-01-01'+(g%1000),
            CASE WHEN g%2=0 THEN timestamptz '2030-01-01 12:00Z'+(g%1000)*interval '1 day' END,
            CASE WHEN g%2=0 THEN timestamptz '2030-01-01 13:00Z'+(g%1000)*interval '1 day' END,
            now(),now() FROM generate_series(1,2000) g"""),
            {"org": world.a, "user": user_id},
        )
        for kind, internal, category in (
            ("chamado", False, "volume-chamado"),
            ("finalizacao", True, "volume-retomada"),
        ):
            db.execute(
                text("""INSERT INTO record
              (id,organization_id,client_id,author_id,type,texto_original,status,revision,
               ocorrido_em,enviado_em,category,system,internal_activity)
              SELECT gen_random_uuid()::text,:org,:client,:user,:kind,'Relato fictício de volume',
                'aguardando_revisao',1,now(),now(),:category,'',:internal
              FROM generate_series(1,1000) g"""),
                {
                    "org": world.a,
                    "client": None if internal else client_id,
                    "user": user_id,
                    "kind": kind,
                    "category": category,
                    "internal": internal,
                },
            )
        db.execute(
            text("""INSERT INTO ticket
          (id,organization_id,record_id,client_id,code,description,opened_by,assignee_id,
           priority,category,system,status,revision,reopen_count,aberto_em,prazo_em)
          SELECT gen_random_uuid()::text,organization_id,id,client_id,
            'VOL-'||row_number() OVER(ORDER BY id),'Chamado fictício de volume',author_id,author_id,
            'normal','','','aberto',1,0,now(),timestamptz '2030-01-01 12:00Z'+
            ((row_number() OVER(ORDER BY id))%1000)*interval '1 day'
          FROM record WHERE organization_id=:org AND category='volume-chamado'"""),
            {"org": world.a},
        )
        db.execute(
            text("""INSERT INTO attendance
          (id,organization_id,assignee_id,status,retomada_em)
          SELECT id,organization_id,author_id,'aguardando_retomada',
            timestamptz '2030-01-01 12:00Z'+
            ((row_number() OVER(ORDER BY id))%1000)*interval '1 day'
          FROM record WHERE organization_id=:org AND category='volume-retomada'"""),
            {"org": world.a},
        )
        for table in ("task", "calendar_event", "ticket", "attendance", "record"):
            db.execute(text(f"ANALYZE {table}"))
    first = agenda(world, "2030-01-02", "2030-01-04", limit=5).json()
    second = agenda(world, "2030-01-02", "2030-01-04", limit=5, offset=5).json()
    assert first["total"] == second["total"] == 16
    assert not {i["id"] for i in first["items"]} & {i["id"] for i in second["items"]}
    all_rows = agenda(world, "2030-01-02", "2030-01-04", limit=100).json()["items"]
    assert len({i["id"] for i in all_rows}) == 16
    plans = {}
    with Session(world.runtime_engine) as db, db.begin():
        set_context(db, world.a, user_id)
        ctx = Context(
            db=db,
            user=SimpleNamespace(id=user_id),
            session=SimpleNamespace(organization_id=world.a),
            membership=SimpleNamespace(role="administrador"),
        )
        for kind, query in sources(ctx, date(2030, 1, 2), date(2030, 1, 4)).items():
            sql = str(
                query.compile(dialect=db.bind.dialect, compile_kwargs={"literal_binds": True})
            )
            plan = db.scalar(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql))[0]

            def nodes(node):
                return [
                    {
                        "node": node["Node Type"],
                        "index": node.get("Index Name"),
                        "rows": node["Actual Rows"],
                    }
                ] + [child for sub in node.get("Plans", []) for child in nodes(sub)]

            plans[kind] = {"execution_ms": plan["Execution Time"], "nodes": nodes(plan["Plan"])}
        assert plans["task"]["nodes"][0]["rows"] == 8
        assert plans["event"]["nodes"][0]["rows"] == 4
        assert plans["ticket"]["nodes"][0]["rows"] == 2
        assert plans["attendance"]["nodes"][0]["rows"] == 2
    print("EXPLAIN_CALENDARIO=" + json.dumps(plans, ensure_ascii=False))


def test_each_source_permission_and_tenant_is_applied_before_projection(world):
    client = work.prepare(world)
    tasks.create(world)
    ticket(world, client)
    service_item = service(world)
    attendance.update(world, service_item, retomada_em="2030-11-18T12:00:00Z")
    item = create(world, client_id=client).json()
    identity.login(world.client, world.technician, world.password)
    assert agenda(world).json() == {
        "total": 0,
        "timezone": "America/Sao_Paulo",
        "date_from": "2026-11-01",
        "date_until": "2026-12-01",
        "items": [],
    }
    assert agenda(world, "2030-11-01", "2030-12-01").json()["total"] == 0
    identity.login(world.client, world.admin_b, world.password)
    assert agenda(world).json()["items"] == []
    assert world.client.get(f"/api/v1/calendar/events/{item['id']}").status_code == 404
    assert create(world, client_id=client).status_code == 404
    assert create(world, participant_ids=[world.technician_id]).status_code == 404
    assert create(world, organization_id=world.a).status_code == 422
    own = create(world).json()
    with Session(world.runtime_engine) as db, db.begin():
        set_context(db, world.b)
        assert [e.id for e in db.scalars(select(CalendarEvent))] == [own["id"]]
        assert len(list(db.scalars(select(CalendarVersion)))) == 1
        assert len(list(db.scalars(select(CalendarReceipt)))) == 1
    with pytest.raises(DBAPIError), Session(world.runtime_engine) as db, db.begin():
        set_context(db, world.b)
        db.add(
            CalendarParticipant(
                organization_id=world.b, event_id=own["id"], user_id=world.technician_id
            )
        )
        db.flush()
    for table in ("calendar_version", "calendar_receipt"):
        with pytest.raises(DBAPIError), Session(world.admin_engine) as db, db.begin():
            db.execute(text(f"DELETE FROM {table} WHERE event_id=:id"), {"id": own["id"]})


def test_ticket_deadline_is_optional_versioned_and_cleared(world):
    client = work.prepare(world)
    call = ticket(world, client)
    assert call["prazo_em"] == "2026-11-18T12:00:00+00:00"
    cleared = identity.mutate(
        world.client,
        f"/tickets/{call['id']}",
        {"revision": call["revision"], "prazo_em": None},
        "PATCH",
    )
    assert cleared.status_code == 200 and cleared.json()["prazo_em"] is None
    assert agenda(world).json()["total"] == 0
    assert (
        identity.mutate(
            world.client,
            f"/tickets/{call['id']}",
            {"revision": cleared.json()["revision"], "prazo_em": "2026-11-18T12:00:00"},
            "PATCH",
        ).status_code
        == 422
    )


def test_concurrent_identical_create_and_edits(world):
    work.prepare(world)
    barrier, key = Barrier(2), str(uuid4())

    def run(_):
        with TestClient(world.app, client=(uuid4().hex, 1234)) as client:
            identity.login(client, world.admin_a, world.password)
            barrier.wait(timeout=10)
            return mutation(
                client,
                "/calendar/events",
                {"title": "Concorrência fictícia", "data": "2026-11-18"},
                key,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(run, [0, 1]))
    assert all(r.status_code == 201 for r in responses)
    item = responses[0].json()
    assert responses[1].json() == item
    barrier = Barrier(2)

    def edit(index):
        with TestClient(world.app, client=(uuid4().hex, 1234)) as client:
            identity.login(client, world.admin_a, world.password)
            barrier.wait(timeout=10)
            return mutation(
                client,
                f"/calendar/events/{item['id']}",
                {"revision": 1, "title": f"Nome {index}", "data": item["data"]},
                method="PUT",
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(edit, [0, 1])) == [200, 409]
    assert agenda(world).json()["total"] == 1
