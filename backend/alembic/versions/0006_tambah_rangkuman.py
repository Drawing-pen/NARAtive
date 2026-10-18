from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('documents', sa.Column('summary_status', sa.String(length=10), nullable=True))
    op.add_column('chapters', sa.Column('summary', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('chapters', 'summary')
    op.drop_column('documents', 'summary_status')
    op.drop_column('documents', 'summary')
