"""tambah chapters.summary_source (ai atau local)

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0016'
down_revision: Union[str, None] = '0015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('chapters', sa.Column('summary_source', sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column('chapters', 'summary_source')
