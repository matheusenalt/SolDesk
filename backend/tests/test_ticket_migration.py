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


def test_legacy_ticket_mapping_is_additive_and_tenant_receipts_are_isolated(
    pg_settings, monkeypatch
):
    original = make_url(pg_settings.migration_database_url)
    assert original.database == "soldesk_test" and original.host == "test-db"
    name = "soldesk_tickets_" + uuid4().hex
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
        command.upgrade(config, "0013")
        owners = []
        with Session(engine) as db, db.begin():
            for state in ("resolvido", "encerrado"):
                email = uuid4().hex + "@example.test"
                org, _ = create_organization(
                    db,
                    "Empresa fictícia de chamados",
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
                owners.append((org.id, user.id, ticket_id))
                db.execute(
                    text("""INSERT INTO record
                  (id,organization_id,client_id,author_id,type,texto_original,status,revision,
                   ocorrido_em,enviado_em,category,system)
                  VALUES (:id,:org,:client,:user,'chamado','Relato legado fictício','enviado',1,
                    '2026-01-02T03:04:05Z','2026-01-03T03:04:05Z','','')"""),
                    {"id": record_id, "org": org.id, "client": client.id, "user": user.id},
                )
                db.execute(
                    text("""INSERT INTO ticket
                  (id,organization_id,record_id,client_id,code,description,opened_by,assignee_id,
                   priority,category,system,status,revision,reopen_count,aberto_em)
                  VALUES (:id,:org,:record,:client,'SD-0001','Chamado legado fictício',:user,:user,
                    'normal','','',:state,1,0,'2026-01-02T03:04:05Z')"""),
                    {
                        "id": ticket_id,
                        "org": org.id,
                        "record": record_id,
                        "client": client.id,
                        "user": user.id,
                        "state": state,
                    },
                )
        with engine.connect() as db:
            before = (
                db.execute(text("SELECT to_jsonb(t) FROM ticket t ORDER BY id")).scalars().all()
            )
        migrate(settings)
        with engine.connect() as db:
            after = (
                db.execute(
                    text("""SELECT to_jsonb(t)-ARRAY['workflow_state',
              'completion_description','auto_accept','ultima_interacao_em']
              FROM ticket t ORDER BY id""")
                )
                .scalars()
                .all()
            )
            assert before == after
            assert set(db.execute(text("SELECT workflow_state FROM ticket")).scalars()) == {
                "aguardando_validacao",
                "concluido",
            }
            assert (
                db.scalar(text("SELECT count(*) FROM ticket WHERE completion_description<>''")) == 0
            )
        command.downgrade(config, "0013")
        migrate(settings)
        with engine.begin() as db:
            for org, user, ticket_id in owners:
                db.execute(
                    text("""INSERT INTO ticket_receipt
                  (id,organization_id,actor_id,ticket_id,key_hash,fingerprint,snapshot,criado_em)
                  VALUES (:id,:org,:user,:ticket,'ficticio','ficticio','{}',now())"""),
                    {"id": str(uuid4()), "org": org, "user": user, "ticket": ticket_id},
                )
        for org, _user, ticket_id in owners:
            with runtime.begin() as db:
                db.execute(text("SELECT set_config('app.organization_id',:org,true)"), {"org": org})
                assert db.execute(text("SELECT ticket_id FROM ticket_receipt")).scalars().all() == [
                    ticket_id
                ]
        with pytest.raises(RuntimeError, match="preserve"):
            command.downgrade(config, "0013")
    finally:
        runtime.dispose()
        engine.dispose()
