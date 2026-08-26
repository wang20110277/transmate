"""
用户技能与制品数据模型
"""
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, String, Text, UniqueConstraint

from app.core.database import Base


class UserSkill(Base):
    """用户已安装技能清单(文件本体在 MinIO skills/{user_id}/{name}/)"""

    __tablename__ = "trans_user_skill"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_skill"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="自增ID，主键")
    user_id = Column(String(50), nullable=False, index=True, comment="用户ID")
    name = Column(String(64), nullable=False, comment="技能名(^[a-z0-9-]+$)")
    version = Column(String(64), nullable=False, default="", comment="安装时仓库 commit sha")
    description = Column(Text, nullable=False, default="", comment="技能描述")
    source = Column(String(255), nullable=False, default="", comment="来源快照 owner/repo@ref")
    installed_at = Column(
        DateTime, nullable=True, default=datetime.now, comment="安装时间"
    )


class Artifact(Base):
    """用户制品(成果文件,本体在 MinIO)"""

    __tablename__ = "trans_artifact"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="自增ID，主键")
    user_id = Column(String(50), nullable=False, index=True, comment="用户ID")
    conversation_id = Column(
        BigInteger, nullable=False, default=0, index=True, comment="来源会话ID"
    )
    filename = Column(String(255), nullable=False, comment="制品文件名")
    size = Column(BigInteger, nullable=False, default=0, comment="字节数")
    storage_key = Column(String(500), nullable=False, comment="MinIO 对象键")
    description = Column(Text, nullable=False, default="", comment="制品说明")
    created_at = Column(
        DateTime, nullable=True, default=datetime.now, comment="创建时间"
    )
