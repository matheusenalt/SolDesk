"""Catálogo sem reconciliação automática ou alteração dos textos existentes."""

from alembic import op
from sqlalchemy import text

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(r"""CREATE TABLE software_system (
        id varchar(36) PRIMARY KEY,
        organization_id varchar(36) NOT NULL REFERENCES organization(id),
        name varchar(160) NOT NULL,
        name_key text GENERATED ALWAYS AS
          (regexp_replace(btrim(public.search_normalize(name)), '\s+', ' ', 'g')) STORED,
        description text NOT NULL DEFAULT '', manufacturer varchar(160) NOT NULL DEFAULT '',
        category varchar(80) NOT NULL DEFAULT '', notes text NOT NULL DEFAULT '',
        situation varchar(16) NOT NULL DEFAULT 'ativo' CHECK(situation IN ('ativo','inativo')),
        revision integer NOT NULL DEFAULT 1 CHECK(revision > 0),
        UNIQUE(organization_id,id), UNIQUE(organization_id,name_key), CHECK(length(name_key)>0)
    )""")
    op.execute("""CREATE TABLE client_system (
        id varchar(36) PRIMARY KEY,
        organization_id varchar(36) NOT NULL REFERENCES organization(id),
        client_id varchar(36) NOT NULL, system_id varchar(36) NOT NULL,
        version_in_use varchar(160) NOT NULL DEFAULT '', notes text NOT NULL DEFAULT '',
        revision integer NOT NULL DEFAULT 1 CHECK(revision > 0),
        UNIQUE(organization_id,client_id,system_id),
        FOREIGN KEY(organization_id,client_id) REFERENCES client(organization_id,id),
        FOREIGN KEY(organization_id,system_id) REFERENCES software_system(organization_id,id)
    )""")
    op.execute("""CREATE TABLE system_reconciliation (
        id varchar(36) PRIMARY KEY,
        organization_id varchar(36) NOT NULL REFERENCES organization(id),
        actor_id varchar(36) NOT NULL, kind varchar(16) NOT NULL
          CHECK(kind IN ('record','ticket','article')), entity_id varchar(36) NOT NULL,
        decision varchar(16) NOT NULL CHECK(decision IN ('aceitar','rejeitar')),
        legacy_text varchar(80) NOT NULL, system_id varchar(36),
        key_hash varchar(64) NOT NULL, fingerprint varchar(64) NOT NULL,
        snapshot json NOT NULL, criado_em timestamptz NOT NULL,
        UNIQUE(organization_id,actor_id,key_hash),
        FOREIGN KEY(organization_id,actor_id)
          REFERENCES organization_membership(organization_id,user_id),
        FOREIGN KEY(organization_id,system_id) REFERENCES software_system(organization_id,id),
        CHECK((decision='aceitar')=(system_id IS NOT NULL))
    )""")
    for table in ("software_system", "client_system", "system_reconciliation"):
        tenant = "organization_id = nullif(current_setting('app.organization_id', true), '')"
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant ON {table} USING ({tenant}) WITH CHECK ({tenant})")
        op.execute(f"CREATE INDEX {table}_organization ON {table}(organization_id)")
    op.execute(
        "CREATE TRIGGER system_decision_append_only BEFORE UPDATE OR DELETE "
        "ON system_reconciliation FOR EACH ROW "
        "EXECUTE FUNCTION public.preserve_content_validation()"
    )
    for table in ("record", "ticket", "knowledge_article"):
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN system_id varchar(36), "
            "ADD COLUMN system_name_snapshot varchar(160), "
            "ADD COLUMN legacy_system_snapshot varchar(80)"
        )
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_system_tenant "
            "FOREIGN KEY(organization_id,system_id) "
            "REFERENCES software_system(organization_id,id)"
        )
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_system_snapshot CHECK "
            "((system_id IS NULL AND system_name_snapshot IS NULL "
            "AND legacy_system_snapshot IS NULL) "
            "OR (system_id IS NOT NULL AND system_name_snapshot IS NOT NULL "
            "AND legacy_system_snapshot IS NOT NULL))"
        )
        op.execute(f"CREATE INDEX {table}_system ON {table}(organization_id,system_id)")
    article_search(True)


def article_search(with_snapshot):
    extra = ",NEW.system_name_snapshot" if with_snapshot else ""
    op.execute(f"""CREATE OR REPLACE FUNCTION public.refresh_article_search() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        BEGIN
          NEW.search_text := public.unaccent(lower(concat_ws(' ',NEW.title,NEW.problem,
            NEW.context,NEW.confirmed_cause,NEW.procedure,NEW.result,NEW.text,
            NEW.keywords::text,NEW.category,NEW.system{extra})));
          NEW.search_vector := to_tsvector('portuguese',NEW.search_text);
          RETURN NEW;
        END $$""")


def downgrade():
    db = op.get_bind()
    for table in ("software_system", "client_system", "system_reconciliation"):
        if db.scalar(text(f"SELECT EXISTS(SELECT 1 FROM {table})")):
            raise RuntimeError("Reversão bloqueada: preserve o catálogo e suas decisões")
    article_search(False)
    for table in ("record", "ticket", "knowledge_article"):
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT {table}_system_tenant, "
            f"DROP CONSTRAINT {table}_system_snapshot, "
            "DROP COLUMN system_id, DROP COLUMN system_name_snapshot, "
            "DROP COLUMN legacy_system_snapshot"
        )
    for table in ("system_reconciliation", "client_system", "software_system"):
        op.execute(f"DROP TABLE {table}")
