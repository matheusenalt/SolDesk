import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.access import set_context
from app.config import Settings
from app.main import create_app
from app.manage import create_organization, migrate, seed
from app.models import (
    AuditEvent,
    AuthSession,
    Client,
    Invitation,
    Organization,
    OrganizationMembership,
    User,
    now,
)
from app.security import digest, password_hash


@pytest.fixture(scope="session")
def pg_settings():
    settings = Settings()
    if not settings.migration_database_url or not settings.migration_database_url.endswith(
        "/soldesk_test"
    ):
        pytest.skip("Execute o perfil Compose test com PostgreSQL isolado soldesk_test")
    migrate(settings)
    return settings


@pytest.fixture
def world(pg_settings):
    suffix = uuid4().hex[:12]
    password = secrets.token_urlsafe(20)
    admin_engine = create_engine(pg_settings.migration_database_url)
    runtime_engine = create_engine(pg_settings.database_url, pool_size=1, max_overflow=0)
    with Session(admin_engine) as db, db.begin():
        first, _ = create_organization(
            db,
            "Aurora fictícia",
            f"aurora-{suffix}",
            f"admin-a-{suffix}@example.test",
            "Admin Aurora",
            password,
        )
        second, _ = create_organization(
            db,
            "Horizonte fictícia",
            f"horizonte-{suffix}",
            f"admin-b-{suffix}@example.test",
            "Admin Horizonte",
            password,
        )
        admin_a = db.scalar(select(User).where(User.email == f"admin-a-{suffix}@example.test"))
        admin_b = db.scalar(select(User).where(User.email == f"admin-b-{suffix}@example.test"))
        technician = User(
            name="Técnico fictício",
            email=f"tech-{suffix}@example.test",
            password_hash=password_hash(password),
        )
        db.add(technician)
        db.flush()
        membership = OrganizationMembership(
            organization_id=first.id, user_id=technician.id, role="tecnico"
        )
        db.add(membership)
        db.flush()
        data = SimpleNamespace(
            a=first.id,
            b=second.id,
            admin_a=admin_a.email,
            admin_b=admin_b.email,
            technician=technician.email,
            technician_id=technician.id,
            membership=membership.id,
            password=password,
            suffix=suffix,
        )
    app = create_app(pg_settings)
    with TestClient(app, client=(f"test-{suffix}", 12345)) as client:
        data.client = client
        data.app = app
        data.admin_engine = admin_engine
        data.runtime_engine = runtime_engine
        yield data
    runtime_engine.dispose()
    admin_engine.dispose()


def mutate(client, path, data=None, method="POST"):
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200, response.text
    return client.request(
        method, "/api/v1" + path, json=data, headers={"X-CSRF-Token": response.json()["csrf_token"]}
    )


def login(client, email, password):
    response = mutate(client, "/auth/login", {"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response


def test_http_tenant_isolation_and_client_validation(world):
    client = world.client
    assert client.get("/api/v1/health").status_code == 200
    info = client.get("/api/v1/server-info")
    assert info.status_code == 200, info.text
    assert "clients" in info.json()["capabilities"]
    assert client.get("/api/v1/clients").status_code == 401
    login(client, world.admin_a, world.password)
    first = mutate(
        client,
        "/clients",
        {
            "name": "Merceária Ramos",
            "nickname": "Armazém",
            "external_refs": [
                {"provider": "whatsapp", "identifier": "grupo-ficticio", "label": "Grupo fictício"}
            ],
        },
    )
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]
    assert client.get("/api/v1/clients?search=mercearia").json()["total"] == 1
    assert client.get("/api/v1/clients?search=ARMAZEM").json()["total"] == 1
    assert mutate(client, "/clients", {"name": "MERCEARIA RAMOS"}).status_code == 409
    assert (
        mutate(client, "/clients", {"name": "Outro", "organization_id": world.b}).status_code == 422
    )
    assert mutate(client, "/clients", {"name": "Outro", "email": "invalido"}).status_code == 422
    assert mutate(client, "/clients", {"name": "Segundo"}).status_code == 201
    page1 = client.get("/api/v1/clients?limit=1").json()
    page2 = client.get("/api/v1/clients?limit=1&offset=1").json()
    assert page1["total"] == page2["total"] == 2
    assert page1["items"][0]["id"] != page2["items"][0]["id"]
    assert client.get("/api/v1/clients?search=%25").json()["total"] == 0
    login(client, world.admin_b, world.password)
    assert client.get("/api/v1/clients").json()["total"] == 0
    assert client.get(f"/api/v1/clients/{first_id}").status_code == 404
    assert mutate(client, f"/clients/{first_id}", {"name": "Tentativa"}, "PATCH").status_code == 404
    assert mutate(client, "/organizations/select", {"organization_id": world.a}).status_code == 404
    login(client, world.admin_a, world.password)
    assert client.get(f"/api/v1/clients/{first_id}").json()["name"] == "Merceária Ramos"


def test_rls_without_application_filter_and_pool_reset(world):
    with Session(world.admin_engine) as db, db.begin():
        for org in (world.a, world.b):
            db.add(Client(organization_id=org, name=f"Cliente {org}", name_key=org))
    with Session(world.runtime_engine) as db:
        role = db.execute(
            text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
        ).one()
        assert not role.rolsuper and not role.rolbypassrls
        assert db.scalar(
            text("SELECT tableowner <> current_user FROM pg_tables WHERE tablename='client'")
        )
        set_context(db, world.a)
        rows = db.scalars(select(Client)).all()  # Deliberadamente SEM filtro de tenant.
        assert rows and {row.organization_id for row in rows} == {world.a}
        assert (
            db.execute(
                text("UPDATE client SET notes='tentativa' WHERE organization_id=:b"), {"b": world.b}
            ).rowcount
            == 0
        )
        db.commit()
    with Session(world.runtime_engine) as db:
        assert db.scalars(select(Client)).all() == []  # Mesma conexão do pool sem contexto.
        set_context(db, world.b)
        assert {row.organization_id for row in db.scalars(select(Client))} == {world.b}
    with Session(world.runtime_engine) as db:
        set_context(db, world.a)
        db.add(Client(organization_id=world.b, name="Negado", name_key=uuid4().hex))
        with pytest.raises(DBAPIError):
            db.flush()
        db.rollback()


def test_permissions_last_admin_revocation_and_logout(world):
    client = world.client
    login(client, world.technician, world.password)
    assert (
        mutate(
            client,
            f"/memberships/{world.membership}",
            {"role": "administrador", "situation": "ativo"},
            "PATCH",
        ).status_code
        == 403
    )
    assert client.get("/api/v1/memberships").status_code == 403
    technician_token = client.cookies.get("soldesk_session")
    login(client, world.admin_a, world.password)
    members = client.get("/api/v1/memberships").json()
    admin = next(m for m in members if m["email"] == world.admin_a)
    assert (
        mutate(
            client,
            f"/memberships/{admin['id']}",
            {"role": "tecnico", "situation": "ativo"},
            "PATCH",
        ).status_code
        == 409
    )
    assert (
        mutate(
            client,
            f"/memberships/{admin['id']}",
            {"role": "administrador", "situation": "inativo"},
            "PATCH",
        ).status_code
        == 409
    )
    assert (
        mutate(
            client,
            f"/memberships/{world.membership}",
            {"role": "tecnico", "situation": "inativo"},
            "PATCH",
        ).status_code
        == 200
    )
    with TestClient(world.app) as other:
        other.cookies.set("soldesk_session", technician_token)
        assert other.get("/api/v1/me").status_code == 401
    second_token = client.cookies.get("soldesk_session")
    login(client, world.admin_a, world.password)
    assert mutate(client, "/auth/logout-all").status_code == 200
    assert client.get("/api/v1/me").status_code == 401
    with TestClient(world.app) as other:
        other.cookies.set("soldesk_session", second_token)
        assert other.get("/api/v1/me").status_code == 401


def test_csrf_rate_limit_and_no_account_enumeration(world):
    client = world.client
    body = {"email": world.admin_a, "password": world.password}
    denied = client.post("/api/v1/auth/login", json=body)
    assert denied.status_code == 403
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    assert (
        client.post(
            "/api/v1/auth/login",
            json=body,
            headers={"X-CSRF-Token": csrf, "Origin": "https://untrusted.invalid"},
        ).status_code
        == 403
    )
    wrong = mutate(client, "/auth/login", {"email": world.admin_a, "password": "senha-errada"})
    missing = mutate(
        client,
        "/auth/login",
        {"email": f"missing-{world.suffix}@example.test", "password": "senha-errada"},
    )
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json()["title"] == missing.json()["title"]
    for _ in range(4):
        mutate(client, "/auth/login", {"email": world.admin_a, "password": "senha-errada"})
    assert mutate(client, "/auth/login", body).status_code == 429
    assert mutate(client, "/auth/login", body).headers["content-type"] == "application/problem+json"


def test_one_time_invitation_expiration_and_existing_identity(world):
    client = world.client
    login(client, world.admin_a, world.password)
    email = f"invite-{world.suffix}@example.test"
    invitation = mutate(client, "/invitations", {"email": email, "role": "tecnico"}).json()
    token = invitation["invitation_path"].split("=", 1)[1]
    mutate(client, "/auth/logout")
    body = {
        "email": email,
        "name": "Convidado fictício",
        "password": secrets.token_urlsafe(20),
        "token": token,
    }
    assert mutate(client, "/invitations/accept", body).status_code == 200
    assert mutate(client, "/invitations/accept", body).status_code == 400
    login(client, world.admin_a, world.password)
    invitation = mutate(
        client, "/invitations", {"email": f"expired-{world.suffix}@example.test", "role": "tecnico"}
    ).json()
    with Session(world.admin_engine) as db, db.begin():
        db.get(Invitation, invitation["id"]).expira_em = now() - timedelta(seconds=1)
    body["email"] = f"expired-{world.suffix}@example.test"
    body["token"] = invitation["invitation_path"].split("=", 1)[1]
    assert mutate(client, "/invitations/accept", body).status_code == 400
    invitation = mutate(client, "/invitations", {"email": world.admin_b, "role": "tecnico"}).json()
    body.update(email=world.admin_b, token=invitation["invitation_path"].split("=", 1)[1])
    assert mutate(client, "/invitations/accept", body).status_code == 400
    body["password"] = world.password
    assert mutate(client, "/invitations/accept", body).status_code == 200
    organizations = client.get("/api/v1/me").json()["organizations"]
    assert {o["id"] for o in organizations} == {world.a, world.b}
    assert mutate(client, "/organizations/select", {"organization_id": world.b}).status_code == 200
    login(client, world.admin_a, world.password)
    shared = next(
        m for m in client.get("/api/v1/memberships").json() if m["email"] == world.admin_b
    )
    assert mutate(client, f"/memberships/{shared['id']}/reset-password").status_code == 409


def test_temporary_password_reset_expiry_cookies_and_no_secret_logs(world, caplog):
    client = world.client
    login_response = login(client, world.admin_a, world.password)
    assert "HttpOnly" in login_response.headers["set-cookie"]
    assert "SameSite=strict" in login_response.headers["set-cookie"]
    created = mutate(
        client,
        "/memberships",
        {
            "email": f"temporary-{world.suffix}@example.test",
            "name": "Temporário fictício",
            "role": "tecnico",
        },
    )
    assert created.status_code == 201, created.text
    temporary = created.json()["temporary_password"]
    member_id = created.json()["id"]
    login(client, f"temporary-{world.suffix}@example.test", temporary)
    assert client.get("/api/v1/me").json()["must_change_password"] is True
    assert client.get("/api/v1/clients").status_code == 403
    new_password = secrets.token_urlsafe(20)
    assert (
        mutate(
            client, "/auth/password", {"current_password": temporary, "new_password": new_password}
        ).status_code
        == 200
    )
    assert client.get("/api/v1/clients").status_code == 200
    old_token = client.cookies.get("soldesk_session")
    login(client, world.admin_a, world.password)
    reset = mutate(client, f"/memberships/{member_id}/reset-password")
    assert reset.status_code == 200
    with TestClient(world.app) as other:
        other.cookies.set("soldesk_session", old_token)
        assert other.get("/api/v1/me").status_code == 401
    token = client.cookies.get("soldesk_session")
    with Session(world.admin_engine) as db, db.begin():
        rows = db.scalars(select(AuditEvent).where(AuditEvent.organization_id == world.a)).all()
        audit_text = json.dumps([{"before": r.before, "after": r.after} for r in rows])
        db.get(AuthSession, digest(token)).expira_em = now() - timedelta(seconds=1)
    for secret in (
        world.password,
        temporary,
        new_password,
        token,
        reset.json()["temporary_password"],
    ):
        assert secret not in caplog.text
        assert secret not in audit_text
    assert "$argon2" not in audit_text
    assert client.get("/api/v1/me").status_code == 401


def test_signup_modes_and_idempotent_demo(pg_settings, capsys):
    for mode, enabled in (("community", True), ("cloud", False), ("cloud", True)):
        settings = pg_settings.model_copy(
            update={"soldesk_mode": mode, "allow_org_signup": enabled}
        )
        with TestClient(create_app(settings), client=(uuid4().hex, 123)) as client:
            suffix = uuid4().hex[:12]
            body = {
                "email": f"signup-{suffix}@example.test",
                "password": secrets.token_urlsafe(20),
                "name": "Admin fictício",
                "organization_name": "Empresa fictícia",
                "slug": f"signup-{suffix}",
            }
            result = mutate(client, "/organizations", body)
            assert result.status_code == (201 if mode == "cloud" and enabled else 403)
    seed(pg_settings)
    engine = create_engine(pg_settings.migration_database_url)
    with Session(engine) as db:
        count = db.scalar(select(func.count()).select_from(Organization))
    seed(pg_settings)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Organization)) == count
        assert (
            len(
                db.scalars(
                    select(Organization).where(
                        Organization.slug.in_(["demo-aurora", "demo-horizonte"])
                    )
                ).all()
            )
            == 2
        )
    engine.dispose()
    capsys.readouterr()  # Senhas fictícias de demonstração não integram o relatório de testes.


def test_concurrent_last_administrator_guard(world):
    with Session(world.admin_engine) as db, db.begin():
        user = db.scalar(select(User).where(User.email == world.technician))
        db.get(OrganizationMembership, world.membership).role = "administrador"
        first = db.scalar(
            select(OrganizationMembership)
            .join(User, User.id == OrganizationMembership.user_id)
            .where(User.email == world.admin_a)
        )
        first_id = first.id
        second_email = user.email

    def downgrade(email, member_id):
        with TestClient(world.app, client=(uuid4().hex, 123)) as client:
            login(client, email, world.password)
            return mutate(
                client,
                f"/memberships/{member_id}",
                {"role": "tecnico", "situation": "ativo"},
                "PATCH",
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(downgrade, world.admin_a, first_id)
        second = pool.submit(downgrade, second_email, world.membership)
        assert sorted([first.result(), second.result()]) == [200, 409]


def test_runtime_role_guard_secure_cookie_and_password_validation(world, pg_settings):
    unsafe = pg_settings.model_copy(update={"database_url": pg_settings.migration_database_url})
    with TestClient(create_app(unsafe)) as client:
        assert client.get("/api/v1/clients").status_code == 503
    secure = pg_settings.model_copy(update={"environment": "production"})
    with TestClient(create_app(secure), base_url="https://testserver") as client:
        response = client.get("/api/v1/auth/csrf")
        assert response.status_code == 200
        assert "Secure" in response.headers["set-cookie"]
    from app.schemas import Login

    assert (
        Login(email="a@example.test", password=" senha preservada ").password
        == " senha preservada "
    )


def test_ip_throttle_progressive_lock_and_csrf_expiry(world):
    from app.models import AuthThrottle, CsrfGrant

    client = world.client
    for attempt in range(31):
        result = mutate(
            client,
            "/auth/login",
            {
                "email": f"absent-{attempt}-{world.suffix}@example.test",
                "password": "incorreta",
            },
        )
    assert result.status_code == 429
    ip_key = f"login:ip:{digest('test-' + world.suffix)}"
    with Session(world.admin_engine) as db, db.begin():
        row = db.get(AuthThrottle, ip_key)
        assert row.failures >= 5 and row.bloqueado_ate > now()
        row.window_em = now() - timedelta(minutes=2)
    # Mesmo após a janela de contagem, o bloqueio progressivo permanece.
    assert (
        mutate(
            client, "/auth/login", {"email": world.admin_a, "password": world.password}
        ).status_code
        == 429
    )
    response = client.get("/api/v1/auth/csrf")
    token = response.json()["csrf_token"]
    with Session(world.admin_engine) as db, db.begin():
        db.get(CsrfGrant, digest(token)).expira_em = now() - timedelta(seconds=1)
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": world.admin_a, "password": world.password},
            headers={"X-CSRF-Token": token},
        ).status_code
        == 403
    )
