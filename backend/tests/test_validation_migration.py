"""Upgrade real somente em banco novo dentro do cluster de testes isolado."""

import json
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


def test_upgrade_from_previous_preserves_legacy_and_two_tenants(pg_settings, monkeypatch):
    original = make_url(pg_settings.migration_database_url)
    assert original.database == "soldesk_test"
    name = "soldesk_upgrade_" + uuid4().hex
    admin = create_engine(original, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
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
    engine = create_engine(migration_url)
    runtime = create_engine(runtime_url)
    try:
        command.upgrade(config, "0009")
        # Reversão somente com as tabelas novas vazias; nenhum dado de negócio apagado.
        command.downgrade(config, "0006a")
        organizations = []
        with Session(engine) as db, db.begin():
            for number in range(2):
                email = f"legacy-{number}-{uuid4().hex}@example.test"
                org, _ = create_organization(
                    db, "Empresa legada fictícia", uuid4().hex, email, "Autor fictício", uuid4().hex
                )
                author = db.scalar(select(User).where(User.email == email))
                client = Client(
                    organization_id=org.id,
                    name="Cliente legado fictício",
                    name_key="cliente legado ficticio",
                )
                db.add(client)
                db.flush()
                identifier = str(uuid4())
                db.execute(
                    text("""INSERT INTO record
                    (id,organization_id,client_id,author_id,type,texto_original,texto_organizado,
                     status,revision,ocorrido_em,enviado_em,revisado_em,revisado_por,category,system)
                    VALUES (:id,:org,:client,:author,'finalizacao','Fato legado fictício',
                     'Texto legado revisado','confirmado',1,'2026-01-02T03:04:05Z',
                     '2026-01-03T03:04:05Z','2026-01-04T03:04:05Z',:author,'','')"""),
                    {
                        "id": identifier,
                        "org": org.id,
                        "client": client.id,
                        "author": author.id,
                    },
                )
                snapshot = {"ocorrido_em": "2026-01-02T03:04:05+00:00"}
                db.execute(
                    text("""INSERT INTO record_version
                    (id,organization_id,record_id,revision,actor_id,change,snapshot,criado_em)
                    VALUES (:id,:org,:record,1,:author,'registro_confirmar',
                    CAST(:snapshot AS json),now())"""),
                    {
                        "id": str(uuid4()),
                        "org": org.id,
                        "record": identifier,
                        "author": author.id,
                        "snapshot": json.dumps(snapshot),
                    },
                )
                organizations.append((org.id, author.id, identifier))
            before = (
                db.execute(text("SELECT to_jsonb(r) FROM record r ORDER BY id")).scalars().all()
            )
        migrate(settings)
        for row in before:
            row["internal_activity"] = False
        with engine.connect() as db:
            assert (
                db.execute(text("SELECT to_jsonb(r) FROM record r ORDER BY id")).scalars().all()
                == before
            )
            assert db.scalar(text("SELECT count(*) FROM record_version")) == 2
            assert db.scalar(text("SELECT count(*) FROM record_content_version")) == 2
            assert db.scalar(text("SELECT count(*) FROM content_validation")) == 0
        for org, _user, identifier in organizations:
            with runtime.begin() as db:
                db.execute(text("SELECT set_config('app.organization_id',:org,true)"), {"org": org})
                rows = (
                    db.execute(text("SELECT record_id FROM record_content_version")).scalars().all()
                )
                assert rows == [identifier]
                assert db.scalar(text("SELECT count(*) FROM content_validation")) == 0
        # O ciclo novo não converte atendimentos legados nem altera suas datas.
        command.downgrade(config, "0009")  # Sem atendimento/atividade interna, reversão segura.
        migrate(settings)  # Recriação também reaplica privilégios mínimos do runtime.
        with engine.begin() as db:
            assert db.scalar(text("SELECT count(*) FROM attendance")) == 0
            for org, user, identifier in organizations:
                db.execute(
                    text(
                        "INSERT INTO attendance(id,organization_id,assignee_id) "
                        "VALUES (:id,:org,:user)"
                    ),
                    {"id": identifier, "org": org, "user": user},
                )
        for org, _user, identifier in organizations:
            with runtime.begin() as db:
                db.execute(text("SELECT set_config('app.organization_id',:org,true)"), {"org": org})
                assert db.execute(text("SELECT id FROM attendance")).scalars().all() == [identifier]
        with pytest.raises(RuntimeError, match="preserve"):
            command.downgrade(config, "0006a")  # Guarda impede descartar versões importadas.
    finally:
        runtime.dispose()
        engine.dispose()
    # Banco fictício mantido para inspeção no test-db (tmpfs); sem DROP ou acesso à aplicação.
