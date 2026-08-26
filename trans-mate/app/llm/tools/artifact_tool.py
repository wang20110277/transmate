"""
save_artifact 工具:把沙箱内成果文件保存为用户制品(MinIO+PG)
user_id 在 agent 工厂构建时闭包注入;conversation_id 从 RunnableConfig 的 thread_id 解析

注意:RunnableConfig 注入参数命名为 run_config —— 参数名 config 会遮蔽模块级
`from app.core import config`(调用时读取防护上限依赖该模块引用),且 langchain
官方也建议避免用 config 作为工具参数名。
"""
import logging
from pathlib import Path, PurePosixPath

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.core import config
from app.models.skill import Artifact
from app.services.skill_service import _get_storage
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


def _safe_sandbox_path(user_id: str, source_path: str) -> Path | None:
    """虚拟路径 → 沙箱内真实路径;越界返回 None(配置调用时读取,便于测试)"""
    virtual = PurePosixPath(source_path)
    if ".." in virtual.parts or virtual.parts[:1] == ["~"]:
        return None
    real = (Path(config.SANDBOX_ROOT) / user_id / str(virtual).lstrip("/")).resolve()
    sandbox_root = (Path(config.SANDBOX_ROOT) / user_id).resolve()
    if sandbox_root not in real.parents and real != sandbox_root:
        return None
    return real


def make_save_artifact_tool(user_id: str, storage: StorageService | None = None):
    storage = storage or _get_storage()

    @tool
    def save_artifact(
        source_path: str,
        name: str = "",
        description: str = "",
        run_config: RunnableConfig = None,
    ) -> str:
        """把当前工作成果文件保存为用户制品（跨设备可下载）。

        任务产出可交付文件（如 PPT/PDF/报告等）后调用本工具。

        Args:
            source_path: 沙箱内文件虚拟路径，如 /sessions/conv-3/report.pptx
            name: 制品显示名（可选，默认用源文件名）
            description: 制品说明（可选）
        """
        from app.core.database import SessionLocal

        real = _safe_sandbox_path(user_id, source_path)
        if real is None:
            return f"保存失败：路径 {source_path} 无效或超出用户沙箱范围"
        if not real.is_file():
            return f"保存失败：文件 {source_path} 不存在"

        size = real.stat().st_size
        if size > config.ARTIFACT_MAX_BYTES:
            return f"保存失败：文件超过单制品上限（{config.ARTIFACT_MAX_BYTES} 字节）"

        db: Session = SessionLocal()
        try:
            count = db.query(Artifact).filter_by(user_id=user_id).count()
            if count >= config.ARTIFACT_MAX_COUNT:
                return f"保存失败：制品数量已达上限（{config.ARTIFACT_MAX_COUNT}）"

            thread_id = ((run_config or {}).get("configurable") or {}).get("thread_id", "")
            conversation_id = (
                int(thread_id.removeprefix("conv-")) if thread_id.startswith("conv-") else 0
            )
            filename = f"{name}{real.suffix}" if name else real.name
            row = Artifact(
                user_id=user_id,
                conversation_id=conversation_id,
                filename=filename,
                size=size,
                storage_key="",
                description=description,
            )
            db.add(row)
            db.flush()  # 先落库取自增 id,制品对象键与 PG 主键保持一致
            row.storage_key = f"artifacts/{user_id}/{row.id}/{filename}"
            storage.put_bytes(row.storage_key, real.read_bytes())
            db.commit()
            return f"已保存制品：{filename}（id={row.id}）"
        except Exception as exc:  # 工具层兜底:返回文案让模型自纠
            db.rollback()
            logger.warning("save_artifact 失败 user=%s path=%s: %s", user_id, source_path, exc)
            return f"保存失败：{exc}"
        finally:
            db.close()

    return save_artifact
