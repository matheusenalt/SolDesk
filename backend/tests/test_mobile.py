import secrets
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
import test_identity as identity
import test_work as work_tests
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.access import set_context
from app.media_worker import process_audio
from app.mobile_models import MobileRefreshToken
from app.models import AuthSession, OrganizationMembership, User, now
from app.security import digest

pg_settings = identity.pg_settings
world = identity.world


@pytest.fixture
def native(world):
    with TestClient(world.app, client=("native-" + world.suffix, 1234)) as client:
        yield client


def enter(world, native, email=None):
    response = native.post(
        "/api/v1/mobile/auth/login",
        json={
            "email": email or world.admin_a,
            "password": world.password,
        },
    )
    assert response.status_code == 200, response.text
    assert "set-cookie" not in response.headers
    tokens = response.json()
    native.headers["Authorization"] = "Bearer " + tokens["access_token"]
    return tokens


def renew(native, tokens):
    return native.post(
        "/api/v1/mobile/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )


def test_native_login_access_kind_and_web_csrf_boundary(world, native):
    tokens = enter(world, native)
    assert tokens["token_type"] == "Bearer"
    assert native.get("/api/v1/me").json()["organization_id"] == world.a
    info = native.get("/api/v1/server-info").json()
    assert info["mobile_protocol_version"] == 1 and "mobile_auth" in info["capabilities"]
    assert info["instance_name"] == "Instância SolDesk"
    with Session(world.admin_engine) as db:
        session = db.get(AuthSession, digest(tokens["access_token"]))
        assert session.client_kind == "mobile"
        assert 880 < (session.expira_em - now()).total_seconds() <= 900
        assert db.scalar(
            select(MobileRefreshToken).where(
                MobileRefreshToken.token_hash == digest(tokens["refresh_token"])
            )
        )
    # Credencial mobile não pode virar cookie nem cookie web virar bearer.
    native.cookies.set("soldesk_session", tokens["access_token"])
    assert native.get("/api/v1/me").status_code == 401
    native.cookies.clear()
    identity.login(world.client, world.admin_a, world.password)
    web_token = world.client.cookies.get("soldesk_session")
    assert (
        native.get("/api/v1/me", headers={"Authorization": "Bearer " + web_token}).status_code
        == 401
    )
    assert world.client.post("/api/v1/clients", json={"name": "Sem CSRF"}).status_code == 403
    assert (
        native.post(
            "/api/v1/clients",
            json={"name": "Inválido"},
            headers={"Authorization": "Bearer " + "x" * 64},
        ).status_code
        == 401
    )


def test_refresh_rotates_and_replay_revokes_entire_family(world, native):
    original = enter(world, native)
    response = renew(native, original)
    assert response.status_code == 200 and "set-cookie" not in response.headers
    rotated = response.json()
    assert rotated["refresh_token"] != original["refresh_token"]
    assert rotated["renovacao_expira_em"] == original["renovacao_expira_em"]
    assert native.get("/api/v1/me").status_code == 401  # acesso anterior revogado
    native.headers["Authorization"] = "Bearer " + rotated["access_token"]
    assert native.get("/api/v1/me").status_code == 200
    assert renew(native, original).status_code == 401
    assert native.get("/api/v1/me").status_code == 401
    assert renew(native, rotated).status_code == 401
    with Session(world.admin_engine) as db:
        rows = db.scalars(
            select(MobileRefreshToken).where(MobileRefreshToken.organization_id == world.a)
        ).all()
        assert len(rows) == 2 and all(row.revogado_em for row in rows)


def test_expired_access_can_refresh_but_expired_or_revoked_refresh_cannot(world, native):
    tokens = enter(world, native)
    with Session(world.admin_engine) as db, db.begin():
        db.get(AuthSession, digest(tokens["access_token"])).expira_em = now() - timedelta(seconds=1)
    assert native.get("/api/v1/me").status_code == 401
    response = renew(native, tokens)
    assert response.status_code == 200
    tokens = response.json()
    with Session(world.admin_engine) as db, db.begin():
        db.get(MobileRefreshToken, digest(tokens["refresh_token"])).expira_em = now() - timedelta(
            seconds=1
        )
    assert renew(native, tokens).status_code == 401
    tokens = enter(world, native)
    assert (
        native.post(
            "/api/v1/mobile/auth/logout", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 204
    )
    assert native.get("/api/v1/me").status_code == 401 and renew(native, tokens).status_code == 401


def test_concurrent_refresh_has_one_result_and_replay_is_fail_closed(world, native):
    tokens = enter(world, native)

    def attempt(_):
        with TestClient(world.app, client=("race-" + world.suffix, 1234)) as other:
            response = renew(other, tokens)
            return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sorted(code for code, _ in results) == [200, 401]
    issued = next(value for code, value in results if code == 200)
    assert (
        native.get(
            "/api/v1/me", headers={"Authorization": "Bearer " + issued["access_token"]}
        ).status_code
        == 401
    )


def test_membership_global_logout_password_change_and_temporary_password(world, native):
    tokens = enter(world, native, world.technician)
    with Session(world.admin_engine) as db, db.begin():
        db.get(OrganizationMembership, world.membership).situation = "inativo"
    assert native.get("/api/v1/me").status_code == 401 and renew(native, tokens).status_code == 401
    with Session(world.admin_engine) as db, db.begin():
        db.get(OrganizationMembership, world.membership).situation = "ativo"
        db.get(User, world.technician_id).must_change_password = True
    tokens = enter(world, native, world.technician)
    assert native.get("/api/v1/me").json()["must_change_password"]
    assert native.get("/api/v1/clients").status_code == 403
    changed = native.post(
        "/api/v1/mobile/auth/password",
        json={
            "current_password": world.password,
            "new_password": secrets.token_urlsafe(20),
        },
    )
    assert changed.status_code == 200 and "set-cookie" not in changed.headers
    assert renew(native, tokens).status_code == 401
    new = changed.json()
    native.headers["Authorization"] = "Bearer " + new["access_token"]
    assert native.get("/api/v1/clients").status_code == 200
    assert native.post("/api/v1/auth/logout-all").status_code == 200
    assert renew(native, new).status_code == 401


def test_bearer_business_tenant_rls_and_idempotent_text_flow(world, native):
    client_id = work_tests.prepare(world)
    tokens = enter(world, native, world.technician)
    body = {
        "client_id": client_id,
        "type": "finalizacao",
        "texto_original": "Relato mobile fictício.",
        "ocorrido_em": "2026-11-01T23:30:00-03:00",
    }
    key = secrets.token_urlsafe(20)
    created = native.post("/api/v1/records", json=body, headers={"Idempotency-Key": key})
    assert created.status_code == 201, created.text
    record = created.json()
    assert (
        native.post("/api/v1/records", json=body, headers={"Idempotency-Key": key}).json()["id"]
        == record["id"]
    )
    confirmed = native.post(
        f"/api/v1/records/{record['id']}/actions",
        json={"revision": record["revision"], "action": "confirmar"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["ocorrido_em"] == record["ocorrido_em"]
    assert native.get(f"/api/v1/clients/{client_id}/history").json()["confirmed_total"] == 1
    enter(world, native, world.admin_b)
    assert native.get(f"/api/v1/records/{record['id']}").status_code == 404
    assert native.get(f"/api/v1/clients/{client_id}").status_code == 404
    assert native.post("/api/v1/records", json=body).status_code == 404
    with Session(world.runtime_engine) as db:
        set_context(db, world.b)
        assert list(db.scalars(select(MobileRefreshToken))) == []  # exige usuário também
        set_context(db, world.b, world.technician_id)
        assert db.get(MobileRefreshToken, digest(tokens["refresh_token"])) is None
        policies = db.execute(
            text(
                "SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                "WHERE relname='mobile_refresh_token'"
            )
        ).one()
        assert all(policies)


def test_native_m4a_upload_processing_review_and_urgent_ticket(world, native, tmp_path):
    client_id = work_tests.prepare(world)
    enter(world, native, world.technician)
    record = native.post(
        "/api/v1/records",
        json={
            "client_id": client_id,
            "type": "finalizacao",
            "texto_original": "Áudio fictício com relato digitado para o mock.",
        },
    ).json()
    path = tmp_path / "ficticio.m4a"
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
            "aac",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    uploaded = native.post(
        f"/api/v1/records/{record['id']}/audio?revision={record['revision']}",
        content=path.read_bytes(),
        headers={"Content-Type": "audio/mp4", "X-Filename": "ficticio.m4a"},
    )
    assert uploaded.status_code == 202, uploaded.text
    job = uploaded.json()["job"]
    process_audio(world.a, job["id"], world.app.state.settings)
    result = native.get(f"/api/v1/records/{record['id']}/processing").json()
    assert result["record"]["status"] == "aguardando_revisao"
    assert result["record"]["ocorrido_em"] == record["ocorrido_em"]
    assert result["jobs"][0]["provider_metadata"]["simulado"]
    current = result["record"]
    assert (
        native.post(
            f"/api/v1/records/{record['id']}/actions",
            json={"revision": current["revision"], "action": "confirmar", "audio_reviewed": True},
        ).status_code
        == 200
    )
    urgent = native.post(
        "/api/v1/records",
        json={
            "client_id": client_id,
            "type": "chamado",
            "texto_original": "Chamado mobile fictício urgente.",
            "priority": "urgente",
        },
    ).json()
    ticket = native.get(f"/api/v1/tickets/{urgent['ticket_id']}").json()
    assert (
        native.patch(
            f"/api/v1/tickets/{ticket['id']}",
            json={"revision": ticket["revision"], "status": "resolvido"},
        ).status_code
        == 200
    )
    assert native.get("/api/v1/notifications").status_code == 200
