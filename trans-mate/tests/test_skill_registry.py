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
    before = calls["n"]
    assert before < 10  # 首次调用未按目录数线性膨胀
    list_registry()  # 第二次调用应命中 TTL 缓存
    assert calls["n"] == before  # 缓存命中:零新请求


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
