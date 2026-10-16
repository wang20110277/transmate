"""backfill user nicknames

历史遗留：create_user_by_phone 建号时从未写 nickname，导致用户信息区
没有可展示的名字（只在偏好浮层里重复显示一遍手机号）。

本迁移为「已有手机号但昵称为空」的用户补上默认昵称（手机号后 4 位），
与新建用户的默认值保持一致。微信用户本就带昵称，不受影响。

Revision ID: b4f2a7c9e15d
Revises: 7c1d9e4b2f83
Create Date: 2026-10-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4f2a7c9e15d'
down_revision: Union[str, None] = '7c1d9e4b2f83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为昵称为空的用户补默认昵称。

    刻意用 Python 逐行处理而不是 SQL 拼接：RIGHT()/CONCAT() 等在
    MySQL 与 PostgreSQL 上写法不一致（本项目两种方言都要能用）。
    """
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, phone, nickname FROM trans_user")).fetchall()
    for row in rows:
        user_id, phone, nickname = row[0], row[1], row[2]
        if (nickname or "").strip():
            continue
        if not phone or len(phone) < 4:
            continue
        conn.execute(
            sa.text("UPDATE trans_user SET nickname = :nickname WHERE id = :id"),
            {"nickname": f"用户{phone[-4:]}", "id": user_id},
        )


def downgrade() -> None:
    """不改回去：昵称属于用户数据，且用户之后可能自行修改过，
    回滚时删除会误伤用户自己设置的值，故留空实现。"""
    pass
