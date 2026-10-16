"""add user llm provider table (BYOK)

Revision ID: 7c1d9e4b2f83
Revises: a3e8c91f7d02
Create Date: 2026-10-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c1d9e4b2f83'
down_revision: Union[str, None] = 'a3e8c91f7d02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'trans_user_llm_provider',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='自增ID，主键'),
        sa.Column('user_id', sa.String(length=50), nullable=False, comment='所属用户ID'),
        sa.Column('name', sa.String(length=50), nullable=False, comment='显示名，如 智谱GLM'),
        sa.Column('provider', sa.String(length=50), nullable=False, server_default='openai',
                  comment='langchain model_provider'),
        sa.Column('api_url', sa.String(length=500), nullable=False, comment='OpenAI 兼容 base_url'),
        sa.Column('api_key_cipher', sa.Text(), nullable=False, comment='API Key 密文(Fernet)'),
        sa.Column('models', sa.Text(), nullable=False, comment='可用模型名 JSON 数组'),
        sa.Column('active_model', sa.String(length=100), nullable=False, server_default='', comment='当前选用的模型'),
        sa.Column('temperature', sa.Float(), nullable=False, server_default='0.1', comment='采样温度'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true'), comment='是否启用'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.text('false'),
                  comment='是否为该用户当前使用的配置'),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_user_llm_provider_name'),
        comment='用户自带模型供应商配置',
    )
    op.create_index(
        op.f('ix_trans_user_llm_provider_user_id'),
        'trans_user_llm_provider',
        ['user_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_trans_user_llm_provider_user_id'), table_name='trans_user_llm_provider')
    op.drop_table('trans_user_llm_provider')
