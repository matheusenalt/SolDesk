"""Migração da agenda somente em banco novo no cluster isolado de testes."""

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


def test_calendar_migration_preserves_sources_and_guards_both_extensions(pg_settings, monkeypatch):
    original = make_url(pg_settings.migration_database_url)
    assert original.database == "soldesk_test" and original.host == "test-db"
    name = "soldesk_calendar_" + uuid4().hex
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
        command.upgrade(config, "0012")
        owners = []
        with Session(engine) as db, db.begin():
            for _ in range(2):
                email = uuid4().hex + "@example.test"
                org, _created = create_organization(
                    db,
                    "Empresa fictícia da agenda",
                    uuid4().hex,
                    email,
                    "Pessoa fictícia",
                    uuid4().hex,
                )
                user = db.scalar(select(User).where(User.email == email))
                client = Client(
                    organization_id=org.id, name="Cliente fictício", name_key="ficticio"
                )
                db.add(client)
                db.flush()
                record_id, ticket_id = str(uuid4()), str(uuid4())
                owners.append((org.id, user.id, client.id, ticket_id))
                db.execute(
                    text("""INSERT INTO record
                  (id,organization_id,client_id,author_id,type,texto_original,status,revision,
                   ocorrido_em,enviado_em,category,system)
                  VALUES (:id,:org,:client,:author,'chamado','Relato fictício','enviado',1,
                    '2026-01-02T03:04:05Z','2026-01-03T03:04:05Z','','Legado fictício')"""),
                    {"id": record_id, "org": org.id, "client": client.id, "author": user.id},
                )
                db.execute(
                    text("""INSERT INTO ticket
                  (id,organization_id,record_id,client_id,code,description,opened_by,assignee_id,
                   priority,category,system,status,revision,reopen_count,aberto_em)
                  VALUES (:id,:org,:record,:client,'SD-0001','Chamado fictício',:user,:user,
                    'normal','','','aberto',1,0,'2026-01-02T03:04:05Z')"""),
                    {
                        "id": ticket_id,
                        "org": org.id,
                        "record": record_id,
                        "client": client.id,
                        "user": user.id,
                    },
                )
                db.execute(
                    text("""INSERT INTO task
                  (id,organization_id,author_id,assignee_id,title,prevista_para,criado_em,atualizado_em)
                  VALUES (:id,:org,:user,:user,'Ação fictícia','2026-11-18',now(),now())"""),
                    {"id": str(uuid4()), "org": org.id, "user": user.id},
                )
        with engine.connect() as db:
            before = {
                table: db.execute(text(f"SELECT to_jsonb(t) FROM {table} t ORDER BY id"))
                .scalars()
                .all()
                for table in ("record", "ticket", "task")
            }
        migrate(settings)
        with engine.connect() as db:
            for table in before:
                expression = "to_jsonb(t)-'prazo_em'" if table == "ticket" else "to_jsonb(t)"
                assert (
                    db.execute(text(f"SELECT {expression} FROM {table} t ORDER BY id"))
                    .scalars()
                    .all()
                    == before[table]
                )
            assert db.scalar(text("SELECT count(*) FROM calendar_event")) == 0
        command.downgrade(config, "0012")
        migrate(settings)
        # A guarda também protege prazos, mesmo com agenda ainda vazia.
        with engine.begin() as db:
            db.execute(text("UPDATE ticket SET prazo_em='2030-01-02T12:00Z'"))
        with pytest.raises(RuntimeError, match="prazos"):
            command.downgrade(config, "0012")
        events = []
        with engine.begin() as db:
            for org, user, client, _ticket in owners:
                identifier = str(uuid4())
                events.append(identifier)
                db.execute(
                    text("""INSERT INTO calendar_event
                  (id,organization_id,author_id,assignee_id,client_id,title,data,criado_em,atualizado_em)
                  VALUES (:id,:org,:user,:user,:client,'Agenda fictícia',
                    '2026-11-18',now(),now())"""),
                    {"id": identifier, "org": org, "user": user, "client": client},
                )
        for (org, _user, _client, _ticket), identifier in zip(owners, events, strict=True):
            with runtime.begin() as db:
                db.execute(text("SELECT set_config('app.organization_id',:org,true)"), {"org": org})
                assert db.execute(text("SELECT id FROM calendar_event")).scalars().all() == [
                    identifier
                ]
        with pytest.raises(RuntimeError, match="agenda"):
            command.downgrade(config, "0012")
        with engine.connect() as db:
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0013"
            assert db.scalar(text("SELECT count(*) FROM calendar_event")) == 2
            assert db.scalar(text("SELECT count(*) FROM task")) == 2
    finally:
        runtime.dispose()
        engine.dispose()
    # Banco fictício permanece no tmpfs test-db; sem DROP DATABASE.
