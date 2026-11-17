"""Ciclo de atendimento sem substituir registros ou revisões anteriores."""

from alembic import op
from sqlalchemy import text

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE record ALTER COLUMN client_id DROP NOT NULL")
    op.execute("ALTER TABLE record ADD COLUMN internal_activity boolean NOT NULL DEFAULT false")
    op.execute(
        "ALTER TABLE record ADD CONSTRAINT record_client_or_internal CHECK "
        "(client_id IS NOT NULL OR (internal_activity AND type = 'finalizacao'))"
    )
    op.execute("""CREATE TABLE attendance (
        id varchar(36) PRIMARY KEY REFERENCES record(id),
        organization_id varchar(36) NOT NULL REFERENCES organization(id),
        assignee_id varchar(36) NOT NULL,
        status varchar(32) NOT NULL DEFAULT 'em_andamento',
        next_action text NOT NULL DEFAULT '', retomada_em timestamptz,
        finalizado_em timestamptz, result text NOT NULL DEFAULT '',
        revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
        FOREIGN KEY (organization_id,id) REFERENCES record(organization_id,id),
        FOREIGN KEY (organization_id,assignee_id)
            REFERENCES organization_membership(organization_id,user_id),
        CHECK (status IN ('em_andamento','aguardando_retomada','finalizado')),
        CHECK ((status = 'aguardando_retomada') = (retomada_em IS NOT NULL)),
        CHECK ((status = 'finalizado') = (finalizado_em IS NOT NULL)),
        CHECK (status <> 'finalizado' OR length(trim(result)) > 0)
    )""")
    op.execute(
        "CREATE INDEX attendance_pending "
        "ON attendance(organization_id,assignee_id,status,retomada_em)"
    )
    op.execute("ALTER TABLE attendance ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE attendance FORCE ROW LEVEL SECURITY")
    tenant = "organization_id = nullif(current_setting('app.organization_id', true), '')"
    op.execute(f"CREATE POLICY tenant ON attendance USING ({tenant}) WITH CHECK ({tenant})")
    op.execute("""CREATE FUNCTION public.preserve_internal_activity() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        BEGIN
          IF NEW.internal_activity IS DISTINCT FROM OLD.internal_activity THEN
            RAISE EXCEPTION 'A natureza original do registro é imutável';
          END IF;
          RETURN NEW;
        END $$""")
    op.execute(
        "CREATE TRIGGER record_internal BEFORE UPDATE ON record FOR EACH ROW "
        "EXECUTE FUNCTION public.preserve_internal_activity()"
    )


def downgrade():
    db = op.get_bind()
    if db.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM attendance) OR EXISTS "
            "(SELECT 1 FROM record WHERE internal_activity OR client_id IS NULL)"
        )
    ):
        raise RuntimeError("Reversão bloqueada: preserve o histórico de atividades")
    op.execute("DROP TRIGGER record_internal ON record")
    op.execute("DROP FUNCTION public.preserve_internal_activity()")
    op.execute("DROP TABLE attendance")
    op.execute("ALTER TABLE record DROP CONSTRAINT record_client_or_internal")
    op.execute("ALTER TABLE record DROP COLUMN internal_activity")
    op.execute("ALTER TABLE record ALTER COLUMN client_id SET NOT NULL")
