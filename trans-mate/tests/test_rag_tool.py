"""
search_knowledge_base 工具测试：正常检索 / 未命中 / 超时降级 / 异常降级
"""
import time

import pytest

from app.llm.tools import rag_tool
from app.llm.tools.rag_tool import search_knowledge_base


@pytest.mark.asyncio
@pytest.mark.unit
async def test_rag_tool_success(monkeypatch):
    monkeypatch.setattr(rag_tool.rag_agent, "retrieve", lambda q: (True, "知识库答案"))
    result = await search_knowledge_base.ainvoke({"query": "问题"})
    assert result == "知识库答案"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_rag_tool_no_hit(monkeypatch):
    monkeypatch.setattr(rag_tool.rag_agent, "retrieve", lambda q: (False, ""))
    result = await search_knowledge_base.ainvoke({"query": "问题"})
    assert "没有找到" in result


@pytest.mark.asyncio
@pytest.mark.unit
async def test_rag_tool_timeout(monkeypatch):
    def slow_retrieve(query):
        time.sleep(1)
        return True, "不该到达"

    monkeypatch.setattr(rag_tool, "RAG_TOOL_TIMEOUT", 0.05)
    monkeypatch.setattr(rag_tool.rag_agent, "retrieve", slow_retrieve)
    result = await search_knowledge_base.ainvoke({"query": "问题"})
    assert "超时" in result


@pytest.mark.asyncio
@pytest.mark.unit
async def test_rag_tool_error(monkeypatch):
    def broken_retrieve(query):
        raise RuntimeError("chroma 挂了")

    monkeypatch.setattr(rag_tool.rag_agent, "retrieve", broken_retrieve)
    result = await search_knowledge_base.ainvoke({"query": "问题"})
    assert "失败" in result
