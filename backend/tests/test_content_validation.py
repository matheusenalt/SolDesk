import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
import test_identity as identity
import test_media as media_tests
import test_work as work_tests
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.access import set_context
from app.models import AuditEvent
from app.validation_models import ContentValidation, RecordContentVersion

pg_settings = identity.pg_settings
world = identity.world
login = identity.login
mutate = identity.mutate


def prepare(world, kind="finalizacao", **values):
    client_id = work_tests.prepare(world)
    item = work_tests.create(world, client_id, kind, **values)
    return item


def current(client, item):
    response = client.get(f"/api/v1/records/{item['id']}/text-validation")
    assert response.status_code == 200, response.text
    return response.json()


def validate(client, item, version=None, **fields):
    version = version or current(client, item)["version"]
    return mutate(
        client,
        f"/records/{item['id']}/text-validations",
        {
            "version_id": version["id"],
            "content_hash": version["content_hash"],
            "reviewed": True,
            **fields,
        },
    )


def test_self_validation_is_explicit_idempotent_and_keeps_facts(world):
    item = prepare(world)
    assert "text_validation" in world.client.get("/api/v1/server-info").json()["capabilities"]
    pending = current(world.client, item)
    assert pending["status"] == "nao_validado" and pending["validations"] == []
    version = pending["version"]
    canonical = json.dumps(
        version["content"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    assert version["content_hash"] == hashlib.sha256(canonical.encode()).hexdigest()
    assert validate(world.client, item, reviewed=False).status_code == 422
    result = validate(world.client, item)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "validado"
    assert validate(world.client, item).json()["validations"] == result.json()["validations"]
    after = world.client.get(f"/api/v1/records/{item['id']}").json()
    assert after == item  # Nem revisão, horários, resolução ou confirmação operacional mudam.
    with Session(world.admin_engine) as db:
        events = db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.entity_id == item["id"], AuditEvent.action == "fidelidade_validada")
        )
        assert events == 1


def test_other_authorized_reader_validates_without_resolving_ticket(world):
    item = prepare(world, "chamado", assignee_id=world.technician_id)
    ticket_before = world.client.get(f"/api/v1/tickets/{item['ticket_id']}").json()
    login(world.client, world.technician, world.password)
    response = validate(world.client, item)
    assert response.status_code == 200, response.text
    assert response.json()["validations"][0]["validated_by"] == world.technician_id
    assert world.client.get(f"/api/v1/tickets/{item['ticket_id']}").json() == ticket_before
    resolved = mutate(
        world.client,
        f"/tickets/{item['ticket_id']}",
        {
            "revision": ticket_before["revision"],
            "status": "resolvido",
        },
        "PATCH",
    )
    assert resolved.status_code == 200
    resolved_detail = world.client.get(f"/api/v1/tickets/{item['ticket_id']}").json()
    assert validate(world.client, item).status_code == 200
    assert world.client.get(f"/api/v1/tickets/{item['ticket_id']}").json() == resolved_detail
    assert (
        mutate(
            world.client,
            f"/records/{item['id']}",
            {
                "revision": item["revision"],
                "texto_organizado": "Não autorizado a editar o autor",
            },
            "PATCH",
        ).status_code
        == 403
    )


def test_permissions_object_tenant_and_explicit_hash(world):
    item = prepare(world)
    version = current(world.client, item)["version"]
    assert validate(world.client, item, version, content_hash="0" * 64).status_code == 409
    assert validate(world.client, item, version, organization_id=world.b).status_code == 422
    login(world.client, world.technician, world.password)
    assert world.client.get(f"/api/v1/records/{item['id']}/text-validation").status_code == 404
    assert validate(world.client, item, version).status_code == 404
    assert current_pending(world.client)["total"] == 0
    login(world.client, world.admin_b, world.password)
    assert validate(world.client, item, version).status_code == 404
    assert world.client.get(f"/api/v1/records/{item['id']}/text-validation").status_code == 404
    for org in (world.b, ""):
        with Session(world.runtime_engine) as db:
            set_context(db, org)
            assert not db.scalars(
                select(RecordContentVersion).where(RecordContentVersion.record_id == item["id"])
            ).all()
            assert not db.scalars(
                select(ContentValidation).where(ContentValidation.record_id == item["id"])
            ).all()


def current_pending(client):
    result = client.get("/api/v1/records/text-validations/pending")
    assert result.status_code == 200, result.text
    return result.json()


def test_material_edit_invalidates_current_and_preserves_previous(world):
    item = prepare(world)
    first = current(world.client, item)["version"]
    assert validate(world.client, item).status_code == 200
    assert current_pending(world.client)["total"] == 0
    edited = mutate(
        world.client,
        f"/records/{item['id']}",
        {
            "revision": item["revision"],
            "texto_organizado": "Correção humana fictícia.",
        },
        "PATCH",
    )
    assert edited.status_code == 200, edited.text
    state = current(world.client, item)
    assert state["status"] == "nao_validado" and len(state["validations"]) == 1
    assert state["version"]["id"] != first["id"]
    stale = validate(world.client, item, first)
    assert stale.status_code == 409 and stale.headers["content-type"].startswith(
        "application/problem+json"
    )
    assert "Recarregue" in stale.json()["title"]
    assert current_pending(world.client)["items"][0]["record_id"] == item["id"]
    assert validate(world.client, item).json()["status"] == "validado"
    validated_version = current(world.client, item)["version"]
    second = mutate(
        world.client,
        f"/records/{item['id']}",
        {
            "revision": edited.json()["revision"],
            "texto_organizado": "Outro texto fictício.",
        },
        "PATCH",
    )
    restored = mutate(
        world.client,
        f"/records/{item['id']}",
        {
            "revision": second.json()["revision"],
            "texto_organizado": "Correção humana fictícia.",
        },
        "PATCH",
    )
    assert restored.status_code == 200
    current_version = current(world.client, item)["version"]
    assert current_version["content_hash"] == validated_version["content_hash"]
    assert current_version["id"] != validated_version["id"]
    assert validate(world.client, item, validated_version).status_code == 409


@pytest.mark.parametrize("kind", ["finalizacao", "chamado"])
def test_async_processing_changes_exact_content_but_never_validates(world, kind):
    _, item = media_tests.prepare(world, kind)
    before = current(world.client, item)["version"]
    assert validate(world.client, item).status_code == 200
    uploaded = media_tests.upload(world, item)
    assert uploaded.status_code == 202, uploaded.text
    job = uploaded.json()["job"]
    assert job["status"] == "aguardando"
    assert current(world.client, item)["status"] == "validado"  # O texto atual não mudou.
    processed = media_tests.run(world, job)
    assert processed["jobs"][0]["status"] == "concluido"
    state = current(world.client, item)
    assert state["status"] == "nao_validado" and state["version"]["id"] != before["id"]
    assert state["version"]["content"]["transcription"]["raw_text"]
    assert len(state["validations"]) == 1
    assert validate(world.client, item, before).status_code == 409
    assert validate(world.client, item).status_code == 200
    if kind == "chamado":
        assert world.client.get(f"/api/v1/tickets/{item['ticket_id']}").json()["status"] == "aberto"


def test_operational_confirmation_does_not_validate_text_or_change_material_version(world):
    item = prepare(world)
    version = current(world.client, item)["version"]
    response = work_tests.action(world.client, item, "confirmar")
    assert response.status_code == 200, response.text
    state = current(world.client, item)
    assert state["status"] == "nao_validado" and state["version"]["id"] == version["id"]
    assert validate(world.client, item).status_code == 200
    assert world.client.get(f"/api/v1/records/{item['id']}").json() == response.json()


@pytest.mark.parametrize("editing", [True, False])
def test_concurrent_edit_validation_and_duplicate_validation(world, editing):
    item = prepare(world)
    version = current(world.client, item)["version"]
    cookie = world.client.cookies.get("soldesk_session")
    barrier = Barrier(2)

    def run(index):
        with TestClient(world.app) as client:
            client.cookies.set("soldesk_session", cookie)
            barrier.wait(timeout=10)
            if editing and index == 0:
                return mutate(
                    client,
                    f"/records/{item['id']}",
                    {
                        "revision": item["revision"],
                        "texto_organizado": "Edição concorrente fictícia.",
                    },
                    "PATCH",
                )
            return validate(client, item, version)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert results[0].status_code == 200, results[0].text
    state = current(world.client, item)
    if editing:
        assert results[1].status_code in {200, 409}, results[1].text
        assert state["status"] == "nao_validado"
        assert len(state["validations"]) == (1 if results[1].status_code == 200 else 0)
        assert all(v["version_id"] != state["version"]["id"] for v in state["validations"])
    else:
        assert results[1].status_code == 200, results[1].text
        assert state["status"] == "validado" and len(state["validations"]) == 1


def test_versions_and_events_are_immutable_and_database_checks_hash(world):
    item = prepare(world)
    state = validate(world.client, item).json()
    with Session(world.admin_engine) as db, pytest.raises(DBAPIError) as invalid_hash:
        db.execute(
            text("""INSERT INTO record_content_version
            (id,organization_id,record_id,record_revision,source_version_id,
             canonical_snapshot,content_hash,criado_em)
            SELECT :id,organization_id,record_id,record_revision,source_version_id,
                   canonical_snapshot,:hash,now() FROM record_content_version WHERE id=:source"""),
            {
                "id": str(uuid4()),
                "hash": "0" * 64,
                "source": state["version"]["id"],
            },
        )
        db.commit()
    assert invalid_hash.value.orig.sqlstate == "23514"
    for table, identifier in (
        ("record_content_version", state["version"]["id"]),
        ("content_validation", state["validations"][0]["id"]),
    ):
        for statement in (
            f"UPDATE {table} SET record_id=record_id WHERE id=:id",
            f"DELETE FROM {table} WHERE id=:id",
        ):
            with Session(world.admin_engine) as db, pytest.raises(DBAPIError):
                db.execute(text(statement), {"id": identifier})
                db.commit()
    with Session(world.runtime_engine) as db, db.begin():
        set_context(db, world.b)
        assert db.scalar(select(func.count()).select_from(ContentValidation)) == 0
        with pytest.raises(DBAPIError):
            db.execute(
                text("""INSERT INTO content_validation
                (id,organization_id,record_id,version_id,content_hash,validated_by,validado_em)
                VALUES (:id,:org,:record,:version,:hash,:user,now())"""),
                {
                    "id": str(uuid4()),
                    "org": world.a,
                    "record": item["id"],
                    "version": state["version"]["id"],
                    "hash": state["version"]["content_hash"],
                    "user": world.technician_id,
                },
            )
