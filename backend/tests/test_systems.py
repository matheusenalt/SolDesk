from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
import test_identity as identity
import test_work as work
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.access import set_context
from app.system_models import ClientSystem, SoftwareSystem, SystemReconciliation
from app.work_models import Record

pg_settings = identity.pg_settings
world = identity.world


def create(world, name="Gestão Fictícia", **fields):
    result = identity.mutate(world.client, "/systems", {"name": name, **fields})
    assert result.status_code == 201, result.text
    return result.json()


def decide(world, item, system=None, key=None, kind="record", decision="aceitar"):
    return work.send(
        world.client,
        "/systems/reconciliation",
        {
            "kind": kind,
            "entity_id": item["id"],
            "revision": item["revision"],
            "legacy_text": item["system"],
            "system_id": system["id"] if system else None,
            "decision": decision,
            "reviewed": True,
        },
        key or str(uuid4()),
    )


def test_catalog_normalized_uniqueness_search_and_inactivation(world):
    client_id = work.prepare(world)
    item = create(
        world,
        "  Gestão   Fictícia  ",
        description="Sistema inventado",
        manufacturer="Fabricante inventado",
    )
    assert item["name"] == "Gestão Fictícia"
    assert identity.mutate(world.client, "/systems", {"name": "GESTAO FICTICIA"}).status_code == 409
    assert world.client.get("/api/v1/systems?q=gestao%20%20ficticia").json()["total"] == 1
    record = work.create(world, client_id, system_id=item["id"], system="Texto original preservado")
    changed = identity.mutate(
        world.client,
        f"/systems/{item['id']}",
        {
            "revision": item["revision"],
            "name": "Sistema renomeado fictício",
            "situation": "inativo",
        },
        "PATCH",
    )
    assert changed.status_code == 200, changed.text
    assert world.client.get("/api/v1/systems").json()["items"] == []
    assert world.client.get("/api/v1/systems?include_inactive=true").json()["total"] == 1
    fresh = world.client.get(f"/api/v1/records/{record['id']}").json()
    assert fresh["system_name_snapshot"] == "Gestão Fictícia"
    assert fresh["legacy_system_snapshot"] == fresh["system"] == "Texto original preservado"
    assert (
        work.send(
            world.client,
            "/records",
            {
                "client_id": client_id,
                "type": "finalizacao",
                "texto_original": "Relato fictício",
                "system_id": item["id"],
            },
            str(uuid4()),
        ).status_code
        == 422
    )
    assert (
        identity.mutate(
            world.client,
            f"/records/{record['id']}",
            {
                "revision": record["revision"],
                "texto_organizado": "Correção fictícia",
                "system_id": item["id"],
            },
            "PATCH",
        ).status_code
        == 200
    )
    with Session(world.admin_engine) as db, db.begin():
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text("DELETE FROM software_system WHERE id=:id"), {"id": item["id"]})


def test_client_many_to_many_versions_and_permissions(world):
    client_id = work.prepare(world)
    other = identity.mutate(world.client, "/clients", {"name": "Segundo cliente fictício"}).json()[
        "id"
    ]
    assert world.client.get(f"/api/v1/clients/{client_id}/systems").json()["total"] == 0
    item = create(world)
    another = create(world, "Outro sistema fictício")
    path = f"/clients/{client_id}/systems/{item['id']}"
    result = identity.mutate(
        world.client, path, {"version_in_use": "2.4", "notes": "Uso fictício"}, "PUT"
    )
    assert result.status_code == 200, result.text
    assert (
        identity.mutate(
            world.client, path, {"version_in_use": "2.4", "notes": "Uso fictício"}, "PUT"
        ).json()
        == result.json()
    )
    assert identity.mutate(world.client, path, {"version_in_use": "3"}, "PUT").status_code == 409
    assert (
        identity.mutate(world.client, path, {"version_in_use": "3", "revision": 1}, "PUT").json()[
            "revision"
        ]
        == 2
    )
    assert (
        identity.mutate(
            world.client, f"/clients/{client_id}/systems/{another['id']}", {}, "PUT"
        ).status_code
        == 200
    )
    assert (
        identity.mutate(
            world.client, f"/clients/{other}/systems/{item['id']}", {}, "PUT"
        ).status_code
        == 200
    )
    assert world.client.get(f"/api/v1/systems?client_id={client_id}").json()["total"] == 2
    identity.login(world.client, world.technician, world.password)
    assert world.client.get("/api/v1/systems").status_code == 200
    assert (
        identity.mutate(world.client, "/systems", {"name": "Proibido fictício"}).status_code == 403
    )
    assert identity.mutate(world.client, path, {}, "PUT").status_code == 403
    assert world.client.get("/api/v1/systems/reconciliation/values").status_code == 403


def test_tenant_rls_and_cross_tenant_references(world):
    client_id = work.prepare(world)
    first = create(world)
    identity.mutate(world.client, f"/clients/{client_id}/systems/{first['id']}", {}, "PUT")
    identity.login(world.client, world.admin_b, world.password)
    second = create(world)
    assert world.client.get(f"/api/v1/systems/{first['id']}").status_code == 404
    assert world.client.get("/api/v1/systems").json()["total"] == 1
    assert (
        identity.mutate(
            world.client, f"/clients/{client_id}/systems/{second['id']}", {}, "PUT"
        ).status_code
        == 404
    )
    identity.login(world.client, world.admin_a, world.password)
    assert (
        work.send(
            world.client,
            "/records",
            {
                "client_id": client_id,
                "type": "finalizacao",
                "texto_original": "Fato fictício",
                "system_id": second["id"],
            },
            str(uuid4()),
        ).status_code
        == 404
    )
    with Session(world.runtime_engine) as db, db.begin():
        set_context(db, world.b)
        assert db.scalars(select(SoftwareSystem.id)).all() == [second["id"]]
        assert db.scalars(select(ClientSystem)).all() == []
        with pytest.raises(DBAPIError), db.begin_nested():
            db.add(
                Record(
                    organization_id=world.b,
                    client_id=client_id,
                    author_id=world.technician_id,
                    type="finalizacao",
                    texto_original="Fato fictício",
                    ocorrido_em=identity.now(),
                    system_id=first["id"],
                    system_name_snapshot="Nome fictício",
                    legacy_system_snapshot="",
                )
            )
    with Session(world.admin_engine) as db, db.begin():
        with pytest.raises(DBAPIError), db.begin_nested():
            db.add(
                ClientSystem(organization_id=world.a, client_id=client_id, system_id=second["id"])
            )
            db.flush()
            db.flush()


def test_selection_in_ticket_attendance_knowledge_and_filters(world):
    client_id = work.prepare(world)
    item = create(world, "Ágil ERP Fictício")
    ticket_record = work.create(world, client_id, "chamado", system_id=item["id"])
    ticket = world.client.get(f"/api/v1/tickets/{ticket_record['ticket_id']}").json()
    assert ticket["system_id"] == item["id"]
    assert world.client.get(f"/api/v1/tickets?system_id={item['id']}").json()["total"] == 1
    attendance = work.send(
        world.client,
        "/attendances",
        {
            "client_id": client_id,
            "texto_original": "Fato contínuo fictício",
            "system_id": item["id"],
        },
        str(uuid4()),
    )
    assert attendance.status_code == 201, attendance.text
    assert world.client.get(f"/api/v1/attendances?system_id={item['id']}").json()["total"] == 1
    record = work.create(
        world, client_id, "conhecimento", system_id=item["id"], system="Grafia legada"
    )
    article_id = record["article_id"]
    from app.work_models import KnowledgeArticle

    with Session(world.admin_engine) as db, db.begin():
        article = db.get(KnowledgeArticle, article_id)
        article.status = "publicado"
        article.title = "Procedimento fictício"
        article.publicado_em = identity.now()
    result = world.client.get(f"/api/v1/knowledge/search?system_id={item['id']}&q=agil")
    assert result.status_code == 200, result.text
    assert result.json()["total"] == 1
    assert result.json()["items"][0]["system_name_snapshot"] == item["name"]
    assert world.client.get(f"/api/v1/records?system_id={item['id']}").json()["total"] == 3
    report = world.client.get(f"/api/v1/reports?preset=inicio&system_id={item['id']}")
    assert report.status_code == 200, report.text
    assert report.json()["filters"]["system_id"] == item["id"]


def test_manual_reconciliation_preserves_text_time_and_prior_validation(world):
    import test_content_validation as validation

    client_id = work.prepare(world)
    catalog = create(world, "Gestão Fictícia")
    records = [
        work.create(world, client_id, system=value)
        for value in ("Gestao Ficticia", "GESTÃO FICTÍCIA", "Gestão Fictícia Pro", "")
    ]
    item = records[0]
    assert validation.validate(world.client, item).status_code == 200
    assert work.action(world.client, item, "confirmar").status_code == 200
    item = world.client.get(f"/api/v1/records/{item['id']}").json()
    groups = world.client.get("/api/v1/systems/reconciliation/values").json()
    assert groups["total"] == 4
    matching = next(row for row in groups["items"] if row["legacy_text"] == item["system"])
    assert matching["count"] == 1 and matching["suggestions"][0]["exact_normalized"]
    assert next(row for row in groups["items"] if row["legacy_text"] == "")["suggestions"] == []
    assert all(
        row["system_id"] is None for row in world.client.get("/api/v1/records").json()["items"]
    )
    key = str(uuid4())
    result = decide(world, item, catalog, key)
    assert result.status_code == 200, result.text
    assert decide(world, item, catalog, key).json() == result.json()
    fresh = world.client.get(f"/api/v1/records/{item['id']}").json()
    for field in ("system", "ocorrido_em", "enviado_em", "revisado_em", "status", "texto_original"):
        assert fresh[field] == item[field]
    assert fresh["legacy_system_snapshot"] == item["system"]
    fidelity = validation.current(world.client, item)
    assert fidelity["status"] == "nao_validado" and len(fidelity["validations"]) == 1
    assert decide(world, records[1], None, decision="rejeitar").status_code == 200
    assert world.client.get(f"/api/v1/records/{records[1]['id']}").json()["system_id"] is None
    assert world.client.get(f"/api/v1/records/{records[2]['id']}").json()["system_id"] is None
    with Session(world.admin_engine) as db, db.begin():
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(
                text("DELETE FROM system_reconciliation WHERE entity_id=:id"), {"id": item["id"]}
            )


def test_concurrent_catalog_create_and_link_are_safe(world):
    client_id = work.prepare(world)
    barrier = Barrier(2)

    def run(index):
        with TestClient(world.app, client=(uuid4().hex, 1234)) as client:
            identity.login(client, world.admin_a, world.password)
            barrier.wait(timeout=10)
            response = identity.mutate(
                client, "/systems", {"name": ["Gestão   Fictícia", "GESTAO FICTICIA"][index]}
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, [0, 1])) == [201, 409]
    item = world.client.get("/api/v1/systems").json()["items"][0]
    path = f"/clients/{client_id}/systems/{item['id']}"

    def link(_):
        with TestClient(world.app, client=(uuid4().hex, 1234)) as client:
            identity.login(client, world.admin_a, world.password)
            barrier.wait(timeout=10)
            result = identity.mutate(client, path, {"version_in_use": "1.2"}, "PUT")
            assert result.status_code == 200, result.text
            return result.json()["id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(link, [0, 1]))
    assert ids[0] == ids[1]


def test_concurrent_manual_decision_is_idempotent_and_revision_guarded(world):
    client_id = work.prepare(world)
    item = work.create(world, client_id, system="Sistema fictício sem vínculo")
    catalog = create(world)
    barrier = Barrier(2)
    key = str(uuid4())
    body = {
        "kind": "record",
        "entity_id": item["id"],
        "revision": item["revision"],
        "legacy_text": item["system"],
        "system_id": catalog["id"],
        "decision": "aceitar",
        "reviewed": True,
    }

    def run(_):
        with TestClient(world.app, client=(uuid4().hex, 1234)) as client:
            identity.login(client, world.admin_a, world.password)
            barrier.wait(timeout=10)
            result = work.send(client, "/systems/reconciliation", body, key)
            assert result.status_code == 200, result.text
            return result.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, [0, 1]))
    assert results[0] == results[1]
    with Session(world.admin_engine) as db:
        assert (
            len(
                db.scalars(
                    select(SystemReconciliation).where(SystemReconciliation.entity_id == item["id"])
                ).all()
            )
            == 1
        )
    assert decide(world, item, catalog).status_code == 409


@pytest.mark.parametrize(
    "kind,route", [("chamado", "tickets"), ("conhecimento", "knowledge/articles")]
)
def test_reconciliation_other_entities_preserves_legacy(world, kind, route):
    client_id = work.prepare(world)
    catalog = create(world)
    source = work.create(world, client_id, kind, system="Grafia fictícia original")
    identifier = source["ticket_id"] if kind == "chamado" else source["article_id"]
    before = world.client.get(f"/api/v1/{route}/{identifier}").json()
    response = decide(world, before, catalog, kind="ticket" if kind == "chamado" else "article")
    assert response.status_code == 200, response.text
    after = world.client.get(f"/api/v1/{route}/{identifier}").json()
    assert after["system"] == before["system"]
    assert after["status"] == before["status"]
    assert after["legacy_system_snapshot"] == "Grafia fictícia original"
    assert after["system_id"] == catalog["id"]


def test_selection_and_removal_are_versioned_and_stale_revision_rejected(world):
    client_id = work.prepare(world)
    catalog = create(world)
    record = work.create(world, client_id, system="Nome legado fictício")
    response = identity.mutate(
        world.client,
        f"/records/{record['id']}",
        {"revision": 1, "texto_organizado": "Texto humano fictício", "system_id": catalog["id"]},
        "PATCH",
    )
    assert response.status_code == 200, response.text
    selected = response.json()
    assert selected["system_id"] == catalog["id"]
    assert selected["legacy_system_snapshot"] == record["system"]
    assert (
        identity.mutate(
            world.client,
            f"/records/{record['id']}",
            {"revision": 1, "texto_organizado": "Texto antigo", "system_id": None},
            "PATCH",
        ).status_code
        == 409
    )
    cleared = identity.mutate(
        world.client,
        f"/records/{record['id']}",
        {"revision": 2, "texto_organizado": "Texto humano fictício", "system_id": None},
        "PATCH",
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["system_id"] is None
    versions = world.client.get(f"/api/v1/records/{record['id']}/versions").json()
    assert versions[1]["snapshot"]["system_id"] == catalog["id"]


def test_legacy_whitespace_is_not_trimmed_by_reconciliation(world):
    client_id = work.prepare(world)
    catalog = create(world, "ERP Fictício")
    item = work.create(world, client_id, system="ERP Fictício")
    raw = "  ERP  Fictício "
    with Session(world.admin_engine) as db, db.begin():
        db.execute(
            text("UPDATE record SET system=:raw WHERE id=:id"), {"raw": raw, "id": item["id"]}
        )
    item = world.client.get(f"/api/v1/records/{item['id']}").json()
    response = decide(world, item, catalog)
    assert response.status_code == 200, response.text
    assert response.json()["legacy_system_snapshot"] == raw
    assert response.json()["legacy_text"] == raw


def test_concurrent_system_edits_have_one_conflict(world):
    work.prepare(world)
    item = create(world)
    barrier = Barrier(2)

    def run(index):
        with TestClient(world.app, client=(uuid4().hex, 1234)) as client:
            identity.login(client, world.admin_a, world.password)
            barrier.wait(timeout=10)
            return identity.mutate(
                client,
                f"/systems/{item['id']}",
                {
                    "revision": 1,
                    "name": f"Nome fictício {index}",
                    "description": f"Descrição {index}",
                },
                "PATCH",
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, [0, 1])) == [200, 409]
