"""
harness 包骨架测试：抽象接口、事件常量与工厂单例
"""
import pytest

from app.llm.harness.base import AgentHarness
from app.llm.harness import events


@pytest.mark.unit
def test_agent_harness_abc_cannot_instantiate():
    with pytest.raises(TypeError):
        AgentHarness()


@pytest.mark.unit
def test_event_constants():
    assert events.EVENT_STATUS == "status"
    assert events.EVENT_AGENT_START == "agent_start"
    assert events.EVENT_TOKEN == "token"
    assert events.EVENT_TOOL_CALL == "tool_call"
    assert events.EVENT_TOOL_RESULT == "tool_result"
    assert events.EVENT_PLAN_UPDATE == "plan_update"
    assert events.EVENT_SUBAGENT_START == "subagent_start"
    assert events.EVENT_SUBAGENT_END == "subagent_end"
    assert events.EVENT_DONE == "done"
    assert events.EVENT_ERROR == "error"
    todo: events.TodoItem = {"content": "查天气", "status": "pending"}
    assert todo["status"] == "pending"
