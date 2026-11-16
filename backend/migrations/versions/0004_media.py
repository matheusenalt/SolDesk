"""Arquivos privados e processamento assíncrono, sem alteração de fatos anteriores."""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    for statement in (
        Path(__file__).with_name("0004_schema.sql").read_text(encoding="utf-8").split(";")
    ):
        if statement.strip():
            op.execute(statement)
    op.add_column("record", sa.Column("template_version_id", sa.String(36), nullable=True))
    op.add_column("record", sa.Column("ditado_texto", sa.Text(), nullable=True))
    tenant = "organization_id = nullif(current_setting('app.organization_id', true), '')"
    for name in ("attachment", "audio_job", "template_version", "glossary_term"):
        op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant ON {name} USING ({tenant}) WITH CHECK ({tenant})")
    for table, fields in {
        "attachment": [("record_id", "record"), ("ticket_id", "ticket"), ("client_id", "client")],
        "audio_job": [
            ("record_id", "record"),
            ("attachment_id", "attachment"),
            ("template_id", "template_version"),
        ],
        "record": [("template_version_id", "template_version")],
    }.items():
        for field, target in fields:
            op.create_foreign_key(
                f"{table}_{field}_media_tenant",
                table,
                target,
                ["organization_id", field],
                ["organization_id", "id"],
            )
    op.execute(
        "ALTER TABLE attachment ADD CONSTRAINT attachment_owner CHECK "
        "((owner_type='client' AND client_id IS NOT NULL AND ticket_id IS NULL "
        "AND record_id IS NULL) OR (owner_type='ticket' AND ticket_id IS NOT NULL "
        "AND client_id IS NULL AND record_id IS NULL) OR (owner_type='record' "
        "AND record_id IS NOT NULL AND client_id IS NULL AND ticket_id IS NULL))"
    )
    op.execute(
        "ALTER TABLE audio_job ADD CONSTRAINT audio_job_status CHECK "
        "(status IN ('aguardando','processando','concluido','erro','descartado'))"
    )
    op.execute(
        "CREATE UNIQUE INDEX one_active_audio ON audio_job(record_id) "
        "WHERE status IN ('aguardando','processando')"
    )
    op.execute(
        "CREATE INDEX audio_dispatch ON audio_job(organization_id,status,proxima_tentativa_em)"
    )
    op.execute("""CREATE FUNCTION public.media_organizations() RETURNS SETOF text
        LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public
        AS $$ SELECT DISTINCT organization_id::text FROM public.attachment $$""")
    op.execute("REVOKE ALL ON FUNCTION public.media_organizations() FROM PUBLIC")
    # Ditado é evidência do dispositivo e não deve mudar após a criação.
    op.execute("""CREATE FUNCTION public.preserve_dictation() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        BEGIN
          IF NEW.ditado_texto IS DISTINCT FROM OLD.ditado_texto THEN
            RAISE EXCEPTION 'Ditado original é imutável';
          END IF;
          RETURN NEW;
        END $$""")
    op.execute(
        "CREATE TRIGGER record_dictation BEFORE UPDATE ON record FOR EACH ROW "
        "EXECUTE FUNCTION public.preserve_dictation()"
    )


def downgrade():
    raise RuntimeError("Reversão destrutiva desabilitada; preserve arquivos e histórico")
