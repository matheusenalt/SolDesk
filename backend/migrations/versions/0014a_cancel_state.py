"""Amplia a restrição legada para cancelamento explícito sem reescrever 0014."""

from alembic import op
from sqlalchemy import text

revision = "0014a"
down_revision = "0014"
branch_labels = None
depends_on = None


def constraint(cancelled):
    extra = ",'cancelado'" if cancelled else ""
    op.execute("ALTER TABLE ticket DROP CONSTRAINT ticket_status")
    op.execute(
        "ALTER TABLE ticket ADD CONSTRAINT ticket_status CHECK(status IN "
        "('aberto','em_andamento','aguardando_esclarecimento','aguardando_terceiros',"
        f"'resolvido','encerrado','reaberto'{extra}))"
    )


def upgrade():
    constraint(True)


def downgrade():
    if op.get_bind().scalar(text("SELECT EXISTS(SELECT 1 FROM ticket WHERE status='cancelado')")):
        raise RuntimeError("Reversão bloqueada: preserve chamados cancelados")
    constraint(False)
