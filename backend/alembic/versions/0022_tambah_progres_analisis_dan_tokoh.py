from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0022'
down_revision: Union[str, None] = '0021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('analysis_progress', sa.Integer(), server_default='0', nullable=False))
    op.add_column('documents', sa.Column('characters_progress', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('documents', 'characters_progress')
    op.drop_column('documents', 'analysis_progress')
