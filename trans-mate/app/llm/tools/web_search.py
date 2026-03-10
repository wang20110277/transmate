import os

import httpx
from langchain_core.tools import tool


@tool
async def web_search(query: str) -> str:
    """使用 Tavily API 搜索网络"""
    tavily_api_key = os.getenv("TAVILY_API_KEY", "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")
    
    url = "https://api.tavily.com/search"
    headers = {"Content-Type": "application/json"}
    payload = {
        "api_key": tavily_api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": 5
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        results = data.get("results", [])
        if not results:
            return f"未找到与「{query}」相关的搜索结果"
        
        formatted_results = []
        for i, result in enumerate(results, 1):
            title = result.get("title", "无标题")
            result_url = result.get("url", "")
            content = result.get("content", "")[:200]
            formatted_results.append(f"{i}. {title}\n   {content}...\n   来源: {result_url}")
        
        return "搜索结果：\n\n" + "\n\n".join(formatted_results)
        
    except httpx.TimeoutException:
        return f"搜索「{query}」超时，请稍后重试"
    except httpx.HTTPStatusError as e:
        return f"搜索失败：HTTP错误 {e.response.status_code}"
    except Exception as e:
        return f"搜索失败：{str(e)}"
