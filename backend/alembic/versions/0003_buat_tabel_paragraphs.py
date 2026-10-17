from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'paragraphs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('idx', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('profanity', sa.Float(), nullable=True),
        sa.Column('sexual', sa.Float(), nullable=True),
        sa.Column('violence', sa.Float(), nullable=True),
        sa.Column('emotion', sa.String(length=10), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_paragraphs_document_id'), 'paragraphs', ['document_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_paragraphs_document_id'), table_name='paragraphs')
    op.drop_table('paragraphs')
