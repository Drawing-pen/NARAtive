from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('pct_adult', sa.Float(), nullable=True))
    op.add_column('documents', sa.Column('heaviness', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'heaviness')
    op.drop_column('documents', 'pct_adult')
