"""hapus berantai: e-book mengikuti penggunanya, bab dan paragraf mengikuti e-booknya

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0017'
down_revision: Union[str, None] = '0016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TARGETS = [
    ('documents', 'user_id', 'users'),
    ('chapters', 'document_id', 'documents'),
    ('paragraphs', 'document_id', 'documents'),
]


def _recreate(ondelete: str | None) -> None:
    inspector = sa.inspect(op.get_bind())
    for table, column, parent in TARGETS:
        for fk in inspector.get_foreign_keys(table):
            if fk['constrained_columns'] == [column] and fk['referred_table'] == parent:
                op.drop_constraint(fk['name'], table, type_='foreignkey')
        op.create_foreign_key(f'fk_{table}_{column}', table, parent, [column], ['id'], ondelete=ondelete)


def upgrade() -> None:
    _recreate('CASCADE')


def downgrade() -> None:
    _recreate(None)
