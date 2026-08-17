"""
智能体流式服务
将 LangGraph 智能体路由的执行过程转换为流式事件（ZCode 式）
"""
import logging
from typing import AsyncGenerator, List, Optional

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from app.llm.router import agent_router

logger = logging.getLogger(__name__)

# 会真正执行 LLM/工具的智能体节点
AGENT_NODES = {"base_agent", "stock_agent", "rag_agent"}
# 路由阶段节点的状态提示
NODE_STATUS = {
    "rag_retrieval": "正在检索知识库...",
    "classifier": "正在分析意图...",
}
# 推送给前端的工具结果最大长度
MAX_TOOL_RESULT_LENGTH = 2000


def _truncate(text: str, limit: int = MAX_TOOL_RESULT_LENGTH) -> str:
    if len(text) > limit:
        return text[:limit] + "...(截断)"
    return text


async def stream_agent_events(history: List[BaseMessage]) -> AsyncGenerator[dict, None]:
    """
    以事件流驱动智能体路由图。

    history: 完整对话消息（含本次用户输入）
    依次产出事件 dict：
      - {"type": "status", "message"}       路由阶段提示
      - {"type": "agent_start", "agent"}    智能体节点开始执行
      - {"type": "token", "content"}        LLM 逐 token 输出
      - {"type": "tool_call", "id","name","args"}   工具调用开始
      - {"type": "tool_result", "id","name","result"} 工具返回
      - {"type": "done", "content", "tool_events"}   完成，携带完整回复
      - {"type": "error", "message"}        执行异常
    """
    streamed_answer = ""
    tool_events: List[dict] = []
    final_answer: Optional[str] = None

    try:
        async for event in agent_router.astream_events({"messages": history}, version="v2"):
            kind = event["event"]
            name = event.get("name", "")

            if kind == "on_chain_start":
                if name in AGENT_NODES:
                    yield {"type": "agent_start", "agent": name}
                elif name in NODE_STATUS:
                    yield {"type": "status", "message": NODE_STATUS[name]}
            elif kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                content = getattr(chunk, "content", None)
                if isinstance(content, str) and content:
                    streamed_answer += content
                    yield {"type": "token", "content": content}
            elif kind == "on_tool_start":
                tool_event = {
                    "id": event["run_id"],
                    "name": name,
                    "args": event["data"].get("input"),
                }
                tool_events.append(tool_event)
                yield {"type": "tool_call", **tool_event}
            elif kind == "on_tool_end":
                result = _truncate(str(event["data"].get("output", "")))
                for tool_event in tool_events:
                    if tool_event["id"] == event["run_id"]:
                        tool_event["result"] = result
                yield {
                    "type": "tool_result",
                    "id": event["run_id"],
                    "name": name,
                    "result": result,
                }
            elif kind == "on_chain_end" and name in AGENT_NODES:
                output = event["data"].get("output") or {}
                messages = (
                    output.get("messages", []) if isinstance(output, dict) else []
                )
                if messages:
                    final_answer = messages[-1].content

        # 非流式路径（如 RAG 直接命中）没有任何 token 事件，补发完整内容
        if final_answer and not streamed_answer:
            streamed_answer = final_answer
            yield {"type": "token", "content": streamed_answer}

        yield {
            "type": "done",
            "content": final_answer if final_answer is not None else streamed_answer,
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
