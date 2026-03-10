from langchain_core.tools import tool
from tavily import TavilyClient

from app.core.config import TAVILY_API_KEY


@tool
async def web_search(query: str) -> str:
    """搜索网络查询功能"""
    api_key = TAVILY_API_KEY

    if not api_key:
        return "搜索功能未配置 API Key，请联系管理员配置 TAVILY_API_KEY"

    try:
        tavily_client = TavilyClient(api_key=api_key)
        response = tavily_client.search(
            query=query,
            search_depth="basic",
            max_results=5,
        )

        results = response.get("results", [])
        if not results:
            return f"未找到与「{query}」相关的搜索结果"

        formatted_results = []
        for i, result in enumerate(results, 1):
            title = result.get("title", "无标题")
            result_url = result.get("url", "")
            content = result.get("content", "")[:200]
            formatted_results.append(
                f"{i}. {title}\n   {content}...\n   来源: {result_url}"
            )

        return "搜索结果：\n\n" + "\n\n".join(formatted_results)

    except Exception as e:
        return f"搜索失败：{str(e)}"
