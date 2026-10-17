from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('heaviness_ai', sa.Float(), nullable=True))
    op.add_column('documents', sa.Column('heaviness_note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'heaviness_note')
    op.drop_column('documents', 'heaviness_ai')
