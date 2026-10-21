"""buat tabel characters dan character_relations

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'characters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('biodata', sa.Text(), nullable=True),
        sa.Column('mention_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('photo_path', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_characters_document_id'), 'characters', ['document_id'], unique=False)
    op.create_table(
        'character_relations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('character_a_id', sa.Integer(), nullable=False),
        sa.Column('character_b_id', sa.Integer(), nullable=False),
        sa.Column('chapter_id', sa.Integer(), nullable=False),
        sa.Column('relation_type', sa.String(length=10), nullable=False),
        sa.Column('weight', sa.Integer(), server_default='1', nullable=False),
        sa.ForeignKeyConstraint(['character_a_id'], ['characters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['character_b_id'], ['characters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('character_a_id', 'character_b_id', 'chapter_id', name='uq_relation_pair_chapter'),
    )
    op.create_index(op.f('ix_character_relations_character_a_id'), 'character_relations', ['character_a_id'], unique=False)
    op.create_index(op.f('ix_character_relations_character_b_id'), 'character_relations', ['character_b_id'], unique=False)
    op.create_index(op.f('ix_character_relations_chapter_id'), 'character_relations', ['chapter_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_character_relations_chapter_id'), table_name='character_relations')
    op.drop_index(op.f('ix_character_relations_character_b_id'), table_name='character_relations')
    op.drop_index(op.f('ix_character_relations_character_a_id'), table_name='character_relations')
    op.drop_table('character_relations')
    op.drop_index(op.f('ix_characters_document_id'), table_name='characters')
    op.drop_table('characters')
