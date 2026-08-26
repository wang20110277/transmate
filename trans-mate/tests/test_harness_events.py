"""
DeepAgentHarness 测试：构造注入、thread 上下文决策、基础事件
"""
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.llm.harness import get_agent_harness
from app.llm.harness.base import AgentHarness
from app.llm.harness.deep_agent_harness import DeepAgentHarness


@pytest.mark.unit
def test_get_agent_harness_singleton(monkeypatch):
    """工厂返回 DeepAgentHarness 单例"""
    import app.llm.harness as harness_module
    monkeypatch.setattr(harness_module, "_harness", None)
    try:
        first = get_agent_harness()
        second = get_agent_harness()
        assert first is second
        assert isinstance(first, AgentHarness)
        assert isinstance(first, DeepAgentHarness)
    finally:
        monkeypatch.setattr(harness_module, "_harness", None)


class StubAgent:
    """伪造 deep agent：回放预设 astream_events，记录收到的输入与 config"""

    def __init__(self, raw_events, state_values=None):
        self.raw_events = raw_events
        self.state_values = state_values if state_values is not None else {}
        self.received = None
        self.received_config = None

    async def astream_events(self, input_data, config=None, version=None):
        self.received = input_data
        self.received_config = config
        for event in self.raw_events:
            yield event

    async def aget_state(self, config):
        return SimpleNamespace(values=self.state_values)


def token_event(text, tags=None):
    return {
        "event": "on_chat_model_stream",
        "name": "ChatOpenAI",
        "tags": tags or [],
        "data": {"chunk": AIMessageChunk(content=text)},
        "run_id": "m1",
    }


@pytest.mark.asyncio
@pytest.mark.unit
async def test_full_history_when_thread_empty():
    """thread 无 checkpoint 状态（新会话/存量会话）→ 全量历史注入"""
    history = [
        HumanMessage(content="一"),
        AIMessage(content="答"),
        HumanMessage(content="二"),
    ]
    stub = StubAgent([], state_values={})
    harness = DeepAgentHarness(agent=stub, checkpointer=InMemorySaver())
    _ = [e async for e in harness.astream(history, "conv-1")]
    assert len(stub.received["messages"]) == 3


@pytest.mark.asyncio
@pytest.mark.unit
async def test_only_last_message_when_thread_has_state():
    """thread 已有 checkpoint 状态 → 只注入最后一条（本次 user 输入）"""
    history = [
        HumanMessage(content="一"),
        AIMessage(content="答"),
        HumanMessage(content="二"),
    ]
    stub = StubAgent([], state_values={"messages": [HumanMessage(content="历史")]})
    harness = DeepAgentHarness(agent=stub, checkpointer=InMemorySaver())
    _ = [e async for e in harness.astream(history, "conv-1")]
    assert stub.received["messages"] == [history[-1]]
    assert stub.received_config["configurable"]["thread_id"] == "conv-1"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_no_checkpointer_full_history():
    """未接 checkpointer（纯 stub 模式）→ 全量历史，且不触碰 aget_state"""
    history = [HumanMessage(content="一"), HumanMessage(content="二")]
    stub = StubAgent([], state_values={"messages": [HumanMessage(content="x")]})
    harness = DeepAgentHarness(agent=stub, checkpointer=None)
    _ = [e async for e in harness.astream(history, "conv-1")]
    assert len(stub.received["messages"]) == 2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_agent_start_then_token():
    """首个原始事件前发 agent_start；token 事件正常透传"""
    stub = StubAgent([token_event("你"), token_event("好")])
    harness = DeepAgentHarness(agent=stub, checkpointer=None)
    out = [e async for e in harness.astream([HumanMessage(content="hi")], "conv-1")]
    assert out[0] == {"type": "agent_start", "agent": "deep_agent"}
    assert out[1] == {"type": "token", "content": "你"}
    assert out[2] == {"type": "token", "content": "好"}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_clear_thread_delegates_to_checkpointer():
    class SpySaver(InMemorySaver):
        def __init__(self):
            super().__init__()
            self.deleted = []

        async def adelete_thread(self, thread_id):
            self.deleted.append(thread_id)

    spy = SpySaver()
    harness = DeepAgentHarness(agent=StubAgent([]), checkpointer=spy)
    await harness.initialize()
    await harness.clear_thread("conv-9")
    assert spy.deleted == ["conv-9"]
