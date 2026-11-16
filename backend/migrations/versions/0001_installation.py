"""Identidade persistente da instalação; sem entidades de negócio."""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    installation = op.create_table(
        "installation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instance_id", sa.String(36), nullable=False, unique=True),
        sa.CheckConstraint("id = 1", name="installation_singleton"),
    )
    op.bulk_insert(installation, [{"id": 1, "instance_id": str(uuid4())}])


def downgrade():
    raise RuntimeError("Reversão destrutiva desabilitada: preserve o ID da instalação")
