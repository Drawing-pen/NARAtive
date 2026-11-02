"""tambah paragraphs.markdown dan paragraphs.kind

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0019'
down_revision: Union[str, None] = '0018'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('paragraphs', sa.Column('markdown', sa.Text(), nullable=True))
    op.add_column('paragraphs', sa.Column('kind', sa.String(length=8), server_default='p', nullable=False))


def downgrade() -> None:
    op.drop_column('paragraphs', 'kind')
    op.drop_column('paragraphs', 'markdown')
