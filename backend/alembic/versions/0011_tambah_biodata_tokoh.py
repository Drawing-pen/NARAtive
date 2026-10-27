"""tambah kolom biodata tokoh (alias, jenis kelamin, usia, pekerjaan, kepribadian, latar)

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0011'
down_revision: Union[str, None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = (
    ('aliases', sa.String(length=255)),
    ('gender', sa.String(length=20)),
    ('age', sa.String(length=100)),
    ('occupation', sa.String(length=300)),
    ('personality', sa.Text()),
    ('background', sa.Text()),
)


def upgrade() -> None:
    for name, type_ in COLUMNS:
        op.add_column('characters', sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(COLUMNS):
        op.drop_column('characters', name)
