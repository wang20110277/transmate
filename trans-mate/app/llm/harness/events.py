"""
harness 归一化事件协议
上层（streaming/WebSocket）与前端依赖这些事件类型名，不可随意改动
"""
from typing import List, TypedDict


EVENT_STATUS = "status"
EVENT_AGENT_START = "agent_start"
EVENT_TOKEN = "token"
EVENT_TOOL_CALL = "tool_call"
EVENT_TOOL_RESULT = "tool_result"
EVENT_PLAN_UPDATE = "plan_update"
EVENT_SUBAGENT_START = "subagent_start"
EVENT_SUBAGENT_END = "subagent_end"
EVENT_DONE = "done"
EVENT_ERROR = "error"


class TodoItem(TypedDict):
    """计划项：status ∈ pending / in_progress / completed"""

    content: str
    status: str


class PlanUpdateEvent(TypedDict):
    type: str
    todos: List[TodoItem]
