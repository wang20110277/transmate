from crewai import Crew, Task, Process
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

from app.llm.agents.base_agent import base_agent
from app.llm.agents.stock_agent import stock_data_agent


class AgentState(dict):
    messages: list


def classify_intent(state: AgentState) -> dict:
    """根据用户输入判断意图：股票相关 or 通用"""
    messages = state.get("messages", [])
    if not messages:
        return {"intent": "general"}

    last_message = messages[-1]
    if isinstance(last_message, HumanMessage):
        user_input = last_message.content
    elif isinstance(last_message, dict):
        user_input = last_message.get("content", "")
    else:
        user_input = str(last_message)

    user_input_lower = user_input.lower()

    stock_keywords = [
        "股票",
        "上证",
        "深证",
        "创业板",
        "科创板",
        "北交所",
        "股价",
        "行情",
        "涨跌",
        "收盘",
        "开盘",
        "指数",
        "市值",
        "市盈率",
        "市净率",
        "成交量",
        "成交额",
        "基金",
        "ETF",
        "A股",
        "港股",
        "美股",
        "股票代码",
        "股票名称",
        "行业",
        "板块",
        "601",
        "600",
        "000",
        "002",
        "300",
        "688",
        "sh0",
        "sz0",
        "sz3",
        "sz6",
        "tushare",
        "股票信息",
        "日线",
        "实时行情",
    ]

    for keyword in stock_keywords:
        if keyword in user_input_lower:
            return {"intent": "stock"}

    return {"intent": "general"}


async def call_base_agent(state: AgentState) -> AgentState:
    """调用通用代理"""
    messages = state.get("messages", [])
    if not messages:
        return state

    last_message = messages[-1]
    if isinstance(last_message, HumanMessage):
        user_input = last_message.content
    elif isinstance(last_message, dict):
        user_input = last_message.get("content", "")
    else:
        user_input = str(last_message)

    result = await base_agent.ainvoke({"messages": [HumanMessage(content=user_input)]})
    response_content = result["messages"][-1].content

    new_messages = messages + [AIMessage(content=response_content)]
    return {"messages": new_messages}


async def call_stock_agent(state: AgentState) -> AgentState:
    """调用股票数据代理"""
    messages = state.get("messages", [])
    if not messages:
        return state

    last_message = messages[-1]
    if isinstance(last_message, HumanMessage):
        user_input = last_message.content
    elif isinstance(last_message, dict):
        user_input = last_message.get("content", "")
    else:
        user_input = str(last_message)

    result = await stock_data_agent.ainvoke({"messages": [HumanMessage(content=user_input)]})
    response_content = result["messages"][-1].content

    new_messages = messages + [AIMessage(content=response_content)]
    return {"messages": new_messages}


def create_stock_task(user_input: str):
    return Task(
        description=user_input,
        agent=stock_data_agent,
        expected_output="股票相关数据和分析结果",
    )


def create_agent_graph():
    """创建 LangGraph 路由图"""
    workflow = StateGraph(AgentState)

    workflow.add_node("classifier", classify_intent)
    workflow.add_node("base_agent", call_base_agent)
    workflow.add_node("stock_agent", call_stock_agent)

    workflow.set_entry_point("classifier")

    workflow.add_conditional_edges(
        "classifier",
        lambda x: x.get("intent", "general"),
        {"stock": "stock_agent", "general": "base_agent"},
    )

    workflow.add_edge("base_agent", END)
    workflow.add_edge("stock_agent", END)

    return workflow.compile()


agent_router = create_agent_graph()
