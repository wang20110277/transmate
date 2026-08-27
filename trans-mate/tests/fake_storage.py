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
            del self.objects[key]

    def delete_key(self, key: str) -> None:
        self.objects.pop(key, None)

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.objects[key] = data

    def get_bytes(self, key: str) -> bytes:
        if key not in self.objects:
            raise KeyError(f"对象不存在: {key}")
        return self.objects[key]

    def presigned_get_url(self, key: str, expires_seconds: int, filename: str | None = None) -> str:
        return f"fake:///{key}"

    def list_keys(self, prefix: str) -> list[str]:
        return sorted(k for k in self.objects if k.startswith(prefix))
