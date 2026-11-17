"""Tarefas com responsabilidade exclusiva, datas distintas e histórico imutável."""

from alembic import op
from sqlalchemy import text

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE team ADD CONSTRAINT team_tenant_id UNIQUE(organization_id,id)")
    op.execute(
        "ALTER TABLE attendance ADD CONSTRAINT attendance_tenant_id UNIQUE(organization_id,id)"
    )
    op.execute("""CREATE TABLE task (
      id varchar(36) PRIMARY KEY,
      organization_id varchar(36) NOT NULL REFERENCES organization(id),
      author_id varchar(36) NOT NULL, title varchar(200) NOT NULL CHECK(length(btrim(title))>0),
      description text NOT NULL DEFAULT '', assignee_id varchar(36), team_id varchar(36),
      client_id varchar(36), system_id varchar(36),
      attendance_id varchar(36), ticket_id varchar(36),
      prevista_para date NOT NULL, agendado_em timestamptz,
      priority varchar(16) NOT NULL DEFAULT 'normal'
        CHECK(priority IN ('baixa','normal','alta','urgente')),
      status varchar(16) NOT NULL DEFAULT 'pendente'
        CHECK(status IN ('pendente','em_andamento','concluida','cancelada')),
      revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
      criado_em timestamptz NOT NULL, atualizado_em timestamptz NOT NULL,
      concluido_em timestamptz, cancelado_em timestamptz,
      UNIQUE(organization_id,id), CHECK((assignee_id IS NULL) <> (team_id IS NULL)),
      CHECK(attendance_id IS NULL OR ticket_id IS NULL),
      CHECK((status='concluida')=(concluido_em IS NOT NULL)),
      CHECK((status='cancelada')=(cancelado_em IS NOT NULL)),
      FOREIGN KEY(organization_id,author_id)
        REFERENCES organization_membership(organization_id,user_id),
      FOREIGN KEY(organization_id,assignee_id)
        REFERENCES organization_membership(organization_id,user_id),
      FOREIGN KEY(organization_id,team_id) REFERENCES team(organization_id,id),
      FOREIGN KEY(organization_id,client_id) REFERENCES client(organization_id,id),
      FOREIGN KEY(organization_id,system_id) REFERENCES software_system(organization_id,id),
      FOREIGN KEY(organization_id,attendance_id) REFERENCES attendance(organization_id,id),
      FOREIGN KEY(organization_id,ticket_id) REFERENCES ticket(organization_id,id)
    )""")
    op.execute("""CREATE TABLE task_event (
      id varchar(36) PRIMARY KEY, organization_id varchar(36) NOT NULL REFERENCES organization(id),
      task_id varchar(36) NOT NULL, actor_id varchar(36) NOT NULL,
      revision integer NOT NULL CHECK(revision>0), action varchar(24) NOT NULL,
      reason text NOT NULL DEFAULT '', before json NOT NULL, after json NOT NULL,
      ocorrido_em timestamptz NOT NULL, UNIQUE(task_id,revision),
      FOREIGN KEY(organization_id,task_id) REFERENCES task(organization_id,id),
      FOREIGN KEY(organization_id,actor_id)
        REFERENCES organization_membership(organization_id,user_id)
    )""")
    op.execute("""CREATE TABLE task_receipt (
      id varchar(36) PRIMARY KEY, organization_id varchar(36) NOT NULL REFERENCES organization(id),
      task_id varchar(36) NOT NULL, actor_id varchar(36) NOT NULL,
      key_hash varchar(64) NOT NULL, fingerprint varchar(64) NOT NULL,
      snapshot json NOT NULL, criado_em timestamptz NOT NULL,
      UNIQUE(organization_id,actor_id,key_hash),
      FOREIGN KEY(organization_id,task_id) REFERENCES task(organization_id,id),
      FOREIGN KEY(organization_id,actor_id)
        REFERENCES organization_membership(organization_id,user_id)
    )""")
    for table in ("task", "task_event", "task_receipt"):
        tenant = "organization_id = nullif(current_setting('app.organization_id',true),'')"
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant ON {table} USING ({tenant}) WITH CHECK ({tenant})")
        op.execute(f"CREATE INDEX {table}_organization ON {table}(organization_id)")
    for table in ("task_event", "task_receipt"):
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION public.preserve_content_validation()"
        )
    op.execute("CREATE INDEX task_due ON task(organization_id,status,prevista_para)")
    op.execute("CREATE INDEX task_assignee ON task(organization_id,assignee_id)")
    op.execute("CREATE INDEX task_team ON task(organization_id,team_id)")


def downgrade():
    db = op.get_bind()
    for table in ("task", "task_event", "task_receipt"):
        if db.scalar(text(f"SELECT EXISTS(SELECT 1 FROM {table})")):
            raise RuntimeError("Reversão bloqueada: preserve as tarefas e seu histórico")
    for table in ("task_receipt", "task_event", "task"):
        op.execute(f"DROP TABLE {table}")
    op.execute("ALTER TABLE attendance DROP CONSTRAINT attendance_tenant_id")
    op.execute("ALTER TABLE team DROP CONSTRAINT team_tenant_id")
