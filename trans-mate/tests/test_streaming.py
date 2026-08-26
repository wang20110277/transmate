"""
流式事件服务单元测试：harness 事件到 WebSocket 事件协议的聚合
"""
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.llm import streaming
from app.llm.streaming import stream_agent_events, build_history_messages


class StubHarness:
    """伪造 harness：回放预设事件，记录收到的 history 与 thread_id"""

    def __init__(self, events):
        self.events = events
        self.received = None

    async def astream(self, history, thread_id, user_id=None):
        self.received = (list(history), thread_id)
        for event in self.events:
            yield event


def stub_factory(harness):
    return lambda: harness


@pytest.mark.asyncio
@pytest.mark.unit
async def test_streaming_token_flow(monkeypatch):
    stub = StubHarness(
        [
            {"type": "agent_start", "agent": "deep_agent"},
            {"type": "token", "content": "你"},
            {"type": "token", "content": "好"},
        ]
    )
    monkeypatch.setattr(streaming, "get_agent_harness", stub_factory(stub))

    history = [HumanMessage(content="hi")]
    events = [e async for e in stream_agent_events(history, "conv-1")]

    assert [e["type"] for e in events] == ["agent_start", "token", "token", "done"]
    assert events[-1]["content"] == "你好"
    assert stub.received == ([HumanMessage(content="hi")], "conv-1")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_streaming_tool_call_pairing(monkeypatch):
    stub = StubHarness(
        [
            {"type": "agent_start", "agent": "deep_agent"},
            {"type": "token", "content": "我先查一下"},
            {"type": "tool_call", "id": "t1", "name": "get_weather", "args": {"city": "北京"}},
            {"type": "tool_result", "id": "t1", "name": "get_weather", "result": "北京晴，25度"},
            {"type": "token", "content": "查询完成"},
        ]
    )
    monkeypatch.setattr(streaming, "get_agent_harness", stub_factory(stub))

    events = [e async for e in stream_agent_events([HumanMessage(content="北京天气")], "conv-1")]

    types = [e["type"] for e in events]
    assert types == ["agent_start", "token", "tool_call", "tool_result", "token", "done"]

    done = events[-1]
    assert done["content"] == "我先查一下查询完成"
    assert done["tool_events"][0]["result"] == "北京晴，25度"
    # tool_result 事件本身也要透传给前端
    assert events[3]["result"] == "北京晴，25度"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_streaming_tool_result_truncated(monkeypatch):
    stub = StubHarness(
        [
            {"type": "tool_call", "id": "t1", "name": "web_search", "args": {"q": "x"}},
            {"type": "tool_result", "id": "t1", "name": "web_search", "result": "长" * 3000},
        ]
    )
    monkeypatch.setattr(streaming, "get_agent_harness", stub_factory(stub))

    events = [e async for e in stream_agent_events([HumanMessage(content="q")], "conv-1")]
    result = events[1]["result"]
    assert len(result) == streaming.MAX_TOOL_RESULT_LENGTH + len("...(截断)")
    assert result.endswith("...(截断)")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_streaming_subagent_end_result_truncated(monkeypatch):
    stub = StubHarness(
        [
            {"type": "subagent_start", "name": "stock_data_expert", "task": "查行情"},
            {"type": "subagent_end", "name": "stock_data_expert", "result": "长" * 3000},
        ]
    )
    monkeypatch.setattr(streaming, "get_agent_harness", stub_factory(stub))

    events = [e async for e in stream_agent_events([HumanMessage(content="q")], "conv-1")]
    result = events[1]["result"]
    assert len(result) == streaming.MAX_TOOL_RESULT_LENGTH + len("...(截断)")
    assert result.endswith("...(截断)")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_streaming_exception_yields_error(monkeypatch):
    class BrokenHarness:
        async def astream(self, history, thread_id, user_id=None):
            yield {"type": "token", "content": "部分"}
            raise RuntimeError("LLM 炸了")

    monkeypatch.setattr(streaming, "get_agent_harness", stub_factory(BrokenHarness()))

    events = [e async for e in stream_agent_events([HumanMessage(content="hi")], "conv-1")]
    assert events[-1]["type"] == "error"
    assert "LLM 炸了" in events[-1]["message"]


@pytest.mark.unit
def test_build_history_messages():
    class Record:
        def __init__(self, role, content):
            self.role = role
            self.content = content

    history = build_history_messages(
        [Record("user", "第一问"), Record("assistant", "第一答"), Record("user", "第二问")]
    )
    assert len(history) == 3
    assert isinstance(history[0], HumanMessage)
    assert isinstance(history[1], AIMessage)
    assert history[-1].content == "第二问"
