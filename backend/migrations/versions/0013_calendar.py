"""Eventos próprios e índices da projeção; nenhum backfill das fontes."""

from alembic import op
from sqlalchemy import text

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE ticket ADD COLUMN prazo_em timestamptz")
    op.execute("""CREATE TABLE calendar_event (
      id varchar(36) PRIMARY KEY,
      organization_id varchar(36) NOT NULL REFERENCES organization(id),
      author_id varchar(36) NOT NULL, assignee_id varchar(36) NOT NULL, client_id varchar(36),
      title varchar(200) NOT NULL CHECK(length(btrim(title))>0),
      description text NOT NULL DEFAULT '',
      data date NOT NULL, inicio_em timestamptz, fim_em timestamptz,
      status varchar(16) NOT NULL DEFAULT 'ativo' CHECK(status IN ('ativo','cancelado')),
      revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
      criado_em timestamptz NOT NULL, atualizado_em timestamptz NOT NULL, cancelado_em timestamptz,
      UNIQUE(organization_id,id), CHECK((status='cancelado')=(cancelado_em IS NOT NULL)),
      CHECK(fim_em IS NULL OR (inicio_em IS NOT NULL AND fim_em>inicio_em)),
      FOREIGN KEY(organization_id,author_id)
        REFERENCES organization_membership(organization_id,user_id),
      FOREIGN KEY(organization_id,assignee_id)
        REFERENCES organization_membership(organization_id,user_id),
      FOREIGN KEY(organization_id,client_id) REFERENCES client(organization_id,id)
    )""")
    op.execute("""CREATE TABLE calendar_participant (
      id varchar(36) PRIMARY KEY, organization_id varchar(36) NOT NULL REFERENCES organization(id),
      event_id varchar(36) NOT NULL, user_id varchar(36) NOT NULL,
      active boolean NOT NULL DEFAULT true,
      UNIQUE(event_id,user_id),
      FOREIGN KEY(organization_id,event_id) REFERENCES calendar_event(organization_id,id),
      FOREIGN KEY(organization_id,user_id)
        REFERENCES organization_membership(organization_id,user_id)
    )""")
    op.execute("""CREATE TABLE calendar_version (
      id varchar(36) PRIMARY KEY, organization_id varchar(36) NOT NULL REFERENCES organization(id),
      event_id varchar(36) NOT NULL, actor_id varchar(36) NOT NULL, revision integer NOT NULL,
      action varchar(24) NOT NULL, reason text NOT NULL DEFAULT '',
      before json NOT NULL, after json NOT NULL, ocorrido_em timestamptz NOT NULL,
      UNIQUE(event_id,revision),
      FOREIGN KEY(organization_id,event_id) REFERENCES calendar_event(organization_id,id),
      FOREIGN KEY(organization_id,actor_id)
        REFERENCES organization_membership(organization_id,user_id)
    )""")
    op.execute("""CREATE TABLE calendar_receipt (
      id varchar(36) PRIMARY KEY, organization_id varchar(36) NOT NULL REFERENCES organization(id),
      event_id varchar(36) NOT NULL, actor_id varchar(36) NOT NULL,
      key_hash varchar(64) NOT NULL, fingerprint varchar(64) NOT NULL, snapshot json NOT NULL,
      criado_em timestamptz NOT NULL, UNIQUE(organization_id,actor_id,key_hash),
      FOREIGN KEY(organization_id,event_id) REFERENCES calendar_event(organization_id,id),
      FOREIGN KEY(organization_id,actor_id)
        REFERENCES organization_membership(organization_id,user_id)
    )""")
    for table in ("calendar_event", "calendar_participant", "calendar_version", "calendar_receipt"):
        tenant = "organization_id = nullif(current_setting('app.organization_id',true),'')"
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant ON {table} USING ({tenant}) WITH CHECK ({tenant})")
        op.execute(f"CREATE INDEX {table}_organization ON {table}(organization_id)")
    for table in ("calendar_version", "calendar_receipt"):
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION public.preserve_content_validation()"
        )
    op.execute(
        "CREATE INDEX calendar_participant_reader ON calendar_participant"
        "(organization_id,user_id,event_id) WHERE active"
    )
    for table, column, suffix, condition in (
        ("task", "prevista_para", "day", "agendado_em IS NULL"),
        ("task", "agendado_em", "instant", "agendado_em IS NOT NULL"),
        ("ticket", "prazo_em", "instant", "prazo_em IS NOT NULL"),
        ("attendance", "retomada_em", "instant", "retomada_em IS NOT NULL"),
        ("calendar_event", "data", "day", "inicio_em IS NULL"),
        ("calendar_event", "inicio_em", "start", "inicio_em IS NOT NULL"),
        ("calendar_event", "fim_em", "end", "fim_em IS NOT NULL"),
    ):
        op.execute(
            f"CREATE INDEX {table}_calendar_{suffix} ON {table}"
            f"(organization_id,{column}) WHERE {condition}"
        )


def downgrade():
    db = op.get_bind()
    for table in ("calendar_event", "calendar_participant", "calendar_version", "calendar_receipt"):
        if db.scalar(text(f"SELECT EXISTS(SELECT 1 FROM {table})")):
            raise RuntimeError("Reversão bloqueada: preserve a agenda e seu histórico")
    if db.scalar(text("SELECT EXISTS(SELECT 1 FROM ticket WHERE prazo_em IS NOT NULL)")):
        raise RuntimeError("Reversão bloqueada: preserve os prazos dos chamados")
    for table, suffix in (
        ("task", "day"),
        ("task", "instant"),
        ("ticket", "instant"),
        ("attendance", "instant"),
    ):
        op.execute(f"DROP INDEX {table}_calendar_{suffix}")
    for table in ("calendar_receipt", "calendar_version", "calendar_participant", "calendar_event"):
        op.execute(f"DROP TABLE {table}")
    op.execute("ALTER TABLE ticket DROP COLUMN prazo_em")
