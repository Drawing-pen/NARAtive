from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0023'
down_revision: Union[str, None] = '0022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('transactions') as batch:
        batch.alter_column('bank', existing_type=sa.String(length=10), nullable=True)
        batch.alter_column('va_number', existing_type=sa.String(length=30), nullable=True)
        batch.add_column(sa.Column('snap_token', sa.String(length=64), nullable=True))
        batch.add_column(sa.Column('payment_method', sa.String(length=60), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('transactions') as batch:
        batch.drop_column('payment_method')
        batch.drop_column('snap_token')
        batch.alter_column('va_number', existing_type=sa.String(length=30), nullable=False)
        batch.alter_column('bank', existing_type=sa.String(length=10), nullable=False)
