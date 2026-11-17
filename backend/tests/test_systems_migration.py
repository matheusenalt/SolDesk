"""Migração em banco descartável novo do cluster test-db; nunca no banco da aplicação."""

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
from app.system_models import ClientSystem, SoftwareSystem

pg_settings = identity.pg_settings


def test_upgrade_0010_preserves_variants_and_requires_manual_links(pg_settings, monkeypatch):
    original = make_url(pg_settings.migration_database_url)
    assert original.database == "soldesk_test" and original.host == "test-db"
    name = "soldesk_systems_" + uuid4().hex
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
        command.upgrade(config, "0010")
        organizations = []
        variants = ["ERP Fictício", "erp ficticio", " ERP  Fictício Pro ", ""]
        with Session(engine) as db, db.begin():
            for _number in range(2):
                email = f"migration-{uuid4().hex}@example.test"
                org, _ = create_organization(
                    db,
                    "Empresa fictícia de catálogo",
                    uuid4().hex,
                    email,
                    "Pessoa fictícia",
                    uuid4().hex,
                )
                author = db.scalar(select(User).where(User.email == email))
                client = Client(
                    organization_id=org.id, name="Cliente fictício", name_key="cliente ficticio"
                )
                db.add(client)
                db.flush()
                organizations.append((org.id, client.id))
                for raw in variants:
                    db.execute(
                        text("""INSERT INTO record
                      (id,organization_id,client_id,author_id,type,texto_original,status,revision,
                       ocorrido_em,enviado_em,category,system)
                      VALUES (:id,:org,:client,:author,'finalizacao','Relato legado fictício',
                       'confirmado',1,'2026-01-02T03:04:05Z','2026-01-03T03:04:05Z','',:system)"""),
                        {
                            "id": str(uuid4()),
                            "org": org.id,
                            "client": client.id,
                            "author": author.id,
                            "system": raw,
                        },
                    )
            before = (
                db.execute(text("SELECT to_jsonb(r) FROM record r ORDER BY id")).scalars().all()
            )
        migrate(settings)
        with engine.connect() as db:
            after = (
                db.execute(
                    text("""SELECT to_jsonb(r)-'system_id'
                       -'system_name_snapshot'-'legacy_system_snapshot'
                                     FROM record r ORDER BY id""")
                )
                .scalars()
                .all()
            )
            assert after == before
            assert db.scalar(text("SELECT count(*) FROM record WHERE system_id IS NOT NULL")) == 0
            assert db.scalar(text("SELECT count(*) FROM software_system")) == 0
            assert db.scalar(text("SELECT count(*) FROM system_reconciliation")) == 0
        command.downgrade(config, "0010")  # Só extensão vazia; textos legados permanecem.
        migrate(settings)
        ids = []
        with Session(engine) as db, db.begin():
            for org, client in organizations:
                item = SoftwareSystem(organization_id=org, name="ERP Fictício")
                db.add(item)
                db.flush()
                ids.append(item.id)
                db.add(
                    ClientSystem(
                        organization_id=org,
                        client_id=client,
                        system_id=item.id,
                        version_in_use="2.0",
                    )
                )
        for index, (org, _) in enumerate(organizations):
            with runtime.begin() as db:
                db.execute(text("SELECT set_config('app.organization_id',:org,true)"), {"org": org})
                assert db.execute(text("SELECT id FROM software_system")).scalars().all() == [
                    ids[index]
                ]
                assert db.scalar(text("SELECT count(*) FROM client_system")) == 1
        with pytest.raises(RuntimeError, match="preserve"):
            command.downgrade(config, "0010")
        with engine.connect() as db:
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0012"
            assert db.scalar(text("SELECT count(*) FROM record")) == 8
    finally:
        runtime.dispose()
        engine.dispose()
    # Banco fictício mantido no tmpfs de test-db para inspeção; sem DROP DATABASE.
