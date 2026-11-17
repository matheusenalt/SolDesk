"""Estado alvo derivado preserva estados/eventos legados; conclusão rastreável."""

from alembic import op
from sqlalchemy import text

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE ticket
      ADD COLUMN workflow_state varchar(32) GENERATED ALWAYS AS (CASE status
        WHEN 'aberto' THEN 'novo' WHEN 'resolvido' THEN 'aguardando_validacao'
        WHEN 'encerrado' THEN 'concluido' WHEN 'cancelado' THEN 'cancelado'
        WHEN 'aguardando_esclarecimento' THEN 'aguardando_retorno'
        WHEN 'aguardando_terceiros' THEN 'aguardando_retorno' ELSE 'em_andamento' END) STORED,
      ADD COLUMN completion_description text NOT NULL DEFAULT '',
      ADD COLUMN auto_accept boolean NOT NULL DEFAULT false,
      ADD COLUMN ultima_interacao_em timestamptz DEFAULT now()""")
    op.execute("""UPDATE ticket t SET ultima_interacao_em=greatest(t.aberto_em,
      (SELECT max(e.ocorrido_em) FROM ticket_event e WHERE e.ticket_id=t.id),
      (SELECT max(c.criado_em) FROM ticket_comment c WHERE c.ticket_id=t.id))""")
    op.execute("""CREATE TABLE ticket_receipt (
      id varchar(36) PRIMARY KEY, organization_id varchar(36) NOT NULL REFERENCES organization(id),
      actor_id varchar(36) NOT NULL, ticket_id varchar(36) NOT NULL,
      key_hash varchar(64) NOT NULL, fingerprint varchar(64) NOT NULL, snapshot json NOT NULL,
      criado_em timestamptz NOT NULL, UNIQUE(organization_id,actor_id,key_hash),
      FOREIGN KEY(organization_id,ticket_id) REFERENCES ticket(organization_id,id),
      FOREIGN KEY(organization_id,actor_id)
        REFERENCES organization_membership(organization_id,user_id)
    )""")
    op.execute("ALTER TABLE ticket_receipt ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ticket_receipt FORCE ROW LEVEL SECURITY")
    tenant = "organization_id=nullif(current_setting('app.organization_id',true),'')"
    op.execute(f"CREATE POLICY tenant ON ticket_receipt USING ({tenant}) WITH CHECK ({tenant})")
    op.execute("CREATE INDEX ticket_workflow ON ticket(organization_id,workflow_state)")
    op.execute("CREATE INDEX ticket_updated ON ticket(organization_id,ultima_interacao_em)")
    op.execute(
        "CREATE TRIGGER ticket_receipt_append_only BEFORE UPDATE OR DELETE ON ticket_receipt "
        "FOR EACH ROW EXECUTE FUNCTION public.preserve_content_validation()"
    )


def downgrade():
    db = op.get_bind()
    if db.scalar(
        text("""SELECT EXISTS(SELECT 1 FROM ticket_receipt) OR EXISTS
      (SELECT 1 FROM ticket
        WHERE completion_description<>'' OR auto_accept OR status='cancelado')""")
    ):
        raise RuntimeError("Reversão bloqueada: preserve conclusões e recibos dos chamados")
    op.execute("DROP TABLE ticket_receipt")
    op.execute("DROP INDEX ticket_updated")
    op.execute("DROP INDEX ticket_workflow")
    op.execute("""ALTER TABLE ticket DROP COLUMN workflow_state,
      DROP COLUMN completion_description, DROP COLUMN auto_accept,
      DROP COLUMN ultima_interacao_em""")
