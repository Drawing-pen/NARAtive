from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chapters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_chapters_document_id'), 'chapters', ['document_id'], unique=False)
    op.add_column('paragraphs', sa.Column('chapter_no', sa.Integer(), server_default='1', nullable=False))
    op.add_column('documents', sa.Column('paragraph_count', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('documents', 'paragraph_count')
    op.drop_column('paragraphs', 'chapter_no')
    op.drop_index(op.f('ix_chapters_document_id'), table_name='chapters')
    op.drop_table('chapters')
