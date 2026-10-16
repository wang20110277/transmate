"""
harness 归一化事件协议
上层（streaming/WebSocket）与前端依赖这些事件类型名，不可随意改动

事件结构（todos / args / result 等字段）由前端 src/types/index.ts 的
AgentEvent 联合类型定义，两端保持一致。
"""


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
