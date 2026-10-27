"""tambah documents.cover_path

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0018'
down_revision: Union[str, None] = '0017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('cover_path', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'cover_path')
