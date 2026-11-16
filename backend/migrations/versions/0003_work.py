"""Relatos, revisão própria, chamados e notificações com RLS."""

from pathlib import Path

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    snapshot = Path(__file__).with_name("0003_schema.sql").read_text(encoding="utf-8")
    for statement in snapshot.split(";"):
        if statement.strip():
            op.execute(statement)
    tenant = "organization_id = nullif(current_setting('app.organization_id', true), '')"
    own = "user_id = nullif(current_setting('app.user_id', true), '')"
    names = (
        "record",
        "record_version",
        "ticket_sequence",
        "ticket",
        "ticket_participant",
        "ticket_comment",
        "ticket_event",
        "ticket_interval",
        "knowledge_article",
        "notification",
        "request_receipt",
    )
    for name in names:
        op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
        if name in {"notification", "request_receipt"}:
            op.execute(f"CREATE POLICY own_read ON {name} FOR SELECT USING ({tenant} AND {own})")
            insert = tenant if name == "notification" else f"{tenant} AND {own}"
            op.execute(f"CREATE POLICY own_insert ON {name} FOR INSERT WITH CHECK ({insert})")
            if name == "notification":
                op.execute(
                    f"CREATE POLICY own_update ON {name} FOR UPDATE "
                    f"USING ({tenant} AND {own}) WITH CHECK ({tenant} AND {own})"
                )
        else:
            op.execute(f"CREATE POLICY tenant ON {name} USING ({tenant}) WITH CHECK ({tenant})")
    references = {
        "record": [("client_id", "client"), ("origem_record_id", "record")],
        "ticket": [("client_id", "client"), ("record_id", "record")],
        "record_version": [("record_id", "record")],
        "ticket_participant": [("ticket_id", "ticket")],
        "ticket_comment": [("ticket_id", "ticket")],
        "ticket_event": [("ticket_id", "ticket")],
        "ticket_interval": [("ticket_id", "ticket")],
        "knowledge_article": [("record_id", "record")],
        "request_receipt": [("record_id", "record")],
    }
    for table, fields in references.items():
        for field, target in fields:
            op.create_foreign_key(
                f"{table}_{field}_tenant",
                table,
                target,
                ["organization_id", field],
                ["organization_id", "id"],
            )
    for table, field in (
        ("record", "author_id"),
        ("record", "revisado_por"),
        ("ticket", "assignee_id"),
        ("ticket_participant", "user_id"),
        ("notification", "user_id"),
    ):
        op.create_foreign_key(
            f"{table}_{field}_member",
            table,
            "organization_membership",
            ["organization_id", field],
            ["organization_id", "user_id"],
        )
    for field, target in (("ticket_id", "ticket"), ("article_id", "knowledge_article")):
        op.create_foreign_key(
            f"record_{field}_tenant",
            "record",
            target,
            ["organization_id", field],
            ["organization_id", "id"],
        )
    op.execute(
        "CREATE UNIQUE INDEX one_open_ticket_interval ON ticket_interval(ticket_id) "
        "WHERE saida_em IS NULL"
    )
    op.execute(
        "CREATE INDEX record_client_time ON record(organization_id,client_id,ocorrido_em,id)"
    )
    op.execute(
        "CREATE INDEX notification_unread ON notification(organization_id,user_id,criado_em) "
        "WHERE lida_em IS NULL"
    )
    op.execute(
        "ALTER TABLE record ADD CONSTRAINT record_type "
        "CHECK (type IN ('finalizacao','chamado','conhecimento'))"
    )
    op.execute(
        "ALTER TABLE record ADD CONSTRAINT record_status CHECK (status IN "
        "('rascunho','enviado','processando','aguardando_revisao','confirmado',"
        "'publicado','erro','cancelado'))"
    )
    op.execute("ALTER TABLE record ADD CONSTRAINT record_revision CHECK (revision > 0)")
    op.execute(
        "ALTER TABLE ticket ADD CONSTRAINT ticket_status CHECK (status IN "
        "('aberto','em_andamento','aguardando_esclarecimento','aguardando_terceiros',"
        "'resolvido','encerrado','reaberto'))"
    )
    op.execute(
        "ALTER TABLE ticket ADD CONSTRAINT ticket_priority "
        "CHECK (priority IN ('baixa','normal','alta','urgente'))"
    )
    op.execute(
        "ALTER TABLE ticket_interval ADD CONSTRAINT valid_interval "
        "CHECK (saida_em IS NULL OR saida_em >= entrada_em)"
    )
    op.execute("""CREATE FUNCTION public.preserve_record_facts() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        BEGIN
          IF NEW.enviado_em IS DISTINCT FROM OLD.enviado_em
             OR NEW.texto_original IS DISTINCT FROM OLD.texto_original
             OR NEW.author_id IS DISTINCT FROM OLD.author_id
             OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
             OR NEW.client_id IS DISTINCT FROM OLD.client_id
             OR NEW.type IS DISTINCT FROM OLD.type
             OR NEW.origem_record_id IS DISTINCT FROM OLD.origem_record_id
             OR NEW.capturado_em IS DISTINCT FROM OLD.capturado_em THEN
            RAISE EXCEPTION 'Fatos originais do registro são imutáveis';
          END IF;
          IF OLD.status IN ('confirmado','publicado','cancelado') AND
            (NEW.ocorrido_em IS DISTINCT FROM OLD.ocorrido_em
             OR NEW.texto_organizado IS DISTINCT FROM OLD.texto_organizado
             OR NEW.revisado_em IS DISTINCT FROM OLD.revisado_em
             OR NEW.revisado_por IS DISTINCT FROM OLD.revisado_por) THEN
            RAISE EXCEPTION 'Registro revisado não pode ter conteúdo substituído';
          END IF;
          RETURN NEW;
        END $$""")
    op.execute(
        "CREATE TRIGGER record_facts BEFORE UPDATE ON record "
        "FOR EACH ROW EXECUTE FUNCTION public.preserve_record_facts()"
    )


def downgrade():
    raise RuntimeError("Reversão destrutiva desabilitada; preserve o histórico")
