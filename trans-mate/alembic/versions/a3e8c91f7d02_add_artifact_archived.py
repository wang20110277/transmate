"""add artifact archived columns (recycle bin)

Revision ID: a3e8c91f7d02
Revises: 5bd42a74d601
Create Date: 2026-08-27 15:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3e8c91f7d02'
down_revision: Union[str, None] = '5bd42a74d601'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trans_artifact',
                  sa.Column('archived', sa.Boolean(), nullable=False, server_default=sa.text('false'),
                            comment='是否在回收站'))
    op.add_column('trans_artifact',
                  sa.Column('archived_at', sa.DateTime(), nullable=True, comment='归档时间'))
    op.create_index(op.f('ix_trans_artifact_archived'), 'trans_artifact', ['archived'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_trans_artifact_archived'), table_name='trans_artifact')
    op.drop_column('trans_artifact', 'archived_at')
    op.drop_column('trans_artifact', 'archived')
