import logging
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

from app.llm.agents.base_agent import base_agent
from app.llm.agents.stock_agent import stock_data_agent
from app.llm.agents.rag_agent import rag_agent

logger = logging.getLogger(__name__)


class AgentState(dict):
    messages: list
    rag_available: bool
    rag_response: str
    intent: str


def get_user_input(state: AgentState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return ""

    last_message = messages[-1]
    if isinstance(last_message, HumanMessage):
        return last_message.content
    elif isinstance(last_message, dict):
        return last_message.get("content", "")
    else:
        return str(last_message)


def try_rag_retrieval(state: AgentState) -> dict:
    """优先尝试RAG检索，如果能回答则直接返回"""
    user_input = get_user_input(state)
    if not user_input:
        return {"rag_available": False}

    try:
        success, rag_response = rag_agent.retrieve(user_input)
        if success and rag_response:
            logger.info(f"RAG successfully retrieved answer for: {user_input}")
            return {"rag_available": True, "rag_response": rag_response}
    except Exception as e:
        logger.error(f"RAG retrieval error: {e}")

    return {"rag_available": False}


def classify_intent(state: AgentState) -> dict:
    """根据用户输入判断意图：股票相关 or 通用"""
    user_input = get_user_input(state)
    if not user_input:
        return {"intent": "general"}

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


async def call_rag_agent(state: AgentState) -> AgentState:
    """RAG检索成功，直接返回结果"""
    messages = state.get("messages", [])
    rag_response = state.get("rag_response", "")
    logger.info(f"call_rag_agent received state keys: {state.keys()}")
    logger.info(f"call_rag_agent rag_response length: {len(rag_response)}")
    new_messages = messages + [AIMessage(content=rag_response)]
    logger.info(f"RAG response: {rag_response[:100]}...")
    return {"messages": new_messages}


async def call_base_agent(state: AgentState) -> AgentState:
    """调用通用代理"""
    messages = state.get("messages", [])
    user_input = get_user_input(state)

    if not user_input:
        return state

    result = await base_agent.ainvoke({"messages": [HumanMessage(content=user_input)]})
    response_content = result["messages"][-1].content

    new_messages = messages + [AIMessage(content=response_content)]
    return {"messages": new_messages}


async def call_stock_agent(state: AgentState) -> AgentState:
    """调用股票数据代理"""
    messages = state.get("messages", [])
    user_input = get_user_input(state)

    if not user_input:
        return state

    result = await stock_data_agent.ainvoke(
        {"messages": [HumanMessage(content=user_input)]}
    )
    response_content = result["messages"][-1].content

    new_messages = messages + [AIMessage(content=response_content)]
    return {"messages": new_messages}


def create_agent_graph():
    """创建 LangGraph 路由图 - RAG优先策略"""
    workflow = StateGraph(AgentState)

    workflow.add_node("rag_retrieval", try_rag_retrieval)
    workflow.add_node("rag_agent", call_rag_agent)
    workflow.add_node("classifier", classify_intent)
    workflow.add_node("base_agent", call_base_agent)
    workflow.add_node("stock_agent", call_stock_agent)

    workflow.set_entry_point("rag_retrieval")

    workflow.add_conditional_edges(
        "rag_retrieval",
        lambda x: "rag" if x.get("rag_available", False) else "fallback",
        {"rag": "rag_agent", "fallback": "classifier"},
    )

    workflow.add_conditional_edges(
        "classifier",
        lambda x: x.get("intent", "general"),
        {"stock": "stock_agent", "general": "base_agent"},
    )

    workflow.add_edge("rag_agent", END)
    workflow.add_edge("base_agent", END)
    workflow.add_edge("stock_agent", END)

    return workflow.compile()


agent_router = create_agent_graph()
