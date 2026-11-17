"""Validação independente: snapshots materiais e eventos humanos append-only."""

import hashlib
import json
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0006a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE UNIQUE INDEX record_version_validation_ref "
        "ON record_version(organization_id,record_id,id)"
    )
    op.execute("""CREATE TABLE record_content_version (
        id varchar(36) PRIMARY KEY, organization_id varchar(36) NOT NULL,
        record_id varchar(36) NOT NULL, record_revision integer NOT NULL CHECK(record_revision>0),
        source_version_id varchar(36) NOT NULL, canonical_snapshot text NOT NULL,
        content_hash varchar(64) NOT NULL, criado_em timestamptz NOT NULL DEFAULT now(),
        UNIQUE(record_id,record_revision), UNIQUE(organization_id,record_id,id,content_hash),
        FOREIGN KEY(organization_id,record_id) REFERENCES record(organization_id,id),
        FOREIGN KEY(organization_id,record_id,source_version_id)
            REFERENCES record_version(organization_id,record_id,id),
        CHECK(jsonb_typeof(canonical_snapshot::jsonb)='object'),
        CHECK(content_hash=encode(sha256(convert_to(canonical_snapshot,'UTF8')),'hex'))
    )""")
    op.execute("""CREATE TABLE content_validation (
        id varchar(36) PRIMARY KEY, organization_id varchar(36) NOT NULL,
        record_id varchar(36) NOT NULL, version_id varchar(36) NOT NULL,
        content_hash varchar(64) NOT NULL, validated_by varchar(36) NOT NULL,
        validado_em timestamptz NOT NULL DEFAULT now(), UNIQUE(version_id,validated_by),
        FOREIGN KEY(organization_id,record_id,version_id,content_hash)
            REFERENCES record_content_version(organization_id,record_id,id,content_hash),
        FOREIGN KEY(organization_id,validated_by)
            REFERENCES organization_membership(organization_id,user_id)
    )""")
    for table in ("record_content_version", "content_validation"):
        op.execute(f"CREATE INDEX {table}_record ON {table}(organization_id,record_id)")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        tenant = "organization_id=nullif(current_setting('app.organization_id',true),'')"
        op.execute(f"CREATE POLICY tenant ON {table} USING ({tenant}) WITH CHECK ({tenant})")
    op.execute("""CREATE FUNCTION public.preserve_content_validation() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        BEGIN RAISE EXCEPTION 'Versões e validações são imutáveis'; END $$""")
    for table in ("record_content_version", "content_validation"):
        op.execute(
            f"CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION public.preserve_content_validation()"
        )
    # Importar o conteúdo atual não cria nenhuma validação nem autoria histórica nova.
    fields = (
        "client_id",
        "type",
        "texto_original",
        "texto_organizado",
        "ditado_texto",
        "ocorrido_em",
        "category",
        "system",
    )
    audio_fields = (
        "id",
        "raw_text",
        "normalized_text",
        "organized_text",
        "segments",
        "warnings",
        "sections",
    )
    db = op.get_bind()
    rows = db.execute(
        sa.text("""SELECT r.id,r.organization_id,r.revision,v.id AS version_id,
        v.snapshot,to_jsonb(r) AS current_record,
        (SELECT to_jsonb(j) FROM audio_job j WHERE j.record_id=r.id
         AND j.organization_id=r.organization_id ORDER BY j.criado_em DESC,j.id DESC LIMIT 1) AS job
        FROM record r JOIN record_version v ON v.record_id=r.id
        AND v.organization_id=r.organization_id AND v.revision=r.revision""")
    ).mappings()
    for row in rows:
        current = row["current_record"]
        current["ocorrido_em"] = row["snapshot"]["ocorrido_em"]
        job = row["job"]
        snapshot = {
            "record": {key: current.get(key) for key in fields},
            "transcription": (
                {key: job.get(key) for key in audio_fields}
                if job and job["raw_text"] is not None and job["status"] != "descartado"
                else None
            ),
        }
        canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        db.execute(
            sa.text("""INSERT INTO record_content_version
            (id,organization_id,record_id,record_revision,source_version_id,canonical_snapshot,content_hash)
            VALUES (:id,:org,:record,:revision,:source,:snapshot,:hash)"""),
            {
                "id": str(uuid4()),
                "org": row["organization_id"],
                "record": row["id"],
                "revision": row["revision"],
                "source": row["version_id"],
                "snapshot": canonical,
                "hash": hashlib.sha256(canonical.encode()).hexdigest(),
            },
        )


def downgrade():
    db = op.get_bind()
    if db.scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM record_content_version) "
            "OR EXISTS(SELECT 1 FROM content_validation)"
        )
    ):
        raise RuntimeError("Reversão bloqueada: preserve as versões e validações existentes")
    for table in ("content_validation", "record_content_version"):
        op.drop_table(table)
    op.execute("DROP FUNCTION public.preserve_content_validation()")
    op.execute("DROP INDEX record_version_validation_ref")
