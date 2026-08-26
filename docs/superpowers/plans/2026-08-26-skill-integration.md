# Skill 集成与用户云工作区 · 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 TransMate 实现 skill 集成(GitHub 仓库浏览/安装/渐进式披露注入)与用户云工作区(每用户服务器沙箱、云端技能库 PG+MinIO、最小制品链路 save_artifact+列表/下载)。

**Architecture:** 复用 deepagents 0.7.8 原生能力——`create_deep_agent(skills=, backend=)` 注入 `SkillsMiddleware`(渐进式披露)与真实文件工具;`CompositeBackend` 把 `/skills/` 路由到用户技能物化缓存、默认路由到用户沙箱(virtual_mode 防越界)。技能文件存 MinIO、安装清单存 PG,agent 构建时按清单版本物化;制品经 `save_artifact` 工具上传 MinIO。agent 工厂缓存键=user_id,checkpointer 全局共享。

**Tech Stack:** FastAPI + SQLAlchemy(+alembic)+ deepagents 0.7.8 + langchain 1.x + httpx + minio SDK(新增)+ Vue 3 + Element Plus + axios。

**Spec:** `docs/superpowers/specs/2026-08-26-skill-integration-design.md`(本计划论证自该 spec,执行者需同时阅读)

## Global Constraints

- Python 依赖固定版本写入 `trans-mate/requirements.txt`;本期仅新增 `minio==7.2.15`
- 所有测试必须带 pytest 标记(`@pytest.mark.unit` 或 `@pytest.mark.integration`,pytest.ini 开了 `--strict-markers`)
- 后端测试不依赖真实 GitHub/MinIO:GitHub 用 `httpx.MockTransport`,MinIO 用 `tests/fake_storage.py` 的 FakeStorage
- 新接口不接鉴权中间件,`user_id` 作为显式参数(沿用 `chat_routes.py` 现有模式)
- 数据库:模型经 `init_db()` 自动建表;alembic 迁移用于生产对齐
- 前端改动后必须通过 `npm run type-check`(在 `trans-mate-web-ui/` 下)
- 目录约定:沙箱根 `store/sandbox/{user_id}/`(会话子目录 `sessions/conv-{id}/`),技能物化缓存 `store/skill_cache/{user_id}/`,均可由 env 覆盖
- 提交信息用中文、conventional 风格(`feat:`/`test:`/`docs:`)

---

### Task 1: 钉住 CompositeBackend 路由与 FilesystemBackend 虚拟路径行为

设计文档 §8 指定的首个验证点:确认 `/skills/` 前缀被剥离后交给子 backend、技能扫描可用、越界被拒。纯测试任务,不改产品代码;若行为与预期不符,停下修订后续任务的接线方式。

**Files:**
- Test: `trans-mate/tests/test_backend_routing.py`

**Interfaces:**
- Consumes: `deepagents.backends.composite.CompositeBackend`、`deepagents.backends.filesystem.FilesystemBackend`、`deepagents.middleware.skills._list_skills`(内部函数,仅测试用)
- Produces: 验证结论(后续任务依赖的接线事实),无代码产物

- [ ] **Step 1: 写测试**

```python
"""
CompositeBackend 路由与 FilesystemBackend 虚拟路径行为验证
(设计文档 §8 首个验证点:接线事实在此钉住)
"""
import pytest


@pytest.mark.unit
def test_composite_routes_skills_prefix_and_strips_it(tmp_path):
    from deepagents.backends.composite import CompositeBackend
    from deepagents.backends.filesystem import FilesystemBackend
    from deepagents.middleware.skills import _list_skills

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    cache = tmp_path / "cache"
    skill_dir = cache / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: 演示技能\n---\n# Demo\n", encoding="utf-8"
    )

    backend = CompositeBackend(
        default=FilesystemBackend(root_dir=str(sandbox), virtual_mode=True),
        routes={"/skills/": FilesystemBackend(root_dir=str(cache), virtual_mode=True)},
    )

    skills = _list_skills(backend, "/skills/")
    assert [s["name"] for s in skills] == ["demo-skill"]
    assert skills[0]["path"] == "/skills/demo-skill/SKILL.md"
    # 模型按注入的 path 读全文 → download_files 走路由
    resp = backend.download_files(["/skills/demo-skill/SKILL.md"])[0]
    assert resp.error is None
    assert b"name: demo-skill" in resp.content


@pytest.mark.unit
def test_filesystem_backend_virtual_mode_blocks_traversal(tmp_path):
    from deepagents.backends.filesystem import FilesystemBackend

    root = tmp_path / "sandbox"
    root.mkdir()
    (root / "a.txt").write_text("x", encoding="utf-8")
    backend = FilesystemBackend(root_dir=str(root), virtual_mode=True)

    assert backend.ls("/").entries is not None
    resp = backend.download_files(["/a.txt"])[0]
    assert resp.error is None
    # 越界与 home 展开必须被拒
    assert backend.download_files(["/../escape.txt"])[0].error is not None
    assert backend.download_files(["/~/secret"])[0].error is not None
```

- [ ] **Step 2: 运行验证**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_backend_routing.py -v`
Expected: 2 passed。若失败,记录实际行为并**停止**,与计划维护者确认接线调整(不要静默改测试放水)。

- [ ] **Step 3: Commit**

```bash
git add trans-mate/tests/test_backend_routing.py
git commit -m "test: 钉住 CompositeBackend 技能路由与沙箱越界拦截行为"
```

---

### Task 2: 配置项、数据模型与迁移

**Files:**
- Modify: `trans-mate/app/core/config.py`(文件末尾追加)
- Create: `trans-mate/app/models/skill.py`
- Modify: `trans-mate/app/core/database.py`(`init_db` 增加导入)
- Modify: `trans-mate/tests/conftest.py`(db fixture 增加导入)
- Create: `trans-mate/alembic/versions/<new>_add_user_skill_and_artifact.py`(autogenerate)
- Test: `trans-mate/tests/test_skill_models.py`

**Interfaces:**
- Produces(后续任务依赖的确切名字):
  - 配置常量:`SKILL_REGISTRY_OWNER, SKILL_REGISTRY_REPO, SKILL_REGISTRY_REF, SKILL_REGISTRY_SUBDIR, SKILL_REGISTRY_TOKEN, SKILL_REGISTRY_PROXY, SKILL_REGISTRY_CACHE_TTL, MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET, MINIO_SECURE, SANDBOX_ROOT, SKILL_CACHE_ROOT, SKILL_MAX_FILE_BYTES, SKILL_MAX_FILES, ARTIFACT_MAX_BYTES, ARTIFACT_MAX_COUNT`
  - 模型类:`UserSkill`(表 `trans_user_skill`,字段 id/user_id/name/version/description/source/installed_at,唯一约束 (user_id, name))、`Artifact`(表 `trans_artifact`,字段 id/user_id/conversation_id/filename/size/storage_key/description/created_at)

- [ ] **Step 1: 写失败测试**

```python
"""UserSkill / Artifact 模型与表结构测试"""
import pytest

from app.core.database import Base
from app.models.skill import Artifact, UserSkill


@pytest.mark.unit
def test_user_skill_table_columns(db):
    table = UserSkill.__table__
    assert table.name == "trans_user_skill"
    cols = {c.name for c in table.columns}
    assert {"id", "user_id", "name", "version", "description", "source", "installed_at"} <= cols
    uniques = [str(u) for u in table.constraints if "UniqueConstraint" in str(u)]
    assert any("user_id" in u and "name" in u for u in uniques)


@pytest.mark.unit
def test_artifact_table_columns(db):
    table = Artifact.__table__
    assert table.name == "trans_artifact"
    cols = {c.name for c in table.columns}
    assert {
        "id", "user_id", "conversation_id", "filename", "size", "storage_key",
        "description", "created_at",
    } <= cols


@pytest.mark.unit
def test_models_create_and_query(db):
    skill = UserSkill(
        user_id="u1", name="demo-skill", version="abc123",
        description="演示", source="anthropics/skills@main",
    )
    db.add(skill)
    db.commit()
    rows = db.query(UserSkill).filter_by(user_id="u1").all()
    assert [r.name for r in rows] == ["demo-skill"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_skill_models.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.models.skill'`

- [ ] **Step 3: 写模型与配置**

`trans-mate/app/models/skill.py`:

```python
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
```

`trans-mate/app/core/config.py` 末尾追加:

```python
# Skill 注册表(GitHub 仓库,默认 anthropics/skills)
SKILL_REGISTRY_OWNER = os.getenv("SKILL_REGISTRY_OWNER", "anthropics")
SKILL_REGISTRY_REPO = os.getenv("SKILL_REGISTRY_REPO", "skills")
SKILL_REGISTRY_REF = os.getenv("SKILL_REGISTRY_REF", "main")
SKILL_REGISTRY_SUBDIR = os.getenv("SKILL_REGISTRY_SUBDIR", "")
SKILL_REGISTRY_TOKEN = os.getenv("SKILL_REGISTRY_TOKEN", "")
SKILL_REGISTRY_PROXY = os.getenv("SKILL_REGISTRY_PROXY", "")
SKILL_REGISTRY_CACHE_TTL = float(os.getenv("SKILL_REGISTRY_CACHE_TTL", "300"))

# MinIO 对象存储
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "transmate")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# 用户云工作区
SANDBOX_ROOT = os.getenv(
    "SANDBOX_ROOT",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "store", "sandbox"),
)
SKILL_CACHE_ROOT = os.getenv(
    "SKILL_CACHE_ROOT",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "store", "skill_cache"),
)

# 防护上限(spec §6)
SKILL_MAX_FILE_BYTES = int(os.getenv("SKILL_MAX_FILE_BYTES", str(10 * 1024 * 1024)))
SKILL_MAX_FILES = int(os.getenv("SKILL_MAX_FILES", "200"))
ARTIFACT_MAX_BYTES = int(os.getenv("ARTIFACT_MAX_BYTES", str(200 * 1024 * 1024)))
ARTIFACT_MAX_COUNT = int(os.getenv("ARTIFACT_MAX_COUNT", "500"))
```

`trans-mate/app/core/database.py` 的 `init_db()` 导入区追加:

```python
    from app.models.skill import UserSkill, Artifact  # noqa: F401
```

`trans-mate/tests/conftest.py` 的 `db` fixture 导入区同样追加:

```python
    from app.models.skill import UserSkill, Artifact  # noqa: F401
```

- [ ] **Step 4: 运行测试通过**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_skill_models.py -v`
Expected: 3 passed

- [ ] **Step 5: 生成 alembic 迁移**

Run: `cd trans-mate && .venv/bin/alembic revision --autogenerate -m "add user_skill and artifact tables"`
检查生成文件 upgrade 包含 `trans_user_skill`/`trans_artifact` 两表。
Run: `cd trans-mate && .venv/bin/alembic upgrade head`
Expected: 成功(本地 dev 库可达时;不可达则记录原因跳过——`init_db()` 的 create_all 已保证开发/测试可用,迁移文件进库即完成生产对齐)。

- [ ] **Step 6: Commit**

```bash
git add trans-mate/app/models/skill.py trans-mate/app/core/config.py trans-mate/app/core/database.py trans-mate/tests/conftest.py trans-mate/tests/test_skill_models.py trans-mate/alembic/versions/
git commit -m "feat: 技能/制品数据模型、云工作区配置项与迁移"
```

---

### Task 3: StorageService(MinIO 封装)与 FakeStorage

**Files:**
- Create: `trans-mate/app/services/storage_service.py`
- Create: `trans-mate/tests/fake_storage.py`
- Modify: `trans-mate/requirements.txt`(dependencies 段加 `minio==7.2.15`)
- Test: `trans-mate/tests/test_storage_service.py`

**Interfaces:**
- Produces:
  - `StorageService`(基类,定义统一接口):
    - `upload_prefix(local_dir: Path, prefix: str) -> int`(目录递归上传到 `prefix/` 下,返回对象数)
    - `download_prefix(prefix: str, local_dir: Path) -> None`(把 `prefix/` 下对象下载回目录)
    - `delete_prefix(prefix: str) -> None`
    - `put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None`
    - `get_bytes(key: str) -> bytes`
    - `presigned_get_url(key: str, expires_seconds: int) -> str`
    - `list_keys(prefix: str) -> list[str]`
  - `MinioStorageService(StorageService)`:生产实现,minio 客户端懒初始化
  - `FakeStorage(StorageService)`(tests/fake_storage.py):内存 dict 实现,`presigned_get_url` 返回 `fake:///{key}`
- Consumes: Task 2 的 `MINIO_*` 配置

- [ ] **Step 1: 安装依赖**

Run: `cd trans-mate && .venv/bin/pip install minio==7.2.15`
并把 `minio==7.2.15` 加入 `requirements.txt`(放在 `#database` 段后新增 `#object-storage` 段)。

- [ ] **Step 2: 写失败测试**

```python
"""StorageService 内存实现(FakeStorage)契约测试"""
from pathlib import Path

import pytest

from tests.fake_storage import FakeStorage


@pytest.mark.unit
def test_upload_and_download_prefix_roundtrip(tmp_path: Path):
    storage = FakeStorage()
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "SKILL.md").write_text("hello", encoding="utf-8")
    (src / "sub" / "helper.py").write_text("print()", encoding="utf-8")

    count = storage.upload_prefix(src, "skills/u1/demo-skill")
    assert count == 2
    assert sorted(storage.list_keys("skills/u1/demo-skill")) == [
        "skills/u1/demo-skill/SKILL.md",
        "skills/u1/demo-skill/sub/helper.py",
    ]

    dst = tmp_path / "dst"
    storage.download_prefix("skills/u1/demo-skill", dst)
    assert (dst / "SKILL.md").read_text(encoding="utf-8") == "hello"
    assert (dst / "sub" / "helper.py").exists()


@pytest.mark.unit
def test_delete_prefix_and_isolation():
    storage = FakeStorage()
    storage.put_bytes("skills/u1/a/SKILL.md", b"1")
    storage.put_bytes("skills/u2/a/SKILL.md", b"2")
    storage.delete_prefix("skills/u1/")
    assert storage.list_keys("skills/") == ["skills/u2/a/SKILL.md"]


@pytest.mark.unit
def test_put_get_bytes_and_presigned():
    storage = FakeStorage()
    storage.put_bytes("artifacts/u1/x.pptx", b"data")
    assert storage.get_bytes("artifacts/u1/x.pptx") == b"data"
    assert storage.presigned_get_url("artifacts/u1/x.pptx", 3600) == "fake:///artifacts/u1/x.pptx"
```

- [ ] **Step 3: 运行确认失败**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_storage_service.py -v`
Expected: FAIL,`ModuleNotFoundError`(fake_storage / storage_service 均未建)

- [ ] **Step 4: 实现**

`trans-mate/app/services/storage_service.py`:

```python
"""
对象存储封装:技能库/制品统一走该服务
生产为 MinioStorageService;测试用 tests/fake_storage.py 的 FakeStorage
"""
import logging
from pathlib import Path

from app.core.config import (
    MINIO_ACCESS_KEY,
    MINIO_BUCKET,
    MINIO_ENDPOINT,
    MINIO_SECRET_KEY,
    MINIO_SECURE,
)

logger = logging.getLogger(__name__)


class StorageService:
    """存储接口:目录级(技能)与字节级(制品)操作"""

    def upload_prefix(self, local_dir: Path, prefix: str) -> int:
        raise NotImplementedError

    def download_prefix(self, prefix: str, local_dir: Path) -> None:
        raise NotImplementedError

    def delete_prefix(self, prefix: str) -> None:
        raise NotImplementedError

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        raise NotImplementedError

    def get_bytes(self, key: str) -> bytes:
        raise NotImplementedError

    def presigned_get_url(self, key: str, expires_seconds: int) -> str:
        raise NotImplementedError

    def list_keys(self, prefix: str) -> list[str]:
        raise NotImplementedError


class MinioStorageService(StorageService):
    """MinIO 实现(客户端懒初始化,bucket 不存在时自动创建)"""

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is None:
            from minio import Minio

            self._client = Minio(
                MINIO_ENDPOINT,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=MINIO_SECURE,
            )
            if not self._client.bucket_exists(MINIO_BUCKET):
                self._client.make_bucket(MINIO_BUCKET)
        return self._client

    def upload_prefix(self, local_dir: Path, prefix: str) -> int:
        client = self._get_client()
        count = 0
        for path in sorted(local_dir.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            key = f"{prefix}/{path.relative_to(local_dir).as_posix()}"
            client.fput_object(
                MINIO_BUCKET, key, str(path),
            )
            count += 1
        return count

    def download_prefix(self, prefix: str, local_dir: Path) -> None:
        client = self._get_client()
        local_dir.mkdir(parents=True, exist_ok=True)
        for key in self.list_keys(prefix):
            rel = key[len(prefix):].lstrip("/")
            target = local_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            client.fget_object(MINIO_BUCKET, key, str(target))

    def delete_prefix(self, prefix: str) -> None:
        client = self._get_client()
        for key in self.list_keys(prefix):
            client.remove_object(MINIO_BUCKET, key)

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        import io

        self._get_client().put_object(
            MINIO_BUCKET, key, io.BytesIO(data), length=len(data),
            content_type=content_type,
        )

    def get_bytes(self, key: str) -> bytes:
        import io

        response = self._get_client().get_object(MINIO_BUCKET, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def presigned_get_url(self, key: str, expires_seconds: int) -> str:
        from datetime import timedelta

        return self._get_client().presigned_get_object(
            MINIO_BUCKET, key, expires=timedelta(seconds=expires_seconds)
        )

    def list_keys(self, prefix: str) -> list[str]:
        client = self._get_client()
        return [
            obj.object_name
            for obj in client.list_objects(MINIO_BUCKET, prefix=prefix, recursive=True)
        ]


_storage: StorageService | None = None


def get_storage() -> StorageService:
    """进程级单例;测试里直接注入替换该模块变量"""
    global _storage
    if _storage is None:
        _storage = MinioStorageService()
    return _storage
```

`trans-mate/tests/fake_storage.py`:

```python
"""
内存版 StorageService(测试用,行为契约与 MinioStorageService 一致)
"""
from pathlib import Path

from app.services.storage_service import StorageService


class FakeStorage(StorageService):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload_prefix(self, local_dir: Path, prefix: str) -> int:
        count = 0
        for path in sorted(local_dir.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            key = f"{prefix}/{path.relative_to(local_dir).as_posix()}"
            self.objects[key] = path.read_bytes()
            count += 1
        return count

    def download_prefix(self, prefix: str, local_dir: Path) -> None:
        for key in sorted(self.objects):
            if not key.startswith(prefix):
                continue
            rel = key[len(prefix):].lstrip("/")
            target = local_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.objects[key])

    def delete_prefix(self, prefix: str) -> None:
        for key in [k for k in self.objects if k.startswith(prefix)]:
            del self.objects[k]

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.objects[key] = data

    def get_bytes(self, key: str) -> bytes:
        if key not in self.objects:
            raise KeyError(f"对象不存在: {key}")
        return self.objects[key]

    def presigned_get_url(self, key: str, expires_seconds: int) -> str:
        return f"fake:///{key}"

    def list_keys(self, prefix: str) -> list[str]:
        return sorted(k for k in self.objects if k.startswith(prefix))
```

- [ ] **Step 5: 运行测试通过**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_storage_service.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add trans-mate/app/services/storage_service.py trans-mate/tests/fake_storage.py trans-mate/tests/test_storage_service.py trans-mate/requirements.txt
git commit -m "feat: StorageService 对象存储封装(MinIO 实现+测试 FakeStorage)"
```

---

### Task 4: SkillService — GitHub 注册表列表

**Files:**
- Create: `trans-mate/app/services/skill_service.py`
- Test: `trans-mate/tests/test_skill_registry.py`

**Interfaces:**
- Consumes: Task 2 配置;`httpx`(已在依赖)
- Produces:
  - `SkillRegistryItem`(TypedDict):`{"name": str, "description": str, "license": str, "path": str}`(path 为仓库内目录路径)
  - `SkillServiceError(Exception)`:`.message` 属性
  - `list_registry(force: bool = False) -> list[SkillRegistryItem]`(TTL 缓存,force=True 强制刷新)
  - `clear_registry_cache() -> None`
  - 模块内可注入 transport:`_build_client(transport: httpx.BaseTransport | None = None) -> httpx.Client`
  - `parse_skill_md(content: str, dir_name: str) -> dict | None`(frontmatter 解析,供 Task 5 安装校验复用)

- [ ] **Step 1: 写失败测试**

```python
"""SkillService 注册表列表(httpx.MockTransport 伪造 GitHub)"""
import httpx
import pytest

import app.services.skill_service as skill_service
from app.services.skill_service import SkillServiceError, list_registry


def _github_transport(handler=None):
    """伪造 GitHub API:根目录 2 个技能目录 + 各自 SKILL.md"""
    def _handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/commits/main"):
            return httpx.Response(200, json=[{"sha": "sha000"}], request=request)
        if path.endswith("/contents/"):
            return httpx.Response(200, json=[
                {"name": "pdf", "path": "pdf", "type": "dir"},
                {"name": "ppt", "path": "ppt", "type": "dir"},
                {"name": "README.md", "path": "README.md", "type": "file"},
            ], request=request)
        if path.endswith("/contents/pdf/SKILL.md"):
            return httpx.Response(200, json=[{
                "name": "SKILL.md", "path": "pdf/SKILL.md", "type": "file", "size": 100,
                "download_url": "https://raw.test/pdf/SKILL.md",
            }], request=request)
        if path.endswith("/contents/ppt/SKILL.md"):
            return httpx.Response(200, json=[{
                "name": "SKILL.md", "path": "ppt/SKILL.md", "type": "file", "size": 100,
                "download_url": "https://raw.test/ppt/SKILL.md",
            }], request=request)
        if "raw.test" in str(request.url) and path.endswith("pdf/SKILL.md"):
            return httpx.Response(200, text=(
                "---\nname: pdf\ndescription: PDF 处理技能\nlicense: MIT\n---\n# PDF\n"
            ), request=request)
        if "raw.test" in str(request.url) and path.endswith("ppt/SKILL.md"):
            return httpx.Response(200, text=(
                "---\nname: ppt\ndescription: PPT 生成技能\n---\n# PPT\n"
            ), request=request)
        return httpx.Response(404, request=request)

    return httpx.MockTransport(_handler if handler is None else handler)


@pytest.fixture(autouse=True)
def _reset_cache():
    skill_service.clear_registry_cache()
    skill_service._registry_transport = None
    yield
    skill_service.clear_registry_cache()
    skill_service._registry_transport = None


@pytest.mark.unit
def test_list_registry_parses_frontmatter(monkeypatch):
    monkeypatch.setattr(skill_service, "_registry_transport", _github_transport())
    items = list_registry()
    assert {i["name"] for i in items} == {"pdf", "ppt"}
    pdf = next(i for i in items if i["name"] == "pdf")
    assert pdf["description"] == "PDF 处理技能"
    assert pdf["license"] == "MIT"


@pytest.mark.unit
def test_list_registry_uses_ttl_cache(monkeypatch):
    calls = {"n": 0}

    def counting_handler(request):
        calls["n"] += 1
        return _github_transport().handler(request)

    transport = httpx.MockTransport(counting_handler)
    monkeypatch.setattr(skill_service, "_registry_transport", transport)
    list_registry()
    list_registry()
    assert calls["n"] == list_registry() and calls["n"] < 10  # 多次调用未按目录数线性增长


@pytest.mark.unit
def test_list_registry_error_raises(monkeypatch):
    def fail(request):
        raise httpx.ConnectError("boom", request=request)

    monkeypatch.setattr(skill_service, "_registry_transport", httpx.MockTransport(fail))
    with pytest.raises(SkillServiceError):
        list_registry()


@pytest.mark.unit
def test_parse_skill_md_valid_and_invalid():
    ok = skill_service.parse_skill_md(
        "---\nname: demo\ndescription: 演示\n---\n正文", dir_name="demo"
    )
    assert ok["name"] == "demo"
    assert skill_service.parse_skill_md("没有 frontmatter", "x") is None
    assert skill_service.parse_skill_md("---\nname: bad\n---\n", "other") is None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_skill_registry.py -v`
Expected: FAIL,模块不存在

- [ ] **Step 3: 实现 skill_service.py(第一部分:注册表)**

`trans-mate/app/services/skill_service.py`:

```python
"""
Skill 服务:GitHub 注册表浏览 + 安装/卸载(安装/卸载在 Task 5 补齐)
"""
import logging
import re
import time
from typing import Optional, TypedDict

import httpx
import yaml
from sqlalchemy.orm import Session

from app.core.config import (
    SKILL_REGISTRY_CACHE_TTL,
    SKILL_REGISTRY_OWNER,
    SKILL_REGISTRY_PROXY,
    SKILL_REGISTRY_REF,
    SKILL_REGISTRY_REPO,
    SKILL_REGISTRY_SUBDIR,
    SKILL_REGISTRY_TOKEN,
)

logger = logging.getLogger(__name__)

SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9-]+$")

# 测试注入口:设为 httpx.MockTransport 即离线
_registry_transport: Optional[httpx.BaseTransport] = None

# TTL 缓存:ts -> (存入时间, 结果)
_registry_cache: dict[str, tuple[float, list]] = {}
_registry_commit_sha: dict[str, str] = {}


class SkillServiceError(Exception):
    """技能服务业务异常(message 面向用户可读)"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class SkillRegistryItem(TypedDict):
    name: str
    description: str
    license: str
    path: str  # 仓库内技能目录路径


def _build_client() -> httpx.Client:
    headers = {"Accept": "application/vnd.github+json"}
    if SKILL_REGISTRY_TOKEN:
        headers["Authorization"] = f"Bearer {SKILL_REGISTRY_TOKEN}"
    return httpx.Client(
        base_url=f"https://api.github.com/repos/{SKILL_REGISTRY_OWNER}/{SKILL_REGISTRY_REPO}",
        headers=headers,
        transport=_registry_transport,
        proxy=SKILL_REGISTRY_PROXY or None,
        timeout=15.0,
        follow_redirects=True,
    )


def parse_skill_md(content: str, dir_name: str) -> Optional[dict]:
    """解析 SKILL.md frontmatter;不合法返回 None"""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    if not name or not description or name != dir_name:
        return None
    if not SKILL_NAME_PATTERN.match(name):
        return None
    return {
        "name": name,
        "description": description,
        "license": str(data.get("license", "") or "").strip(),
    }


def _api_root() -> str:
    return f"/contents/{SKILL_REGISTRY_SUBDIR}" if SKILL_REGISTRY_SUBDIR else "/contents/"


def _fetch_json(client: httpx.Client, path: str):
    response = client.get(path)
    if response.status_code != 200:
        raise SkillServiceError(f"GitHub API 请求失败 {path}: HTTP {response.status_code}")
    return response.json()


def _fetch_skill_md(client: httpx.Client, dir_path: str) -> Optional[str]:
    """下载技能目录下 SKILL.md 原文;404 返回 None"""
    listing = _fetch_json(client, f"/contents/{dir_path}/SKILL.md")
    if isinstance(listing, list):
        listing = listing[0]
    download_url = listing.get("download_url")
    if not download_url:
        return None
    raw = client.get(download_url)
    if raw.status_code != 200:
        return None
    return raw.text


def list_registry(force: bool = False) -> list[SkillRegistryItem]:
    """列出仓库技能目录(TTL 缓存降级:失败时若缓存未过期返回旧值)"""
    cached = _registry_cache.get("items")
    if not force and cached and time.time() - cached[0] < SKILL_REGISTRY_CACHE_TTL:
        return cached[1]

    try:
        with _build_client() as client:
            entries = _fetch_json(client, _api_root())
            dirs = [e["path"] for e in entries if e.get("type") == "dir"]
            items: list[SkillRegistryItem] = []
            for dir_path in dirs:
                content = _fetch_skill_md(client, dir_path)
                if content is None:
                    continue
                meta = parse_skill_md(content, dir_path.rsplit("/", 1)[-1])
                if meta is None:
                    logger.warning("跳过不合规技能目录: %s", dir_path)
                    continue
                items.append(
                    SkillRegistryItem(
                        name=meta["name"], description=meta["description"],
                        license=meta["license"], path=dir_path,
                    )
                )
    except SkillServiceError:
        if cached:  # 降级返回旧缓存
            return cached[1]
        raise
    except httpx.HTTPError as exc:
        if cached:
            return cached[1]
        raise SkillServiceError(f"技能仓库不可达: {exc}") from exc

    _registry_cache["items"] = (time.time(), items)
    return items


def clear_registry_cache() -> None:
    _registry_cache.clear()
```

- [ ] **Step 4: 运行测试通过**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_skill_registry.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add trans-mate/app/services/skill_service.py trans-mate/tests/test_skill_registry.py
git commit -m "feat: SkillService 技能仓库注册表列表(TTL 缓存+离线测试)"
```

---

### Task 5: SkillService — 安装/卸载/已装列表

原子性实现方式(满足 spec §5"失败清理"):本地临时目录全量下载并校验通过 → 上传 MinIO 正式前缀 → 最后写 PG 清单(可见性以 PG 清单为准,中途失败 `delete_prefix` 清理)。

**Files:**
- Modify: `trans-mate/app/services/skill_service.py`(追加)
- Test: `trans-mate/tests/test_skill_install.py`

**Interfaces:**
- Consumes: Task 3 `StorageService`(`get_storage()`)、Task 4 `parse_skill_md/_build_client/SKILL_NAME_PATTERN`;Task 2 `UserSkill`
- Produces:
  - `install_skill(db: Session, user_id: str, name: str) -> UserSkill`
  - `uninstall_skill(db: Session, user_id: str, name: str) -> None`
  - `list_installed(db: Session, user_id: str) -> list[UserSkill]`
  - `latest_commit_sha() -> str`(安装版本号)

- [ ] **Step 1: 写失败测试**

```python
"""SkillService 安装/卸载/已装列表(FakeStorage + MockTransport + 内存库)"""
import httpx
import pytest

import app.services.skill_service as skill_service
from app.services.skill_service import (
    SkillServiceError,
    install_skill,
    list_installed,
    uninstall_skill,
)
from tests.fake_storage import FakeStorage

RAW_SKILL_MD = "---\nname: demo-skill\ndescription: 演示技能\n---\n# Demo\n"
HELPER = "print('hi')"


def _install_transport(*, big_file: bool = False, fail_raw: bool = False):
    def _handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "sha-latest"}, request=request)
        if path.endswith("/contents/demo-skill"):
            files = [
                {"name": "SKILL.md", "path": "demo-skill/SKILL.md", "type": "file",
                 "size": 10 * 1024 * 1024 + 1 if big_file else 30,
                 "download_url": "https://raw.test/demo-skill/SKILL.md"},
                {"name": "helper.py", "path": "demo-skill/helper.py", "type": "file",
                 "size": 20, "download_url": "https://raw.test/demo-skill/helper.py"},
            ]
            return httpx.Response(200, json=files, request=request)
        if "raw.test" in str(request.url) and path.endswith("SKILL.md"):
            if fail_raw:
                return httpx.Response(500, request=request)
            return httpx.Response(200, text=RAW_SKILL_MD, request=request)
        if "raw.test" in str(request.url) and path.endswith("helper.py"):
            return httpx.Response(200, text=HELPER, request=request)
        return httpx.Response(404, request=request)

    return httpx.MockTransport(_handler)


@pytest.fixture
def storage():
    fake = FakeStorage()
    skill_service._storage_singleton_override = fake
    yield fake
    skill_service._storage_singleton_override = None


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    skill_service.clear_registry_cache()
    monkeypatch.setattr(skill_service, "_registry_transport", None)


@pytest.mark.unit
def test_install_downloads_and_records(db, storage, monkeypatch):
    monkeypatch.setattr(skill_service, "_registry_transport", _install_transport())
    row = install_skill(db, "u1", "demo-skill")
    assert row.version == "sha-latest"
    assert row.name == "demo-skill"
    keys = storage.list_keys("skills/u1/demo-skill")
    assert any(k.endswith("SKILL.md") for k in keys)
    assert any(k.endswith("helper.py") for k in keys)
    assert [r.name for r in list_installed(db, "u1")] == ["demo-skill"]


@pytest.mark.unit
def test_install_rejects_oversize_file(db, storage, monkeypatch):
    monkeypatch.setattr(
        skill_service, "_registry_transport", _install_transport(big_file=True)
    )
    with pytest.raises(SkillServiceError, match="大小超限"):
        install_skill(db, "u1", "demo-skill")
    assert storage.list_keys("skills/u1/") == []  # 无残留
    assert list_installed(db, "u1") == []


@pytest.mark.unit
def test_install_midway_failure_cleans_up(db, storage, monkeypatch):
    monkeypatch.setattr(
        skill_service, "_registry_transport", _install_transport(fail_raw=True)
    )
    with pytest.raises(SkillServiceError):
        install_skill(db, "u1", "demo-skill")
    assert storage.list_keys("skills/u1/") == []
    assert list_installed(db, "u1") == []


@pytest.mark.unit
def test_install_bad_name_rejected(db, storage):
    with pytest.raises(SkillServiceError, match="名称不合法"):
        install_skill(db, "u1", "../escape")


@pytest.mark.unit
def test_uninstall_removes_storage_and_row(db, storage, monkeypatch):
    monkeypatch.setattr(skill_service, "_registry_transport", _install_transport())
    install_skill(db, "u1", "demo-skill")
    uninstall_skill(db, "u1", "demo-skill")
    assert storage.list_keys("skills/u1/") == []
    assert list_installed(db, "u1") == []


@pytest.mark.unit
def test_users_isolated(db, storage, monkeypatch):
    monkeypatch.setattr(skill_service, "_registry_transport", _install_transport())
    install_skill(db, "u1", "demo-skill")
    assert list_installed(db, "u2") == []
    with pytest.raises(KeyError):
        storage.get_bytes("skills/u2/demo-skill/SKILL.md")
```

- [ ] **Step 2: 运行确认失败**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_skill_install.py -v`
Expected: FAIL,`install_skill` 未定义

- [ ] **Step 3: 实现(追加到 skill_service.py)**

在 `skill_service.py` 追加(并把文件头部 import 区补充 `from pathlib import Path`、`import tempfile, shutil, uuid`,Task 3 的 `from app.services.storage_service import get_storage`):

```python
from app.models.skill import UserSkill
from app.services.storage_service import StorageService, get_storage

# 测试可覆盖的单例(不改 get_storage 全局,避免影响其它服务的测试)
_storage_singleton_override: Optional[StorageService] = None


def _get_storage() -> StorageService:
    return _storage_singleton_override or get_storage()


def latest_commit_sha() -> str:
    """仓库 ref 最新 commit sha(安装版本号)"""
    with _build_client() as client:
        response = client.get(f"/commits/{SKILL_REGISTRY_REF}")
        if response.status_code != 200:
            raise SkillServiceError(f"获取仓库版本失败: HTTP {response.status_code}")
        data = response.json()
        return data["sha"] if isinstance(data, dict) else data[0]["sha"]


def _walk_skill_dir(client: httpx.Client, dir_path: str) -> list[dict]:
    """递归列出技能目录全部文件(contents API)"""
    files: list[dict] = []
    entries = _fetch_json(client, f"/contents/{dir_path}")
    for entry in entries:
        if entry.get("type") == "file":
            files.append(entry)
        elif entry.get("type") == "dir":
            files.extend(_walk_skill_dir(client, entry["path"]))
    return files


def install_skill(db: Session, user_id: str, name: str) -> UserSkill:
    """安装:临时目录全量下载校验 → 上传 MinIO → 最后写 PG 清单(失败即清理)"""
    if not SKILL_NAME_PATTERN.match(name):
        raise SkillServiceError(f"技能名称不合法: {name}")

    existing = db.query(UserSkill).filter_by(user_id=user_id, name=name).first()
    if existing is not None:
        raise SkillServiceError(f"技能已安装: {name}")

    storage = _get_storage()
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"skill-{uuid.uuid4().hex[:8]}-"))
    prefix = f"skills/{user_id}/{name}"
    try:
        with _build_client() as client:
            files = _walk_skill_dir(client, name)
            if not files:
                raise SkillServiceError(f"技能目录不存在或为空: {name}")
            if len(files) > SKILL_MAX_FILES:
                raise SkillServiceError(f"技能文件数超限({len(files)} > {SKILL_MAX_FILES})")
            for entry in files:
                if int(entry.get("size", 0)) > SKILL_MAX_FILE_BYTES:
                    raise SkillServiceError(f"文件大小超限: {entry['path']}")
                raw = client.get(entry["download_url"])
                if raw.status_code != 200:
                    raise SkillServiceError(f"下载失败: {entry['path']}")
                rel = entry["path"][len(name):].strip("/")
                target = tmp_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw.content)

        skill_md = (tmp_dir / "SKILL.md").read_text(encoding="utf-8") if (tmp_dir / "SKILL.md").exists() else None
        if skill_md is None:
            raise SkillServiceError(f"技能缺少 SKILL.md: {name}")
        meta = parse_skill_md(skill_md, name)
        if meta is None:
            raise SkillServiceError(f"SKILL.md 不合规(name 必须等于目录名且为小写-数字-连字符)")

        storage.upload_prefix(tmp_dir, prefix)

        row = UserSkill(
            user_id=user_id,
            name=name,
            version=latest_commit_sha(),
            description=meta["description"],
            source=f"{SKILL_REGISTRY_OWNER}/{SKILL_REGISTRY_REPO}@{SKILL_REGISTRY_REF}",
        )
        db.add(row)
        db.commit()
        return row
    except Exception:
        storage.delete_prefix(prefix)  # 不留半成品(spec §5)
        db.rollback()
        raise
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def uninstall_skill(db: Session, user_id: str, name: str) -> None:
    if not SKILL_NAME_PATTERN.match(name):
        raise SkillServiceError(f"技能名称不合法: {name}")
    row = db.query(UserSkill).filter_by(user_id=user_id, name=name).first()
    if row is None:
        raise SkillServiceError(f"未安装该技能: {name}")
    _get_storage().delete_prefix(f"skills/{user_id}/{name}")
    db.delete(row)
    db.commit()


def list_installed(db: Session, user_id: str) -> list[UserSkill]:
    return (
        db.query(UserSkill)
        .filter_by(user_id=user_id)
        .order_by(UserSkill.installed_at.desc())
        .all()
    )
```

- [ ] **Step 4: 运行测试通过**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_skill_install.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add trans-mate/app/services/skill_service.py trans-mate/tests/test_skill_install.py
git commit -m "feat: 技能安装/卸载/已装清单(临时目录校验+失败清理+用户隔离)"
```

---

### Task 6: 技能物化器与 Harness 接线(核心)

**Files:**
- Create: `trans-mate/app/llm/harness/skill_materializer.py`
- Modify: `trans-mate/app/llm/harness/deep_agent_harness.py`
- Modify: `trans-mate/app/llm/streaming.py`
- Modify: `trans-mate/main.py`
- Test: `trans-mate/tests/test_skill_materializer.py`
- Test: `trans-mate/tests/test_harness_user_workspace.py`

**Interfaces:**
- Consumes: Task 2 `UserSkill`/`SANDBOX_ROOT`/`SKILL_CACHE_ROOT`;Task 3 `StorageService`;Task 5 `_get_storage`
- Produces:
  - `sync_user_skills(db: Session, user_id: str, storage: StorageService | None = None) -> Path`——返回该用户技能物化缓存目录;清单指纹(sha256 of sorted "name@version")写入目录下 `.manifest`,未变化直接复用;失败记录警告并尽量返回现状
  - `DeepAgentHarness.astream(history, thread_id, user_id: str | None = None)`(新增第三参,默认 None 走现状)
  - 模块级 `_build_backend(user_id: str) -> BackendProtocol`、`_build_agent(model, checkpointer, user_id: str | None = None)`、常量 `AGENT_CACHE_SIZE = 8`
  - `stream_agent_events(history, thread_id, user_id=None)`(透传)
- 行为契约:agent 工厂缓存键=user_id(LRU);user_id=None 保持现状(默认虚拟 FS);system prompt 增加沙箱/技能库说明

- [ ] **Step 1: 写物化器失败测试**

`trans-mate/tests/test_skill_materializer.py`:

```python
"""技能物化器:按 PG 清单从存储物化到本地缓存目录"""
from pathlib import Path

import pytest

from app.llm.harness.skill_materializer import sync_user_skills
from app.models.skill import UserSkill
from tests.fake_storage import FakeStorage


def _seed(db, user_id, skills):
    for name, version in skills:
        db.add(UserSkill(user_id=user_id, name=name, version=version, description="",
                         source="test"))
    db.commit()


@pytest.mark.unit
def test_sync_downloads_all_skills(db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.SKILL_CACHE_ROOT", str(tmp_path))
    storage = FakeStorage()
    storage.put_bytes("skills/u1/demo-a/SKILL.md", b"---\nname: demo-a\n---\nA")
    storage.put_bytes("skills/u1/demo-b/SKILL.md", b"---\nname: demo-b\n---\nB")
    _seed(db, "u1", [("demo-a", "v1"), ("demo-b", "v1")])

    cache_dir = sync_user_skills(db, "u1", storage=storage)
    assert (Path(cache_dir) / "demo-a" / "SKILL.md").read_bytes().startswith(b"---")
    assert (Path(cache_dir) / "demo-b" / "SKILL.md").exists()
    assert (Path(cache_dir) / ".manifest").exists()


@pytest.mark.unit
def test_sync_skips_when_fingerprint_unchanged(db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.SKILL_CACHE_ROOT", str(tmp_path))
    storage = FakeStorage()
    storage.put_bytes("skills/u1/demo-a/SKILL.md", b"A")
    _seed(db, "u1", [("demo-a", "v1")])
    sync_user_skills(db, "u1", storage=storage)
    # 删掉对象模拟"不应再下载"
    storage.delete_prefix("skills/")
    cache_dir = sync_user_skills(db, "u1", storage=storage)
    assert (Path(cache_dir) / "demo-a" / "SKILL.md").exists()  # 复用本地缓存


@pytest.mark.unit
def test_sync_refreshes_when_version_changes(db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.SKILL_CACHE_ROOT", str(tmp_path))
    storage = FakeStorage()
    storage.put_bytes("skills/u1/demo-a/SKILL.md", b"old")
    _seed(db, "u1", [("demo-a", "v1")])
    sync_user_skills(db, "u1", storage=storage)
    storage.put_bytes("skills/u1/demo-a/SKILL.md", b"new")
    row = db.query(UserSkill).filter_by(user_id="u1", name="demo-a").first()
    row.version = "v2"
    db.commit()
    cache_dir = sync_user_skills(db, "u1", storage=storage)
    assert (Path(cache_dir) / "demo-a" / "SKILL.md").read_bytes() == b"new"


@pytest.mark.unit
def test_sync_failure_degrades_to_empty(db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.SKILL_CACHE_ROOT", str(tmp_path))

    class BrokenStorage(FakeStorage):
        def list_keys(self, prefix):
            raise RuntimeError("minio down")

    _seed(db, "u1", [("demo-a", "v1")])
    cache_dir = sync_user_skills(db, "u1", storage=BrokenStorage())
    assert Path(cache_dir).exists()  # 返回空目录,不抛异常(降级运行)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_skill_materializer.py -v`
Expected: FAIL,模块不存在

- [ ] **Step 3: 实现物化器**

`trans-mate/app/llm/harness/skill_materializer.py`:

```python
"""
技能物化器:PG 清单 → 本地缓存目录(按清单指纹增量)
"""
import hashlib
import logging
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.core import config
from app.models.skill import UserSkill
from app.services.skill_service import _get_storage
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

MANIFEST_FILE = ".manifest"


def _fingerprint(rows: list[UserSkill]) -> str:
    parts = sorted(f"{r.name}@{r.version}" for r in rows)
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def sync_user_skills(
    db: Session, user_id: str, storage: StorageService | None = None
) -> Path:
    """把用户云端技能物化到 SKILL_CACHE_ROOT/{user_id}/;失败降级为空/现状目录

    配置经 config 模块在调用时读取(便于测试 monkeypatch app.core.config.*)
    """
    storage = storage or _get_storage()
    cache_dir = Path(config.SKILL_CACHE_ROOT) / user_id
    rows = db.query(UserSkill).filter_by(user_id=user_id).all()
    fingerprint = _fingerprint(rows)

    staging: Path | None = None
    try:
        if (
            (cache_dir / MANIFEST_FILE).exists()
            and (cache_dir / MANIFEST_FILE).read_text(encoding="utf-8") == fingerprint
        ):
            return cache_dir  # 清单未变,复用缓存

        staging = cache_dir.parent / f".{user_id}.staging"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True, exist_ok=True)
        for row in rows:
            storage.download_prefix(f"skills/{user_id}/{row.name}", staging / row.name)
        # 原子替换:staging -> cache_dir
        shutil.rmtree(cache_dir, ignore_errors=True)
        staging.rename(cache_dir)
        (cache_dir / MANIFEST_FILE).write_text(fingerprint, encoding="utf-8")
    except Exception as exc:
        logger.warning("用户 %s 技能物化失败,降级现有缓存: %s", user_id, exc)
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        cache_dir.mkdir(parents=True, exist_ok=True)  # 至少保证目录存在(可能为空)
    return cache_dir
```

- [ ] **Step 4: 运行物化器测试通过**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_skill_materializer.py -v`
Expected: 4 passed

- [ ] **Step 5: 写 Harness 接线失败测试**

`trans-mate/tests/test_harness_user_workspace.py`:

```python
"""Harness 用户工作区接线:工厂缓存/后端路由/user_id=None 回归"""
import pytest

import app.llm.harness.deep_agent_harness as dah
from app.llm.harness.deep_agent_harness import DeepAgentHarness


class _RecordingHarness(DeepAgentHarness):
    """不触发重量级初始化,只测工厂路径"""
    pass


@pytest.fixture
def captured(monkeypatch, tmp_path, db):
    """捕获 create_deep_agent 调用参数;物化器直写空缓存目录"""
    captured_calls = []
    import deepagents

    def fake_create_deep_agent(**kwargs):
        captured_calls.append(kwargs)
        return object()

    monkeypatch.setattr(deepagents, "create_deep_agent", fake_create_deep_agent)
    monkeypatch.setattr(dah, "AGENT_CACHE_SIZE", 2)
    monkeypatch.setattr("app.core.config.SANDBOX_ROOT", str(tmp_path / "sandbox"))
    monkeypatch.setattr("app.core.config.SKILL_CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setattr(
        dah, "sync_user_skills", lambda db_, uid, **kw: __import__("pathlib").Path(
            __import__("app.core.config", fromlist=["SKILL_CACHE_ROOT"]).SKILL_CACHE_ROOT, uid
        )
    )
    return captured_calls


@pytest.mark.unit
def test_build_agent_with_user_uses_skills_and_composite(captured, db):
    dah._build_agent(model=object(), checkpointer=None, user_id="u1")
    kwargs = captured[-1]
    assert kwargs["skills"] == ["/skills/"]
    from deepagents.backends.composite import CompositeBackend

    assert isinstance(kwargs["backend"], CompositeBackend)


@pytest.mark.unit
def test_build_agent_without_user_keeps_legacy(captured, db):
    dah._build_agent(model=object(), checkpointer=None, user_id=None)
    kwargs = captured[-1]
    assert "skills" not in kwargs and "backend" not in kwargs


@pytest.mark.unit
def test_agent_cache_keyed_by_user_and_lru(captured, db):
    harness = DeepAgentHarness()
    harness._model = object()  # 跳过真实模型构造
    a1 = harness._get_agent_for_user("u1", db)
    a1_again = harness._get_agent_for_user("u1", db)
    assert a1 is a1_again
    harness._get_agent_for_user("u2", db)
    harness._get_agent_for_user("u3", db)  # AGENT_CACHE_SIZE=2 → u1 被逐出
    assert "u1" not in harness._user_agents
    assert len(harness._user_agents) == 2


@pytest.mark.unit
def test_resolve_agent_none_user_returns_legacy(captured, db, monkeypatch):
    async def _noop():  # initialize 为 async,monkeypatch 需返回协程
        pass

    harness = DeepAgentHarness()
    legacy = object()
    monkeypatch.setattr(harness, "initialize", _noop)
    harness._agent = legacy
    harness._initialized = True
    harness._model = object()  # 跳过真实模型构造(工厂路径需要)
    # user_id=None → 传统单例;非 None → 工厂缓存
    assert harness._resolve_agent(None, db) is legacy
    assert harness._resolve_agent("u1", db) is not legacy
```

注:astream 异步生成器的端到端驱动在 Task 11 集成测试覆盖;本任务只钉选择逻辑。

- [ ] **Step 6: 运行确认失败**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_harness_user_workspace.py -v`
Expected: FAIL,`_get_agent_for_user`/`_resolve_agent` 未定义

- [ ] **Step 7: 改造 deep_agent_harness.py**

关键修改(保持既有结构,列出全部新增/变更):

`deep_agent_harness.py` 头部 import 区追加:

```python
from collections import OrderedDict

from sqlalchemy.orm import Session
```

(SANDBOX_ROOT/SKILL_CACHE_ROOT 不做顶层导入,统一在 `_build_backend` 内经 `from app.core import config` 调用时读取,便于测试 monkeypatch。)

模块常量与函数(放在 `STOCK_TOOLS` 之后):

```python
AGENT_CACHE_SIZE = 8  # 每用户 agent 实例 LRU 上限


def _build_backend(user_id: str):
    """用户工作区后端:默认路由=用户沙箱(防越界),/skills/=技能物化缓存"""
    from app.core import config

    from deepagents.backends.composite import CompositeBackend
    from deepagents.backends.filesystem import FilesystemBackend

    sandbox = os.path.join(config.SANDBOX_ROOT, user_id)
    os.makedirs(sandbox, exist_ok=True)
    skill_cache = os.path.join(config.SKILL_CACHE_ROOT, user_id)
    os.makedirs(skill_cache, exist_ok=True)
    return CompositeBackend(
        default=FilesystemBackend(root_dir=sandbox, virtual_mode=True),
        routes={"/skills/": FilesystemBackend(root_dir=skill_cache, virtual_mode=True)},
    )
```

`_build_agent` 变更(签名加 user_id,组装分支):

```python
def _build_agent(model, checkpointer, user_id: str | None = None):
    """组装 deepagents 主智能体;user_id 非空时启用云工作区(skills+沙箱)"""
    from deepagents import create_deep_agent
    from langchain.agents.middleware import TodoListMiddleware

    kwargs = dict(
        model=model,
        tools=[search_knowledge_base, get_weather, web_search],
        system_prompt=MAIN_AGENT_PROMPT,
        middleware=[TodoListMiddleware()],
        subagents=[_build_stock_subagent()],
        checkpointer=checkpointer,
        name=AGENT_NAME,
    )
    if user_id is not None:
        kwargs["skills"] = ["/skills/"]
        kwargs["backend"] = _build_backend(user_id)
    return create_deep_agent(**kwargs)
```

`MAIN_AGENT_PROMPT` 在现有文本末尾追加(工作区段;制品段 Task 8 再加):

```python
MAIN_AGENT_PROMPT = """你是 TransMate 智能助手，帮助用户完成资料检索、天气查询、股票数据采集等任务。

工具使用指引：
- 用户问题可能与已导入文档资料相关时，优先调用 search_knowledge_base 检索本地知识库
- 需要实时网络信息时调用 web_search；天气查询调用 get_weather
- 涉及股票、指数、基金、行情、财务指标、估值等数据时，通过 task 工具派发 stock_data_expert 子智能体采集
- 复杂多步骤任务先用 write_todos 制定计划，并随进展更新计划状态

用户工作区（启用时）：
- 你的文件操作限制在当前用户的工作沙箱内；当前会话的工作目录是 sessions/{会话ID}/，用户其他会话的成果在 sessions/ 的兄弟目录中，可以直接引用
- /skills/ 是已安装技能库（只读，禁止写入）：任务匹配某技能时，先 read_file 读取其 SKILL.md（limit=1000）并按其指引执行
"""
```

`DeepAgentHarness.__init__` 追加两个实例字段:

```python
        self._user_agents: "OrderedDict[str, Any]" = OrderedDict()
```

`DeepAgentHarness` 类内追加方法:

```python
    def _resolve_agent(self, user_id: Optional[str], db: Session | None):
        """user_id 为空 → 传统单例 agent;否则按用户工厂缓存取"""
        if user_id is None:
            return self._agent
        return self._get_agent_for_user(user_id, db)

    def _get_agent_for_user(self, user_id: str, db: Session | None):
        from app.llm.harness.skill_materializer import sync_user_skills

        if user_id in self._user_agents:
            self._user_agents.move_to_end(user_id)
            return self._user_agents[user_id]
        # 物化失败降级为空缓存目录,不阻塞对话(spec §5)
        sync_user_skills(db, user_id)
        model = self._model or _build_model()
        agent = _build_agent(model, self._checkpointer, user_id=user_id)
        self._user_agents[user_id] = agent
        while len(self._user_agents) > AGENT_CACHE_SIZE:
            self._user_agents.popitem(last=False)
        return agent
```

`astream` 变更(签名+agent 选择+数据库会话):

```python
    async def astream(
        self,
        history: List[BaseMessage],
        thread_id: str,
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        """驱动 agent 一轮：产出归一化事件（第一个事件前补 agent_start）

        user_id 非空时启用该用户的云工作区 agent（沙箱+技能库）。
        """
        await self.initialize()
        config = {"configurable": {"thread_id": thread_id}}
        messages = await self._resolve_input_messages(history, config)

        db = None
        try:
            if user_id is not None:
                from app.core.database import SessionLocal

                db = SessionLocal()
            agent = self._resolve_agent(user_id, db)
        finally:
            if db is not None:
                db.close()

        started = False
        state: dict = {}
        async for raw in agent.astream_events({"messages": messages}, config, version="v2"):
            if not started:
                started = True
                yield {"type": EVENT_AGENT_START, "agent": AGENT_NAME}
            for event in self._adapt_event(raw, state):
                yield event
```

`aclose()` 在 finally 追加 `self._user_agents.clear()`。

`trans-mate/app/llm/streaming.py` 的 `stream_agent_events` 签名与调用改为透传:

```python
async def stream_agent_events(
    history: List[BaseMessage], thread_id: str, user_id: str | None = None
) -> AsyncGenerator[dict, None]:
```

调用处:`get_agent_harness().astream(history, thread_id, user_id=user_id)`。

`trans-mate/main.py` 的 `run_agent_stream` 内,`stream_agent_events` 调用前查会话归属:

```python
        conversation = chat_service.get_conversation(db, conversation_id)
        user_id = conversation.user_id if conversation else None
        async for event in stream_agent_events(history, f"conv-{conversation_id}", user_id=user_id):
```

- [ ] **Step 8: 运行新测试与全量回归**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_harness_user_workspace.py tests/test_harness_base.py tests/test_harness_events.py tests/test_streaming.py -v`
Expected: 全部 passed(旧测试证明 user_id=None 回归无恙)

- [ ] **Step 9: Commit**

```bash
git add trans-mate/app/llm/harness/skill_materializer.py trans-mate/app/llm/harness/deep_agent_harness.py trans-mate/app/llm/streaming.py trans-mate/main.py trans-mate/tests/test_skill_materializer.py trans-mate/tests/test_harness_user_workspace.py
git commit -m "feat: harness 接入用户云工作区(CompositeBackend 路由+技能物化+按用户工厂缓存)"
```

---

### Task 7: Skill API 路由

**Files:**
- Create: `trans-mate/app/schemas/skill.py`
- Create: `trans-mate/app/base/skill_routes.py`
- Modify: `trans-mate/main.py`(注册路由)
- Test: `trans-mate/tests/test_skill_routes.py`

**Interfaces:**
- Consumes: Task 4/5 `list_registry/list_installed/install_skill/uninstall_skill/clear_registry_cache/SkillServiceError`;conftest `db` fixture;`app.core.database.get_db`
- Produces(前端 Task 9 依赖的 HTTP 契约):
  - `GET /api/skills/registry` → `{"items": [{name, description, license, installed}]}`
  - `GET /api/skills/installed?user_id=` → `{"items": [{name, version, description, source, installed_at}]}`
  - `POST /api/skills/install` body `{user_id, name}` → `{"name", "version"}`;业务异常 400
  - `DELETE /api/skills/{name}?user_id=` → `{"success": true}`
  - `POST /api/skills/refresh` → `{"success": true}`(清 TTL 缓存)

- [ ] **Step 1: 写失败测试**

```python
"""技能路由:全离线(MockTransport+FakeStorage+内存库)"""
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import app.services.skill_service as skill_service
from app.core.database import get_db
import main as main_module


@pytest.fixture
def client(monkeypatch, db):
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    session_factory = sessionmaker(bind=db.bind, autoflush=False, autocommit=False)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    main_module.app.dependency_overrides[get_db] = override_get_db
    # 注入离线 GitHub 与存储
    monkeypatch.setattr(skill_service, "_registry_transport", _registry_transport())
    monkeypatch.setattr(skill_service, "_storage_singleton_override",
                        __import__("tests.fake_storage", fromlist=["FakeStorage"]).FakeStorage())
    with TestClient(main_module.app) as test_client:
        yield test_client
    main_module.app.dependency_overrides.clear()


def _registry_transport():
    def _handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "sha1"}, request=request)
        if path.endswith("/contents/"):
            return httpx.Response(200, json=[
                {"name": "demo-skill", "path": "demo-skill", "type": "dir"},
            ], request=request)
        if path.endswith("/contents/demo-skill"):
            return httpx.Response(200, json=[
                {"name": "SKILL.md", "path": "demo-skill/SKILL.md", "type": "file",
                 "size": 10, "download_url": "https://raw.test/demo-skill/SKILL.md"},
            ], request=request)
        if "raw.test" in str(request.url):
            return httpx.Response(
                200, text="---\nname: demo-skill\ndescription: 演示\n---\n# D\n",
                request=request)
        return httpx.Response(404, request=request)

    return httpx.MockTransport(_handler)


@pytest.mark.unit
def test_registry_lists_with_installed_flag(client):
    resp = client.get("/api/skills/registry")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["name"] == "demo-skill"
    assert item["installed"] is False


@pytest.mark.unit
def test_install_and_uninstall_roundtrip(client):
    resp = client.post("/api/skills/install", json={"user_id": "u1", "name": "demo-skill"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "demo-skill"

    listed = client.get("/api/skills/installed", params={"user_id": "u1"}).json()["items"]
    assert [i["name"] for i in listed] == ["demo-skill"]

    reg = client.get("/api/skills/registry").json()["items"][0]
    assert reg["installed"] is True

    del_resp = client.delete("/api/skills/demo-skill", params={"user_id": "u1"})
    assert del_resp.status_code == 200
    assert client.get("/api/skills/installed", params={"user_id": "u1"}).json()["items"] == []


@pytest.mark.unit
def test_install_duplicate_returns_400(client):
    client.post("/api/skills/install", json={"user_id": "u1", "name": "demo-skill"})
    resp = client.post("/api/skills/install", json={"user_id": "u1", "name": "demo-skill"})
    assert resp.status_code == 400


@pytest.mark.unit
def test_refresh_clears_cache(client):
    assert client.post("/api/skills/refresh").status_code == 200
```

- [ ] **Step 2: 运行确认失败**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_skill_routes.py -v`
Expected: FAIL,404(路由不存在)

- [ ] **Step 3: 实现 schema 与路由**

`trans-mate/app/schemas/skill.py`:

```python
"""技能相关 Pydantic 模型"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class RegistryItem(BaseModel):
    name: str
    description: str
    license: str = ""
    installed: bool = False


class RegistryResponse(BaseModel):
    items: List[RegistryItem]


class InstalledItem(BaseModel):
    name: str
    version: str
    description: str = ""
    source: str = ""
    installed_at: Optional[datetime] = None


class InstalledResponse(BaseModel):
    items: List[InstalledItem]


class InstallRequest(BaseModel):
    user_id: str
    name: str


class InstallResponse(BaseModel):
    name: str
    version: str
```

`trans-mate/app/base/skill_routes.py`:

```python
"""
技能路由:注册表浏览/安装/卸载/已装列表
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.skill import (
    InstallRequest,
    InstallResponse,
    InstalledItem,
    InstalledResponse,
    RegistryItem,
    RegistryResponse,
)
from app.services import skill_service
from app.services.skill_service import SkillServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["技能"])


@router.get("/registry", response_model=RegistryResponse)
async def list_registry_route():
    """浏览技能仓库(installed 标记需 user_id)"""
    try:
        items = skill_service.list_registry()
        return RegistryResponse(items=[RegistryItem(**i) for i in items])
    except SkillServiceError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc


@router.get("/registry/{user_id}", response_model=RegistryResponse)
async def list_registry_for_user(user_id: str, db: Session = Depends(get_db)):
    """浏览技能仓库并标记该用户已装项"""
    try:
        items = skill_service.list_registry()
        installed = {r.name for r in skill_service.list_installed(db, user_id)}
        return RegistryResponse(
            items=[RegistryItem(**i, installed=i["name"] in installed) for i in items]
        )
    except SkillServiceError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc


@router.get("/installed", response_model=InstalledResponse)
async def list_installed_route(user_id: str, db: Session = Depends(get_db)):
    rows = skill_service.list_installed(db, user_id)
    return InstalledResponse(items=[InstalledItem(
        name=r.name, version=r.version, description=r.description,
        source=r.source, installed_at=r.installed_at,
    ) for r in rows])


@router.post("/install", response_model=InstallResponse)
async def install_route(request: InstallRequest, db: Session = Depends(get_db)):
    try:
        row = skill_service.install_skill(db, request.user_id, request.name)
        return InstallResponse(name=row.name, version=row.version)
    except SkillServiceError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.delete("/{name}")
async def uninstall_route(name: str, user_id: str, db: Session = Depends(get_db)):
    try:
        skill_service.uninstall_skill(db, user_id, name)
        return {"success": True}
    except SkillServiceError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post("/refresh")
async def refresh_route():
    skill_service.clear_registry_cache()
    return {"success": True}
```

`main.py` 路由注册区追加:

```python
from app.base.skill_routes import router as skill_router
# ...
app.include_router(skill_router)
```

- [ ] **Step 4: 运行测试通过**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_skill_routes.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add trans-mate/app/schemas/skill.py trans-mate/app/base/skill_routes.py trans-mate/main.py trans-mate/tests/test_skill_routes.py
git commit -m "feat: 技能 API(注册表/安装/卸载/已装列表/刷新)"
```

---

### Task 8: save_artifact 工具与制品 API

**Files:**
- Create: `trans-mate/app/llm/tools/artifact_tool.py`
- Create: `trans-mate/app/schemas/artifact.py`
- Create: `trans-mate/app/base/artifact_routes.py`
- Modify: `trans-mate/app/llm/harness/deep_agent_harness.py`(user_id 分支挂工具+提示词制品段)
- Modify: `trans-mate/main.py`(注册路由)
- Test: `trans-mate/tests/test_artifact_tool.py`
- Test: `trans-mate/tests/test_artifact_routes.py`

**Interfaces:**
- Consumes: Task 2 `Artifact`/`SANDBOX_ROOT`/`ARTIFACT_MAX_BYTES`/`ARTIFACT_MAX_COUNT`;Task 3 `StorageService`;Task 6 `DeepAgentHarness` user_id 分支
- Produces:
  - `make_save_artifact_tool(user_id: str, storage: StorageService | None = None)` → LangChain `@tool` `save_artifact(source_path: str, name: str = "", description: str = "") -> str`;从 `config["configurable"]["thread_id"]` 解析 conversation_id;成功返回含制品 id 的中文消息,失败返回错误文案(模型可自纠)
  - HTTP:`GET /api/artifacts?user_id=&conversation_id=&page=1&page_size=20` → `{"items": [...], "total": n}`;`GET /api/artifacts/{artifact_id}/download?user_id=` → `{"url": <presigned>}`(1 小时)

- [ ] **Step 1: 写工具失败测试**

`trans-mate/tests/test_artifact_tool.py`:

```python
"""save_artifact 工具:沙箱路径解析/上传/上限/错误文案"""
import pytest
from langchain_core.runnables import RunnableConfig

from app.llm.tools.artifact_tool import make_save_artifact_tool
from app.models.skill import Artifact
from tests.fake_storage import FakeStorage


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.SANDBOX_ROOT", str(tmp_path))
    (tmp_path / "u1" / "sessions" / "conv-9").mkdir(parents=True)
    (tmp_path / "u1" / "sessions" / "conv-9" / "report.pptx").write_bytes(b"ppt-bytes")
    return tmp_path


def _invoke(tool, source_path, config=None):
    config = config or {"configurable": {"thread_id": "conv-9"}}
    return tool.invoke({"source_path": source_path, "name": "报告"}, config=config)


@pytest.mark.unit
def test_save_artifact_success(db, sandbox):
    storage = FakeStorage()
    tool = make_save_artifact_tool("u1", storage=storage)
    result = _invoke(tool, "/sessions/conv-9/report.pptx")
    assert "已保存" in result
    row = db.query(Artifact).filter_by(user_id="u1").one()
    assert row.conversation_id == 9
    assert row.filename == "报告.pptx" or row.filename == "report.pptx"
    assert row.size == len(b"ppt-bytes")
    keys = storage.list_keys(f"artifacts/u1/{row.id}/") if row.id else storage.list_keys("artifacts/u1/")
    assert keys  # 已上传


@pytest.mark.unit
def test_save_artifact_missing_file(db, sandbox):
    tool = make_save_artifact_tool("u1", storage=FakeStorage())
    result = _invoke(tool, "/sessions/conv-9/nope.pptx")
    assert "不存在" in result
    assert db.query(Artifact).count() == 0


@pytest.mark.unit
def test_save_artifact_blocks_traversal(db, sandbox):
    tool = make_save_artifact_tool("u1", storage=FakeStorage())
    result = _invoke(tool, "/../../etc/passwd")
    assert "沙箱" in result or "越界" in result or "无效" in result


@pytest.mark.unit
def test_save_artifact_enforces_count_limit(db, sandbox, monkeypatch):
    from app.core.config import ARTIFACT_MAX_COUNT
    monkeypatch.setattr("app.core.config.ARTIFACT_MAX_COUNT", 1)
    db.add(Artifact(user_id="u1", conversation_id=1, filename="a.bin", size=1,
                    storage_key="artifacts/u1/x/a.bin"))
    db.commit()
    tool = make_save_artifact_tool("u1", storage=FakeStorage())
    result = _invoke(tool, "/sessions/conv-9/report.pptx")
    assert "上限" in result
```

- [ ] **Step 2: 运行确认失败**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_artifact_tool.py -v`
Expected: FAIL,模块不存在

- [ ] **Step 3: 实现工具**

`trans-mate/app/llm/tools/artifact_tool.py`:

```python
"""
save_artifact 工具:把沙箱内成果文件保存为用户制品(MinIO+PG)
user_id 在 agent 工厂构建时闭包注入;conversation_id 从 RunnableConfig 的 thread_id 解析
"""
import logging
import uuid
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
        config: RunnableConfig,
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

            thread_id = (config.get("configurable") or {}).get("thread_id", "")
            conversation_id = (
                int(thread_id.removeprefix("conv-")) if thread_id.startswith("conv-") else 0
            )
            artifact_id = uuid.uuid4().hex
            filename = f"{name}{real.suffix}" if name else real.name
            storage_key = f"artifacts/{user_id}/{artifact_id}/{filename}"
            storage.put_bytes(storage_key, real.read_bytes())
            row = Artifact(
                user_id=user_id,
                conversation_id=conversation_id,
                filename=filename,
                size=size,
                storage_key=storage_key,
                description=description,
            )
            db.add(row)
            db.commit()
            return f"已保存制品：{filename}（id={row.id}）"
        except Exception as exc:  # 工具层兜底:返回文案让模型自纠
            db.rollback()
            logger.warning("save_artifact 失败 user=%s path=%s: %s", user_id, source_path, exc)
            return f"保存失败：{exc}"
        finally:
            db.close()

    return save_artifact
```

- [ ] **Step 4: 运行工具测试通过**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_artifact_tool.py -v`
Expected: 4 passed

- [ ] **Step 5: 写制品路由失败测试**

`trans-mate/tests/test_artifact_routes.py`:

```python
"""制品列表/下载路由"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
from app.models.skill import Artifact
import main as main_module


@pytest.fixture
def client(monkeypatch, db):
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    session_factory = sessionmaker(bind=db.bind, autoflush=False, autocommit=False)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    main_module.app.dependency_overrides[get_db] = override_get_db
    with TestClient(main_module.app) as test_client:
        yield test_client
    main_module.app.dependency_overrides.clear()


@pytest.mark.unit
def test_list_artifacts_filters_by_user(client, db):
    db.add(Artifact(user_id="u1", conversation_id=9, filename="a.pptx", size=3,
                    storage_key="artifacts/u1/1/a.pptx"))
    db.add(Artifact(user_id="u2", conversation_id=1, filename="b.pptx", size=4,
                    storage_key="artifacts/u2/2/b.pptx"))
    db.commit()
    resp = client.get("/api/artifacts", params={"user_id": "u1"})
    items = resp.json()["items"]
    assert [i["filename"] for i in items] == ["a.pptx"]
    assert resp.json()["total"] == 1


@pytest.mark.unit
def test_list_artifacts_filters_by_conversation(client, db):
    db.add(Artifact(user_id="u1", conversation_id=9, filename="a.pptx", size=3,
                    storage_key="artifacts/u1/1/a.pptx"))
    db.add(Artifact(user_id="u1", conversation_id=8, filename="c.pptx", size=3,
                    storage_key="artifacts/u1/3/c.pptx"))
    db.commit()
    resp = client.get("/api/artifacts", params={"user_id": "u1", "conversation_id": 9})
    assert [i["filename"] for i in resp.json()["items"]] == ["a.pptx"]


@pytest.mark.unit
def test_download_returns_presigned_url(client, db, monkeypatch):
    row = Artifact(user_id="u1", conversation_id=9, filename="a.pptx", size=3,
                   storage_key="artifacts/u1/1/a.pptx")
    db.add(row)
    db.commit()
    from app.base import artifact_routes

    monkeypatch.setattr(
        artifact_routes, "_get_storage_service",
        lambda: type("S", (), {"presigned_get_url": lambda self, k, e: f"fake:///{k}"})(),
    )
    resp = client.get(f"/api/artifacts/{row.id}/download", params={"user_id": "u1"})
    assert resp.status_code == 200
    assert resp.json()["url"].startswith("fake:///")


@pytest.mark.unit
def test_download_other_users_artifact_404(client, db):
    row = Artifact(user_id="u1", conversation_id=9, filename="a.pptx", size=3,
                   storage_key="artifacts/u1/1/a.pptx")
    db.add(row)
    db.commit()
    resp = client.get(f"/api/artifacts/{row.id}/download", params={"user_id": "u2"})
    assert resp.status_code == 404
```

- [ ] **Step 6: 实现制品路由并接线**

`trans-mate/app/schemas/artifact.py`:

```python
"""制品 Pydantic 模型"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ArtifactItem(BaseModel):
    id: int
    conversation_id: int
    filename: str
    size: int
    description: str = ""
    created_at: Optional[datetime] = None


class ArtifactListResponse(BaseModel):
    items: List[ArtifactItem]
    total: int


class ArtifactDownloadResponse(BaseModel):
    url: str
```

`trans-mate/app/base/artifact_routes.py`:

```python
"""制品路由:列表/下载(预签名 URL)"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.skill import Artifact
from app.schemas.artifact import ArtifactDownloadResponse, ArtifactItem, ArtifactListResponse
from app.services.skill_service import _get_storage

PRESIGN_EXPIRES_SECONDS = 3600

router = APIRouter(prefix="/api/artifacts", tags=["制品"])


def _get_storage_service():
    """模块级注入点:测试 monkeypatch 本函数替身存储"""
    return _get_storage()


@router.get("", response_model=ArtifactListResponse)
async def list_artifacts(
    user_id: str,
    conversation_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    query = db.query(Artifact).filter_by(user_id=user_id)
    if conversation_id is not None:
        query = query.filter_by(conversation_id=conversation_id)
    total = query.count()
    rows = (
        query.order_by(Artifact.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ArtifactListResponse(
        items=[ArtifactItem(
            id=r.id, conversation_id=r.conversation_id, filename=r.filename,
            size=r.size, description=r.description, created_at=r.created_at,
        ) for r in rows],
        total=total,
    )


@router.get("/{artifact_id}/download", response_model=ArtifactDownloadResponse)
async def download_artifact(artifact_id: int, user_id: str, db: Session = Depends(get_db)):
    row = db.query(Artifact).filter_by(id=artifact_id, user_id=user_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="制品不存在")
    url = _get_storage_service().presigned_get_url(row.storage_key, PRESIGN_EXPIRES_SECONDS)
    return ArtifactDownloadResponse(url=url)
```

`main.py` 注册:

```python
from app.base.artifact_routes import router as artifact_router
# ...
app.include_router(artifact_router)
```

`deep_agent_harness.py` user_id 分支挂工具与提示词:

`_build_agent` 的 kwargs 组装中,user_id 分支追加:

```python
    if user_id is not None:
        from app.llm.tools.artifact_tool import make_save_artifact_tool

        kwargs["skills"] = ["/skills/"]
        kwargs["backend"] = _build_backend(user_id)
        kwargs["tools"] = kwargs["tools"] + [make_save_artifact_tool(user_id)]
```

`MAIN_AGENT_PROMPT` 的"用户工作区"段末尾追加一行:

```
- 完成可交付成果（如 PPT/PDF/报告/代码包等文件）后，调用 save_artifact 将其保存为制品，供用户随时跨设备下载
```

- [ ] **Step 7: 运行全部新测试与回归**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_artifact_tool.py tests/test_artifact_routes.py tests/test_harness_user_workspace.py -v`
Expected: 全部 passed

- [ ] **Step 8: Commit**

```bash
git add trans-mate/app/llm/tools/artifact_tool.py trans-mate/app/schemas/artifact.py trans-mate/app/base/artifact_routes.py trans-mate/app/llm/harness/deep_agent_harness.py trans-mate/main.py trans-mate/tests/test_artifact_tool.py trans-mate/tests/test_artifact_routes.py
git commit -m "feat: save_artifact 工具与制品列表/下载 API(预签名 URL)"
```

---

### Task 9: 前端 — 技能页(Skills.vue)

**Files:**
- Create: `trans-mate-web-ui/src/services/skills.ts`
- Create: `trans-mate-web-ui/src/views/Skills.vue`
- Modify: `trans-mate-web-ui/src/router/index.ts`
- Modify: `trans-mate-web-ui/src/views/Home.vue`(侧边栏 footer 加入口按钮)
- Modify: `trans-mate-web-ui/src/i18n/zh.ts`、`trans-mate-web-ui/src/i18n/en.ts`
- Test: `cd trans-mate-web-ui && npm run type-check`

**Interfaces:**
- Consumes: `services/api.ts` 的 `apiClient`(axios 实例,自动带 baseURL/token);`stores/user.ts` 的 `user_id`;Task 7 HTTP 契约
- Produces: 路由 `/skills`;`listRegistry(userId) / listInstalled(userId) / installSkill(userId, name) / uninstallSkill(userId, name) / refreshRegistry()`

- [ ] **Step 1: services/skills.ts**

```typescript
import { apiClient } from './api'

export interface RegistryItem {
  name: string
  description: string
  license: string
  installed: boolean
}

export interface InstalledItem {
  name: string
  version: string
  description: string
  source: string
  installed_at: string | null
}

export async function listRegistry(userId: string): Promise<RegistryItem[]> {
  const { data } = await apiClient.get(`/api/skills/registry/${encodeURIComponent(userId)}`)
  return data.items
}

export async function listInstalled(userId: string): Promise<InstalledItem[]> {
  const { data } = await apiClient.get('/api/skills/installed', { params: { user_id: userId } })
  return data.items
}

export async function installSkill(userId: string, name: string): Promise<void> {
  await apiClient.post('/api/skills/install', { user_id: userId, name })
}

export async function uninstallSkill(userId: string, name: string): Promise<void> {
  await apiClient.delete(`/api/skills/${encodeURIComponent(name)}`, { params: { user_id: userId } })
}

export async function refreshRegistry(): Promise<void> {
  await apiClient.post('/api/skills/refresh')
}
```

注:`services/api.ts` 当前是否具名导出 `apiClient` 需现场确认;若为默认导出则改 `import apiClient from './api'`。

- [ ] **Step 2: views/Skills.vue**

```vue
<template>
  <div class="skills-page">
    <header class="skills-header">
      <h1>{{ t('skills.title') }}</h1>
      <el-button :loading="refreshing" @click="onRefresh">{{ t('skills.refresh') }}</el-button>
    </header>

    <el-row :gutter="16">
      <el-col :span="14">
        <el-card>
          <template #header>{{ t('skills.registry') }}</template>
          <el-input
            v-model="keyword"
            :placeholder="t('skills.searchPlaceholder')"
            clearable
            class="skills-search"
          />
          <div v-loading="loadingRegistry">
            <div v-for="item in filteredRegistry" :key="item.name" class="skill-row">
              <div class="skill-info">
                <div class="skill-name">{{ item.name }}</div>
                <div class="skill-desc">{{ item.description }}</div>
                <div v-if="item.license" class="skill-license">{{ item.license }}</div>
              </div>
              <el-button
                v-if="item.installed"
                type="danger"
                plain
                size="small"
                :loading="pending === item.name"
                @click="onUninstall(item.name)"
              >{{ t('skills.uninstall') }}</el-button>
              <el-button
                v-else
                type="primary"
                size="small"
                :loading="pending === item.name"
                @click="onInstall(item.name)"
              >{{ t('skills.install') }}</el-button>
            </div>
            <el-empty v-if="!loadingRegistry && filteredRegistry.length === 0" :description="t('skills.emptyRegistry')" />
          </div>
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card>
          <template #header>{{ t('skills.installed') }}</template>
          <div v-loading="loadingInstalled">
            <div v-for="item in installed" :key="item.name" class="skill-row">
              <div class="skill-info">
                <div class="skill-name">{{ item.name }}</div>
                <div class="skill-desc">{{ item.description }}</div>
              </div>
              <span class="skill-version">{{ item.version.slice(0, 7) }}</span>
            </div>
            <el-empty v-if="!loadingInstalled && installed.length === 0" :description="t('skills.emptyInstalled')" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import {
  installSkill,
  listInstalled,
  listRegistry,
  refreshRegistry,
  uninstallSkill,
  type InstalledItem,
  type RegistryItem,
} from '../services/skills'
import { useUserStore } from '../stores/user'

const { t } = useI18n()
const userStore = useUserStore()

const registry = ref<RegistryItem[]>([])
const installed = ref<InstalledItem[]>([])
const keyword = ref('')
const loadingRegistry = ref(false)
const loadingInstalled = ref(false)
const refreshing = ref(false)
const pending = ref('')

const filteredRegistry = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return registry.value
  return registry.value.filter(
    (i) => i.name.toLowerCase().includes(kw) || i.description.toLowerCase().includes(kw),
  )
})

async function loadAll() {
  const userId = userStore.user_id
  if (!userId) return
  loadingRegistry.value = true
  loadingInstalled.value = true
  try {
    ;[registry.value, installed.value] = await Promise.all([
      listRegistry(userId),
      listInstalled(userId),
    ])
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('skills.loadFailed'))
  } finally {
    loadingRegistry.value = false
    loadingInstalled.value = false
  }
}

async function onRefresh() {
  refreshing.value = true
  try {
    await refreshRegistry()
    await loadAll()
  } finally {
    refreshing.value = false
  }
}

async function onInstall(name: string) {
  pending.value = name
  try {
    await installSkill(userStore.user_id, name)
    ElMessage.success(t('skills.installDone', { name }))
    await loadAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('skills.installFailed'))
  } finally {
    pending.value = ''
  }
}

async function onUninstall(name: string) {
  pending.value = name
  try {
    await uninstallSkill(userStore.user_id, name)
    ElMessage.success(t('skills.uninstallDone', { name }))
    await loadAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('skills.uninstallFailed'))
  } finally {
    pending.value = ''
  }
}

onMounted(loadAll)
</script>

<style scoped>
.skills-page { max-width: 1100px; margin: 0 auto; padding: 24px; }
.skills-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.skills-search { margin-bottom: 12px; }
.skill-row { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.skill-info { flex: 1; min-width: 0; }
.skill-name { font-weight: 600; }
.skill-desc { color: var(--el-text-color-secondary); font-size: 13px; }
.skill-license { color: var(--el-text-color-placeholder); font-size: 12px; }
.skill-version { color: var(--el-text-color-placeholder); font-size: 12px; }
</style>
```

- [ ] **Step 3: 路由与入口**

`router/index.ts` routes 数组追加:

```typescript
import Skills from '../views/Skills.vue'
// ...
    { path: '/skills', name: 'skills', component: Skills },
```

`Home.vue` 侧边栏 footer(`settings-entry-btn` 按钮旁,约 37-39 行区域)追加入口按钮,`goSettings`(约 397 行)旁追加跳转函数:

```vue
<button class="settings-entry-btn" :title="t('home.skills')" @click="goSkills">
  <!-- 图标沿用项目现有图标组件方式;无则用文字 -->
  <span>{{ t('skills.title') }}</span>
</button>
```

```typescript
const goSkills = () => { router.push('/skills'); };
```

样式类复用 `settings-entry-btn`(与设置按钮同款式,现场按 Home.vue 实际结构调整对齐)。

- [ ] **Step 4: i18n**

`zh.ts` 追加:

```typescript
skills: {
  title: '技能',
  refresh: '刷新仓库',
  registry: '技能仓库',
  installed: '已安装',
  searchPlaceholder: '搜索技能名称或描述',
  install: '安装',
  uninstall: '卸载',
  emptyRegistry: '仓库为空或不可达，可点击刷新重试',
  emptyInstalled: '尚未安装任何技能',
  loadFailed: '加载技能失败',
  installDone: '已安装 {name}',
  installFailed: '安装失败',
  uninstallDone: '已卸载 {name}',
  uninstallFailed: '卸载失败',
},
```

`en.ts` 追加(同名 key 英文文案)。`Home.vue` 用到的 `home.skills: '技能' / 'Skills'` 也加入两文件 `home` 段。

- [ ] **Step 5: 类型检查与手工验收**

Run: `cd trans-mate-web-ui && npm run type-check`
Expected: 无错误
手工:`npm run dev` 打开 `/skills`,确认列表渲染、安装/卸载流程可用(后端以 Task 7 的假数据模式或真实配置运行)。

- [ ] **Step 6: Commit**

```bash
git add trans-mate-web-ui/src/services/skills.ts trans-mate-web-ui/src/views/Skills.vue trans-mate-web-ui/src/router/index.ts trans-mate-web-ui/src/views/Home.vue trans-mate-web-ui/src/i18n/zh.ts trans-mate-web-ui/src/i18n/en.ts
git commit -m "feat(web-ui): 技能管理页(仓库浏览/搜索/安装/卸载)"
```

---

### Task 10: 前端 — 制品面板(Home.vue)

**Files:**
- Create: `trans-mate-web-ui/src/services/artifacts.ts`
- Modify: `trans-mate-web-ui/src/views/Home.vue`
- Modify: `trans-mate-web-ui/src/i18n/zh.ts`、`trans-mate-web-ui/src/i18n/en.ts`
- Test: `cd trans-mate-web-ui && npm run type-check`

**Interfaces:**
- Consumes: Task 8 HTTP 契约;`apiClient`;`userStore.user_id`;Home.vue 现有会话状态(当前 conversation_id 的响应式变量名现场确认)
- Produces: `listArtifacts(userId, conversationId?) / getArtifactDownloadUrl(artifactId, userId)`

- [ ] **Step 1: services/artifacts.ts**

```typescript
import { apiClient } from './api'

export interface ArtifactItem {
  id: number
  conversation_id: number
  filename: string
  size: number
  description: string
  created_at: string | null
}

export async function listArtifacts(
  userId: string,
  conversationId?: number,
): Promise<{ items: ArtifactItem[]; total: number }> {
  const { data } = await apiClient.get('/api/artifacts', {
    params: { user_id: userId, ...(conversationId != null ? { conversation_id: conversationId } : {}) },
  })
  return data
}

export async function getArtifactDownloadUrl(artifactId: number, userId: string): Promise<string> {
  const { data } = await apiClient.get(`/api/artifacts/${artifactId}/download`, {
    params: { user_id: userId },
  })
  return data.url
}
```

- [ ] **Step 2: Home.vue 制品抽屉**

在侧边栏 footer 的技能入口按钮旁加"制品"按钮;在 template 根节点尾部加抽屉:

```vue
<button class="settings-entry-btn" :title="t('artifacts.title')" @click="openArtifacts">
  <span>{{ t('artifacts.title') }}</span>
</button>

<el-drawer v-model="artifactsVisible" :title="t('artifacts.title')" size="360px">
  <el-checkbox v-model="onlyCurrentConversation" @change="loadArtifacts">
    {{ t('artifacts.onlyCurrent') }}
  </el-checkbox>
  <div v-loading="artifactsLoading" class="artifact-list">
    <div v-for="a in artifacts" :key="a.id" class="artifact-row">
      <div class="artifact-info">
        <div class="artifact-name">{{ a.filename }}</div>
        <div class="artifact-meta">{{ formatSize(a.size) }} · {{ a.created_at }}</div>
      </div>
      <el-button size="small" type="primary" plain @click="downloadArtifact(a)">
        {{ t('artifacts.download') }}
      </el-button>
    </div>
    <el-empty v-if="!artifactsLoading && artifacts.length === 0" :description="t('artifacts.empty')" />
  </div>
</el-drawer>
```

script 部分(goSkills 附近)追加:

```typescript
import {
  listArtifacts,
  getArtifactDownloadUrl,
  type ArtifactItem,
} from '../services/artifacts'

const artifactsVisible = ref(false)
const artifactsLoading = ref(false)
const artifacts = ref<ArtifactItem[]>([])
const onlyCurrentConversation = ref(true)

function openArtifacts() {
  artifactsVisible.value = true
  loadArtifacts()
}

async function loadArtifacts() {
  if (!userStore.user_id) return
  artifactsLoading.value = true
  try {
    const convId = onlyCurrentConversation.value ? currentConversationId.value : undefined
    const data = await listArtifacts(userStore.user_id, convId ?? undefined)
    artifacts.value = data.items
  } finally {
    artifactsLoading.value = false
  }
}

async function downloadArtifact(a: ArtifactItem) {
  const url = await getArtifactDownloadUrl(a.id, userStore.user_id)
  window.open(url, '_blank')
}

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}
```

注:`currentConversationId`/`userStore` 以 Home.vue 现有命名为准(现场对齐,不改既有命名);若用户状态另有来源则从其来源取。

- [ ] **Step 3: i18n**

`zh.ts`:

```typescript
artifacts: {
  title: '制品',
  onlyCurrent: '只看当前会话',
  download: '下载',
  empty: '暂无制品，完成任务后由助手保存',
},
```

`en.ts` 同名英文(`Artifacts / Current conversation only / Download / No artifacts yet`),`home.artifacts` 入口文案加入两文件。

- [ ] **Step 4: 类型检查与手工验收**

Run: `cd trans-mate-web-ui && npm run type-check`
Expected: 无错误
手工:后端跑通 Task 8 后,用会话让助手产出一个文件并 `save_artifact`,抽屉里能看到并下载。

- [ ] **Step 5: Commit**

```bash
git add trans-mate-web-ui/src/services/artifacts.ts trans-mate-web-ui/src/views/Home.vue trans-mate-web-ui/src/i18n/zh.ts trans-mate-web-ui/src/i18n/en.ts
git commit -m "feat(web-ui): 制品面板(会话过滤/列表/预签名下载)"
```

---

### Task 11: 全链路集成测试与回归

**Files:**
- Create: `trans-mate/tests/test_skill_integration.py`

**Interfaces:**
- Consumes: Task 1-8 全部产物
- Produces: 端到端行为保障(真实 deepagents 组装+物化技能可扫描、沙箱文件读写、越界拒绝、user_id=None 回归;save_artifact 行为由 Task 8 的工具级测试覆盖)

- [ ] **Step 1: 写集成测试**

```python
"""
端到端集成:用户 agent 组装(技能经路由可扫描)/沙箱文件工具/越界拒绝/旧路径回归
不触网、不连 MinIO(FakeStorage+内存库+真实 deepagents 组装)
"""
import pytest

from app.llm.harness.deep_agent_harness import DeepAgentHarness
from app.models.skill import UserSkill
from tests.fake_storage import FakeStorage


@pytest.fixture
def workspace(tmp_path, monkeypatch, db):
    monkeypatch.setattr("app.core.config.SANDBOX_ROOT", str(tmp_path / "sandbox"))
    monkeypatch.setattr("app.core.config.SKILL_CACHE_ROOT", str(tmp_path / "cache"))
    storage = FakeStorage()
    storage.put_bytes(
        "skills/u1/demo-skill/SKILL.md",
        b"---\nname: demo-skill\ndescription: 演示技能端到端\n---\n# Demo\n",
    )
    db.add(UserSkill(user_id="u1", name="demo-skill", version="v1", description="",
                     source="test"))
    db.commit()
    yield tmp_path, storage


class _FakeModel:
    """最小模型替身:deepagents 组装期只需 bind_tools 可调用"""

    def bind_tools(self, tools, **kwargs):
        return self


@pytest.mark.integration
def test_user_agent_assembles_with_materialized_skills(workspace, db):
    """真实 deepagents 组装 + 物化目录包含该技能(SkillsMiddleware 由 create_deep_agent 挂载)"""
    tmp_path, storage = workspace
    harness = DeepAgentHarness()
    harness._model = _FakeModel()
    agent = harness._get_agent_for_user("u1", db)
    assert agent is not None  # 真实 create_deep_agent(skills=/skills/, backend=Composite)组装成功

    # 物化目录确实包含该技能,且经 CompositeBackend 路由可扫描到
    import pathlib

    from deepagents.middleware.skills import _list_skills

    import app.llm.harness.deep_agent_harness as dah

    cache = pathlib.Path(str(tmp_path / "cache")) / "u1" / "demo-skill" / "SKILL.md"
    assert cache.exists()
    backend = dah._build_backend("u1")
    skills = _list_skills(backend, "/skills/")
    assert [s["name"] for s in skills] == ["demo-skill"]


@pytest.mark.integration
def test_sandbox_file_tools_read_write_and_traversal_denied(workspace, db):
    tmp_path, storage = workspace
    from deepagents.backends.filesystem import FilesystemBackend

    import app.llm.harness.deep_agent_harness as dah

    backend = dah._build_backend("u1")
    # 写入会话目录
    responses = backend.upload_files([("/sessions/conv-1/a.txt", b"hello")])
    assert responses[0].error is None
    resp = backend.download_files(["/sessions/conv-1/a.txt"])[0]
    assert resp.error is None and resp.content == b"hello"
    # 越界拒绝
    assert backend.download_files(["/../../etc/passwd"])[0].error is not None


@pytest.mark.integration
def test_legacy_path_unchanged(db):
    """user_id=None:仍构建默认(无 skills/backend kwargs)agent"""
    import deepagents
    import app.llm.harness.deep_agent_harness as dah

    captured = {}
    original = deepagents.create_deep_agent
    deepagents.create_deep_agent = lambda **kw: captured.update(kw) or object()
    try:
        dah._build_agent(model=object(), checkpointer=None, user_id=None)
    finally:
        deepagents.create_deep_agent = original
    assert "skills" not in captured and "backend" not in captured
```

- [ ] **Step 2: 运行集成测试**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/test_skill_integration.py -v`
Expected: 3 passed(真实 `create_deep_agent(skills=/skills/, backend=Composite)` 组装 + 物化目录经路由可被 `_list_skills` 扫描到;若 `_FakeModel` 不满足 deepagents 组装期所需表面,按报错补齐替身方法,但不得改成 mock 掉 create_deep_agent)

- [ ] **Step 3: 全量回归**

Run: `cd trans-mate && .venv/bin/python -m pytest tests/ -v`
Expected: 全部 passed(存量测试零回归;若存量测试因环境依赖失败,须确认是否本次改动引入,否则向计划维护者报告)

Run: `cd trans-mate-web-ui && npm run type-check`
Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add trans-mate/tests/test_skill_integration.py
git commit -m "test: 技能/沙箱/制品全链路集成测试与回归"
```

---

## 执行注意事项(所有任务通用)

1. **Task 1 是闸门**:若路由/越界行为与预期不符,后续 harness 接线(Task 6)须先调整设计再继续。
2. `deepagents`、`minio` 一律懒导入(模块顶层不 import),沿用 `deep_agent_harness.py` 现有风格。
3. 每个任务收尾必须:新测试绿 + 相关存量测试绿 + commit。禁止"先提交后补测试"。
4. 配置常量的读取约定:运行代码内统一 `from app.core import config` 后在调用时读 `config.<常量>`(不顶层 `from app.core.config import X`),测试统一 monkeypatch `"app.core.config.<常量>"` 即可生效。本计划涉及 `SANDBOX_ROOT`/`SKILL_CACHE_ROOT`/`ARTIFACT_MAX_BYTES`/`ARTIFACT_MAX_COUNT` 四个。
5. 前端两处 `apiClient` 导入方式以 `services/api.ts` 实际导出为准。
