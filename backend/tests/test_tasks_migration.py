"""Upgrade/reversão vazia somente em banco novo no cluster isolado de testes."""

from pathlib import Path
from uuid import uuid4

import pytest
import test_identity as identity
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.manage import create_organization, migrate
from app.models import Client, User

pg_settings = identity.pg_settings


def test_upgrade_preserves_legacy_and_enforces_task_tenants(pg_settings, monkeypatch):
    original = make_url(pg_settings.migration_database_url)
    assert original.database == "soldesk_test" and original.host == "test-db"
    name = "soldesk_tasks_" + uuid4().hex
    admin = create_engine(original, isolation_level="AUTOCOMMIT")
    with admin.connect() as db:
        db.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    migration_url = original.set(database=name).render_as_string(hide_password=False)
    runtime_url = (
        make_url(pg_settings.database_url).set(database=name).render_as_string(hide_password=False)
    )
    monkeypatch.setenv("MIGRATION_DATABASE_URL", migration_url)
    monkeypatch.setenv("DATABASE_URL", runtime_url)
    settings = pg_settings.model_copy(
        update={"migration_database_url": migration_url, "database_url": runtime_url}
    )
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    engine, runtime = create_engine(migration_url), create_engine(runtime_url)
    try:
        command.upgrade(config, "0011")
        owners = []
        with Session(engine) as db, db.begin():
            for _ in range(2):
                email = uuid4().hex + "@example.test"
                org, _created = create_organization(
                    db, "Empresa fictícia", uuid4().hex, email, "Pessoa fictícia", uuid4().hex
                )
                user = db.scalar(select(User).where(User.email == email))
                client = Client(
                    organization_id=org.id, name="Cliente fictício", name_key="ficticio"
                )
                db.add(client)
                db.flush()
                owners.append((org.id, user.id, client.id))
                db.execute(
                    text("""INSERT INTO record
                  (id,organization_id,client_id,author_id,type,texto_original,status,revision,
                   ocorrido_em,enviado_em,category,system)
                  VALUES (:id,:org,:client,:author,'finalizacao','Relato fictício','confirmado',1,
                    '2026-01-02T03:04:05Z','2026-01-03T03:04:05Z','','Legado fictício')"""),
                    {"id": str(uuid4()), "org": org.id, "client": client.id, "author": user.id},
                )
        with engine.connect() as db:
            before = (
                db.execute(text("SELECT to_jsonb(r) FROM record r ORDER BY id")).scalars().all()
            )
        migrate(settings)
        with engine.connect() as db:
            assert (
                db.execute(text("SELECT to_jsonb(r) FROM record r ORDER BY id")).scalars().all()
                == before
            )
            assert db.scalar(text("SELECT count(*) FROM task")) == 0
        command.downgrade(config, "0011")
        migrate(settings)
        tasks = []
        with engine.begin() as db:
            for org, user, client in owners:
                identifier = str(uuid4())
                tasks.append(identifier)
                db.execute(
                    text("""INSERT INTO task
                  (id,organization_id,author_id,assignee_id,client_id,title,prevista_para,
                   criado_em,atualizado_em) VALUES
                  (:id,:org,:user,:user,:client,'Tarefa fictícia','2026-11-18',now(),now())"""),
                    {"id": identifier, "org": org, "user": user, "client": client},
                )
        for (org, _user, _client), identifier in zip(owners, tasks, strict=True):
            with runtime.begin() as db:
                db.execute(text("SELECT set_config('app.organization_id',:org,true)"), {"org": org})
                assert db.execute(text("SELECT id FROM task")).scalars().all() == [identifier]
        with pytest.raises(RuntimeError, match="preserve"):
            command.downgrade(config, "0011")
        with engine.connect() as db:
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0014a"
            assert (
                db.execute(text("SELECT to_jsonb(r) FROM record r ORDER BY id")).scalars().all()
                == before
            )
            assert db.scalar(text("SELECT count(*) FROM task")) == 2
    finally:
        runtime.dispose()
        engine.dispose()
    # Banco fictício permanece no tmpfs test-db; não há DROP DATABASE.
