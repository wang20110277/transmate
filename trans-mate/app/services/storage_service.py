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
