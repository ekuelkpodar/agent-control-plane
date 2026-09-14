"""Initial schema: all ACP tables.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-14

Uses Base.metadata.create_all so the revision can never drift from the models.
"""

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from acp.db.models import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    from acp.db.models import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind)
