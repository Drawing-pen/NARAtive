"""buat tabel collections dan kolom documents.collection_id, position

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'collections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_collections_user_id', 'collections', ['user_id'])
    with op.batch_alter_table('documents') as batch:
        batch.add_column(sa.Column('collection_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('position', sa.Integer(), server_default='0', nullable=False))
        batch.create_index('ix_documents_collection_id', ['collection_id'])
        batch.create_foreign_key('fk_documents_collection', 'collections', ['collection_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('documents') as batch:
        batch.drop_constraint('fk_documents_collection', type_='foreignkey')
        batch.drop_index('ix_documents_collection_id')
        batch.drop_column('position')
        batch.drop_column('collection_id')
    op.drop_index('ix_collections_user_id', table_name='collections')
    op.drop_table('collections')
