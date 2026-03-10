from crewai import Agent
from app.llm.models.kimi_model import create_crewai_llm
from app.llm.tools import (
    get_stock_info,
    get_stock_daily,
    get_stock_realtime,
    get_index_daily,
    get_stock_daily_basic,
    search_stock,
)

model = create_crewai_llm()

stock_data_agent = Agent(
    role="股票产品数据采集专家",
    goal="采集个股/指数/基金的行情、财务指标、估值、行业分类等数据",
    backstory="精通股票数据接口（如 Tushare/同花顺），能处理实时/历史行情数据",
    tools=[
        get_stock_info,
        get_stock_daily,
        get_stock_realtime,
        get_index_daily,
        get_stock_daily_basic,
        search_stock,
    ],
    llm=model,
    verbose=True,
)
