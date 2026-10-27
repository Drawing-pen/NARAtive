"""buat tabel transactions dan usage_quota, tambah users.tier_expires_at dan extra_checks

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0014'
down_revision: Union[str, None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.String(length=40), nullable=False),
        sa.Column('kind', sa.String(length=15), nullable=False),
        sa.Column('plan', sa.String(length=10), nullable=True),
        sa.Column('quantity', sa.Integer(), server_default='1', nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('bank', sa.String(length=10), nullable=False),
        sa.Column('va_number', sa.String(length=30), nullable=False),
        sa.Column('provider', sa.String(length=12), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id'),
    )
    op.create_index('ix_transactions_user_id', 'transactions', ['user_id'])
    op.create_table(
        'usage_quota',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('period', sa.String(length=7), nullable=False),
        sa.Column('used', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'period', name='uq_usage_user_period'),
    )
    op.create_index('ix_usage_quota_user_id', 'usage_quota', ['user_id'])
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('tier_expires_at', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('extra_checks', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_column('extra_checks')
        batch.drop_column('tier_expires_at')
    op.drop_index('ix_usage_quota_user_id', table_name='usage_quota')
    op.drop_table('usage_quota')
    op.drop_index('ix_transactions_user_id', table_name='transactions')
    op.drop_table('transactions')
