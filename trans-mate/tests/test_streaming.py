"""
流式事件服务单元测试：验证 LangChain 事件到 WebSocket 事件协议的转换
"""
import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from app.llm import streaming
from app.llm.streaming import stream_agent_events, build_history_messages


class StubGraph:
    """伪造 agent_router，回放预设的 astream_events 事件"""

    def __init__(self, events):
        self.events = events
        self.received_input = None

    async def astream_events(self, input_data, version=None):
        self.received_input = input_data
        for event in self.events:
            yield event


def chain_start(name):
    return {"event": "on_chain_start", "name": name, "data": {}, "run_id": f"s-{name}"}


def token_event(text):
    return {
        "event": "on_chat_model_stream",
        "name": "ChatOpenAI",
        "data": {"chunk": AIMessageChunk(content=text)},
        "run_id": "m1",
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_streaming_token_flow(monkeypatch):
    stub = StubGraph(
        [
            chain_start("classifier"),
            chain_start("base_agent"),
            token_event("你"),
            token_event("好"),
            {
                "event": "on_chain_end",
                "name": "base_agent",
                "data": {"output": {"messages": [AIMessage(content="你好")]}},
                "run_id": "s-base_agent",
            },
        ]
    )
    monkeypatch.setattr(streaming, "agent_router", stub)

    events = [event async for event in stream_agent_events([HumanMessage(content="hi")])]

    assert [e["type"] for e in events] == ["status", "agent_start", "token", "token", "done"]
    assert events[0]["message"] == "正在分析意图..."
    assert events[1]["agent"] == "base_agent"
    assert events[2]["content"] == "你"
    assert events[-1]["content"] == "你好"
    assert stub.received_input == {"messages": [HumanMessage(content="hi")]}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_streaming_tool_call_pairing(monkeypatch):
    stub = StubGraph(
        [
            chain_start("base_agent"),
            token_event("我先查一下"),
            {
                "event": "on_tool_start",
                "name": "get_weather",
                "run_id": "tool-1",
                "data": {"input": {"city": "北京"}},
            },
            {
                "event": "on_tool_end",
                "name": "get_weather",
                "run_id": "tool-1",
                "data": {"output": "北京晴，25度"},
            },
            token_event("查询完成"),
            {
                "event": "on_chain_end",
                "name": "base_agent",
                "data": {"output": {"messages": [AIMessage(content="最终回复")]}},
                "run_id": "s-base_agent",
            },
        ]
    )
    monkeypatch.setattr(streaming, "agent_router", stub)

    events = [event async for event in stream_agent_events([HumanMessage(content="北京天气")])]

    types = [e["type"] for e in events]
    assert types == ["agent_start", "token", "tool_call", "tool_result", "token", "done"]

    tool_call = events[2]
    assert tool_call["name"] == "get_weather"
    assert tool_call["args"] == {"city": "北京"}

    tool_result = events[3]
    assert tool_result["id"] == "tool-1"
    assert tool_result["result"] == "北京晴，25度"

    # done 事件中的 tool_events 应带上结果
    done = events[-1]
    assert done["content"] == "最终回复"
    assert done["tool_events"][0]["result"] == "北京晴，25度"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_streaming_non_streaming_path_catchup(monkeypatch):
    """RAG 直接命中（无 token 事件）时应补发完整内容"""
    stub = StubGraph(
        [
            chain_start("rag_retrieval"),
            chain_start("rag_agent"),
            {
                "event": "on_chain_end",
                "name": "rag_agent",
                "data": {"output": {"messages": [AIMessage(content="知识库答案")]}},
                "run_id": "s-rag_agent",
            },
        ]
    )
    monkeypatch.setattr(streaming, "agent_router", stub)

    events = [event async for event in stream_agent_events([HumanMessage(content="问题")])]

    types = [e["type"] for e in events]
    assert types == ["status", "agent_start", "token", "done"]
    assert events[2]["content"] == "知识库答案"
    assert events[-1]["content"] == "知识库答案"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_streaming_exception_yields_error(monkeypatch):
    class BrokenGraph:
        async def astream_events(self, input_data, version=None):
            yield token_event("部分")
            raise RuntimeError("LLM 炸了")

    monkeypatch.setattr(streaming, "agent_router", BrokenGraph())

    events = [event async for event in stream_agent_events([HumanMessage(content="hi")])]
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
