from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0021'
down_revision: Union[str, None] = '0020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('read_pages', sa.Integer(), server_default='0', nullable=False))
    op.add_column('documents', sa.Column('failure_reason', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'failure_reason')
    op.drop_column('documents', 'read_pages')
