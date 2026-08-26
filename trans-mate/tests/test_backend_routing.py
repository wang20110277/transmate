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
