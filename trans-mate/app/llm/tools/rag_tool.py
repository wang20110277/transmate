"""
RAG 知识库检索工具：供 deep agent 主智能体调用
超时/异常一律返回降级文案，不向 agent 抛错（agent 可转用 web_search）
"""
import asyncio
import logging

from langchain_core.tools import tool

from app.llm.agents.rag_agent import rag_agent

logger = logging.getLogger(__name__)

RAG_TOOL_TIMEOUT = 15


@tool
async def search_knowledge_base(query: str) -> str:
    """检索本地知识库。当用户的问题可能与已导入的文档资料相关时，先调用本工具查找相关内容。"""
    try:
        success, response = await asyncio.wait_for(
            asyncio.to_thread(rag_agent.retrieve, query),
            timeout=RAG_TOOL_TIMEOUT,
        )
        if success and response:
            return response
        return "知识库中没有找到相关内容。"
    except asyncio.TimeoutError:
        logger.warning(f"RAG 检索超时: {query[:50]}")
        return "知识库检索超时，暂时不可用，请尝试其他方式（如网络搜索）。"
    except Exception as e:
        logger.error(f"RAG 检索异常: {e}")
        return f"知识库检索失败：{e}"
