from langchain.agents import create_agent

from app.llm.models import ModelPool
from app.llm.tools import get_weather, web_search

model = ModelPool()

# 系统提示语，定义智能助手的行为
system_prompt = """
你是一个智能助手，你需要根据用户的指令，调用工具函数获取数据，然后给出结果。
你支持的工具包括：
- get_weather: 获取指定城市的天气信息
- web_search: 搜索查询功能
"""

# 创建智能助手代理，集成模型、工具和系统提示
agent = create_agent(
    model=model,
    tools=[get_weather, web_search],
    system_prompt=system_prompt,
    # debug=True,
)