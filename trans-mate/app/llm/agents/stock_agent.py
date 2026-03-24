from langchain.agents import create_agent
from app.llm.models.qwen_model import ModelPool
from app.llm.tools import get_stock_info,get_stock_daily,get_stock_realtime,get_index_daily,get_stock_daily_basic,search_stock

model = ModelPool()

# 系统提示语，定义智能助手的行为
system_prompt = """
你是一个股票产品数据采集专家，你需要根据用户的指令，采集个股/指数/基金的行情、财务指标、估值、行业分类等数据。
精通股票数据接口（如 Tushare/同花顺），能处理实时/历史行情数据。
你支持的工具包括：
- get_stock_info: 获取股票基本信息
- get_stock_daily: 获取股票日线数据
- get_stock_realtime: 获取股票实时行情数据
- get_index_daily: 获取指数日线数据
- get_stock_daily_basic: 获取股票每日基本面指标
- search_stock: 搜索股票
"""

stock_data_agent = create_agent(
    model=model,
    tools=[
        get_stock_info,
        get_stock_daily,
        get_stock_realtime,
        get_index_daily,
        get_stock_daily_basic,
        search_stock,
    ],
    system_prompt=system_prompt
)
