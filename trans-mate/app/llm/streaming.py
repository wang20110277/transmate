"""
智能体流式服务
将 agent harness 产出的事件流聚合为 WebSocket 事件协议（ZCode 式）
"""
import logging
from typing import AsyncGenerator, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.llm.harness import get_agent_harness

logger = logging.getLogger(__name__)

# 推送给前端的工具结果最大长度
MAX_TOOL_RESULT_LENGTH = 2000


def _truncate(text: str, limit: int = MAX_TOOL_RESULT_LENGTH) -> str:
    if len(text) > limit:
        return text[:limit] + "...(截断)"
    return text


async def stream_agent_events(
    history: List[BaseMessage], thread_id: str
) -> AsyncGenerator[dict, None]:
    """
    驱动 agent harness 执行一轮并聚合事件。

    history: 完整对话消息（含本次用户输入）
    thread_id: 会话 thread 标识（conv-{conversation_id}）
    依次产出事件 dict：
      - harness 归一化事件透传：status / agent_start / token /
        tool_call / tool_result / plan_update / subagent_start / subagent_end
      - {"type": "done", "content", "tool_events"}   完成，content 为累计 token
      - {"type": "error", "message"}        执行异常
    """
    streamed_answer = ""
    tool_events: List[dict] = []

    try:
        async for event in get_agent_harness().astream(history, thread_id):
            kind = event.get("type")

            if kind == "token":
                streamed_answer += event["content"]
            elif kind == "tool_call":
                tool_events.append(dict(event))
            elif kind == "tool_result":
                result = _truncate(str(event.get("result", "")))
                event["result"] = result
                for tool_event in tool_events:
                    if tool_event["id"] == event["id"]:
                        tool_event["result"] = result

            yield event

        yield {
            "type": "done",
            "content": streamed_answer,
            "tool_events": tool_events,
        }
    except Exception as e:
        logger.error(f"智能体流式执行异常: {e}", exc_info=True)
        yield {"type": "error", "message": f"智能体执行失败: {e}"}


def build_history_messages(records) -> List[BaseMessage]:
    """
    将数据库消息记录转换为 LangChain 消息列表（多轮上下文）
    """
    history: List[BaseMessage] = []
    for record in records:
        if record.role == "user":
            history.append(HumanMessage(content=record.content))
        elif record.content:
            history.append(AIMessage(content=record.content))
    return history
