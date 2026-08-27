"""
DeepAgentHarness：基于 deepagents 的 agent harness 实现
组装主智能体（RAG/天气/搜索工具 + 规划 + 虚拟文件系统）与 stock 子智能体，
通过 AsyncSqliteSaver 按 thread 持久化 agent 内部状态
"""
import logging
import os
from collections import OrderedDict
from typing import Any, AsyncGenerator, List, Optional

from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.orm import Session

from app.core.config import (
    CHECKPOINT_DB_PATH,
    DEFAULT_API_KEY,
    DEFAULT_API_URL,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
)
from app.llm.harness.base import AgentHarness
from app.llm.harness.events import (
    EVENT_AGENT_START,
    EVENT_PLAN_UPDATE,
    EVENT_STATUS,
    EVENT_SUBAGENT_END,
    EVENT_SUBAGENT_START,
    EVENT_TOKEN,
    EVENT_TOOL_CALL,
    EVENT_TOOL_RESULT,
)
from app.llm.tools import get_weather, web_search
from app.llm.tools.rag_tool import search_knowledge_base
from app.llm.tools.stock_tool import (
    get_stock_daily,
    get_stock_daily_basic,
    get_stock_info,
    get_index_daily,
    get_stock_realtime,
    search_stock,
)

logger = logging.getLogger(__name__)

AGENT_NAME = "deep_agent"

# 子智能体名称集合（含 deepagents 自动添加的 general-purpose）：
# 这些 agent 的 LLM token 输出不进入主回复流（Task 5 用于 token 过滤）
SUBAGENT_NAMES = {"general-purpose", "stock_data_expert"}

# 主智能体系统提示（迁移自 base_agent 并补充工具使用指引）
MAIN_AGENT_PROMPT = """你是 TransMate 智能助手，帮助用户完成资料检索、天气查询、股票数据采集等任务。

工具使用指引：
- 用户问题可能与已导入文档资料相关时，优先调用 search_knowledge_base 检索本地知识库
- 需要实时网络信息时调用 web_search；天气查询调用 get_weather
- 涉及股票、指数、基金、行情、财务指标、估值等数据时，通过 task 工具派发 stock_data_expert 子智能体采集
- 复杂多步骤任务先用 write_todos 制定计划，并随进展更新计划状态

用户工作区（启用时）：
- 你的文件操作限制在当前用户的工作沙箱内；当前会话的工作目录是 sessions/{会话ID}/，用户其他会话的成果在 sessions/ 的兄弟目录中，可以直接引用
- /skills/ 是已安装技能库（只读，禁止写入）：任务匹配某技能时，先 read_file 读取其 SKILL.md（limit=1000）并按其指引执行

【文件交付流程——必须遵守】
凡用户要求"生成/保存/导出/写成文件"的任务，固定两步，缺一不可：
1. write_file 把内容写入沙箱；
2. 紧接着调用 save_artifact 把该文件上传为云盘制品（source_path 用第 1 步的同一路径）。
只执行第 1 步就回复"已保存"是错误的：用户在云盘制品面板看不到文件，等于没有交付。回复用户时，必须以 save_artifact 的成功结果为准。
"""

# stock 子智能体提示（迁移自 app/llm/agents/stock_agent.py）
STOCK_SUBAGENT_PROMPT = """
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

STOCK_TOOLS = [
    get_stock_info,
    get_stock_daily,
    get_stock_realtime,
    get_index_daily,
    get_stock_daily_basic,
    search_stock,
]

AGENT_CACHE_SIZE = 8  # 每用户 agent 实例 LRU 上限


def _build_backend(user_id: str):
    """用户工作区后端:默认路由=用户沙箱(防越界),/skills/=技能物化缓存"""
    from app.core import config

    from deepagents.backends.composite import CompositeBackend
    from deepagents.backends.filesystem import FilesystemBackend

    sandbox = os.path.join(config.SANDBOX_ROOT, user_id)
    os.makedirs(sandbox, exist_ok=True)
    skill_cache = os.path.join(config.SKILL_CACHE_ROOT, user_id)
    os.makedirs(skill_cache, exist_ok=True)
    return CompositeBackend(
        default=FilesystemBackend(root_dir=sandbox, virtual_mode=True),
        routes={"/skills/": FilesystemBackend(root_dir=skill_cache, virtual_mode=True)},
    )


def _build_model():
    """创建共享 BaseChatModel（Qwen OpenAI 兼容接口，配置与 ModelPool 相同）"""
    return init_chat_model(
        model=DEFAULT_MODEL,
        model_provider=DEFAULT_PROVIDER,
        base_url=DEFAULT_API_URL,
        api_key=DEFAULT_API_KEY,
        temperature=0.1,
    )


def _build_stock_subagent() -> dict:
    """stock 子智能体声明（SubAgent TypedDict 字段名，deepagents 懒导入在 _build_agent 内）"""
    return {
        "name": "stock_data_expert",
        "description": "股票产品数据采集专家：采集个股/指数/基金的行情、财务指标、估值、行业分类等数据（Tushare 数据源）",
        "system_prompt": STOCK_SUBAGENT_PROMPT,
        "tools": STOCK_TOOLS,
    }


def _build_agent(model, checkpointer, user_id: str | None = None):
    """组装 deepagents 主智能体;user_id 非空时启用云工作区(skills+沙箱)"""
    from deepagents import create_deep_agent
    from langchain.agents.middleware import TodoListMiddleware

    kwargs = dict(
        model=model,
        tools=[search_knowledge_base, get_weather, web_search],
        system_prompt=MAIN_AGENT_PROMPT,
        middleware=[TodoListMiddleware()],
        subagents=[_build_stock_subagent()],
        checkpointer=checkpointer,
        name=AGENT_NAME,
    )
    if user_id is not None:
        from app.llm.tools.artifact_tool import make_save_artifact_tool

        kwargs["skills"] = ["/skills/"]
        kwargs["backend"] = _build_backend(user_id)
        kwargs["tools"] = kwargs["tools"] + [make_save_artifact_tool(user_id)]
    return create_deep_agent(**kwargs)


class DeepAgentHarness(AgentHarness):
    """deepagents 实现的 agent harness

    checkpointer/agent/model 均可注入，便于测试替身；生产默认懒初始化。
    """

    def __init__(
        self,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        agent: Any = None,
        model: Any = None,
    ):
        self._checkpointer_param = checkpointer
        self._agent_param = agent
        self._model_param = model
        self._checkpointer: Optional[BaseCheckpointSaver] = None
        self._agent: Any = None
        self._model: Any = None
        self._user_agents: "OrderedDict[str, Any]" = OrderedDict()
        self._saver_cm = None
        self._initialized = False

    def _resolve_agent(self, user_id: Optional[str], db: Session | None):
        """user_id 为空 → 传统单例 agent;否则按用户工厂缓存取"""
        if user_id is None:
            return self._agent
        return self._get_agent_for_user(user_id, db)

    def _get_agent_for_user(self, user_id: str, db: Session | None):
        from app.llm.harness.skill_materializer import sync_user_skills

        # 每轮都校验清单指纹:安装/卸载后已缓存 agent 的 /skills/ 立即生效(spec §3.3)
        # 物化失败在 sync_user_skills 内降级为现状缓存目录,不阻塞对话(spec §5)
        sync_user_skills(db, user_id)

        if user_id in self._user_agents:
            self._user_agents.move_to_end(user_id)
            return self._user_agents[user_id]
        model = self._model or _build_model()
        agent = _build_agent(model, self._checkpointer, user_id=user_id)
        self._user_agents[user_id] = agent
        while len(self._user_agents) > AGENT_CACHE_SIZE:
            self._user_agents.popitem(last=False)
        return agent

    async def initialize(self) -> None:
        """初始化重量级资源（测试注入模式跳过真实组件构造）"""
        if self._initialized:
            return
        if self._agent_param is not None:
            self._agent = self._agent_param
            self._checkpointer = self._checkpointer_param
            self._initialized = True
            return

        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        self._model = self._model_param or _build_model()
        # 全新环境 store/ 目录可能不存在（git-ignored），先确保目录存在
        checkpoint_dir = os.path.dirname(CHECKPOINT_DB_PATH)
        if checkpoint_dir:
            os.makedirs(checkpoint_dir, exist_ok=True)
        self._saver_cm = AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB_PATH)
        self._checkpointer = await self._saver_cm.__aenter__()
        await self._checkpointer.setup()
        self._agent = _build_agent(self._model, self._checkpointer)
        self._initialized = True
        logger.info("DeepAgentHarness 初始化完成（checkpoint=%s）", CHECKPOINT_DB_PATH)

    async def aclose(self) -> None:
        """释放 checkpoint 存储（应用关停时调用）"""
        if self._saver_cm is not None:
            try:
                await self._saver_cm.__aexit__(None, None, None)
            except Exception as exc:
                logger.warning(f"关闭 checkpoint 存储异常: {exc}")
            finally:
                self._saver_cm = None
                self._checkpointer = None
                self._agent = None
                self._user_agents.clear()
                self._initialized = False

    async def clear_thread(self, thread_id: str) -> None:
        """清除会话的 agent 持久化状态（未初始化时静默跳过）"""
        if self._checkpointer is None:
            return
        try:
            await self._checkpointer.adelete_thread(thread_id)
        except Exception as exc:
            logger.warning(f"清除会话 checkpoint 失败 thread={thread_id}: {exc}")

    async def astream(
        self,
        history: List[BaseMessage],
        thread_id: str,
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        """驱动 agent 一轮：产出归一化事件（第一个事件前补 agent_start）

        user_id 非空时启用该用户的云工作区 agent（沙箱+技能库）。
        """
        await self.initialize()
        config = {"configurable": {"thread_id": thread_id}}
        messages = await self._resolve_input_messages(history, config)

        db = None
        try:
            if user_id is not None:
                from app.core.database import SessionLocal

                db = SessionLocal()
            agent = self._resolve_agent(user_id, db)
        finally:
            if db is not None:
                db.close()

        started = False
        state: dict = {}
        async for raw in agent.astream_events({"messages": messages}, config, version="v2"):
            if not started:
                started = True
                yield {"type": EVENT_AGENT_START, "agent": AGENT_NAME}
            for event in self._adapt_event(raw, state):
                yield event

        # 轮末兜底:write_file 过但未 save_artifact 的文件自动上云盘(否则用户云盘看不到)
        pending = state.get("written_files", set()) - state.get("saved_paths", set())
        if user_id is not None and pending:
            from app.llm.tools.artifact_tool import make_save_artifact_tool

            autosave = make_save_artifact_tool(user_id)
            for path in sorted(pending):
                result = autosave.invoke(
                    {"source_path": path},
                    config={"configurable": {"thread_id": thread_id}},
                )
                if result.startswith("已保存"):
                    yield {"type": EVENT_STATUS, "message": f"自动保存制品：{result}"}
                else:
                    logger.info("自动补录跳过 %s: %s", path, result)

    async def _resolve_input_messages(
        self, history: List[BaseMessage], config: dict
    ) -> List[BaseMessage]:
        """checkpoint 有 thread 状态 → 只注入最后一条；否则全量（新会话/存量会话兜底）"""
        if self._checkpointer is None:
            return list(history)
        try:
            snapshot = await self._agent.aget_state(config)
            if snapshot and snapshot.values.get("messages"):
                return [history[-1]]
        except Exception as exc:
            logger.warning(f"读取 checkpoint 状态失败，回退全量历史: {exc}")
        return list(history)

    def _adapt_event(self, raw: dict, state: dict) -> List[dict]:
        """原始 astream_events 事件 → 归一化协议事件（0..n 条）

        state 在一轮 astream 内跨调用共享：记录最近派发的子智能体名，
        供 task 工具结束时回填 subagent_end.name。
        """
        kind = raw.get("event")
        name = raw.get("name", "")
        data = raw.get("data") or {}
        tags = set(raw.get("tags") or [])

        if kind == "on_chat_model_stream":
            if tags & SUBAGENT_NAMES:
                # 子智能体的 token 不进入主回复流
                return []
            chunk = data.get("chunk")
            content = getattr(chunk, "content", None)
            if isinstance(content, str) and content:
                return [{"type": EVENT_TOKEN, "content": content}]
            return []

        if kind == "on_tool_start":
            tool_input = data.get("input")
            out = [{"type": EVENT_STATUS, "message": f"正在调用工具 {name}..."}]

            # 轮末自动补录的差集依据:记录本轮写过/已交付的文件(小模型常漏调 save_artifact)
            if name == "write_file":
                # deepagents write_file 的参数名为 file_path
                written = str((tool_input or {}).get("file_path", ""))
                if written:
                    state.setdefault("written_files", set()).add(written)
            elif name == "save_artifact":
                saved = str((tool_input or {}).get("source_path", ""))
                if saved:
                    state.setdefault("saved_paths", set()).add(saved)

            if name == "write_todos":
                todos = (tool_input or {}).get("todos", [])
                out.append(
                    {
                        "type": EVENT_PLAN_UPDATE,
                        "todos": [self._norm_todo(t) for t in todos],
                    }
                )
            elif name == "task":
                args = tool_input or {}
                sub_name = str(args.get("subagent_type", ""))
                task_desc = str(args.get("description", ""))
                state["last_subagent_name"] = sub_name
                out.append(
                    {
                        "type": EVENT_SUBAGENT_START,
                        "name": sub_name,
                        "description": task_desc,
                        "task": task_desc,
                    }
                )

            out.append(
                {
                    "type": EVENT_TOOL_CALL,
                    "id": raw.get("run_id"),
                    "name": name,
                    "args": tool_input,
                }
            )
            return out

        if kind == "on_tool_end":
            result = str(data.get("output", ""))
            out = []
            if name == "task":
                out.append(
                    {
                        "type": EVENT_SUBAGENT_END,
                        "name": state.get("last_subagent_name", ""),
                        "result": result,
                    }
                )
            out.append(
                {
                    "type": EVENT_TOOL_RESULT,
                    "id": raw.get("run_id"),
                    "name": name,
                    "result": result,
                }
            )
            return out

        return []

    @staticmethod
    def _norm_todo(todo: Any) -> dict:
        """归一化 write_todos 的计划项"""
        if isinstance(todo, dict):
            return {
                "content": str(todo.get("content", "")),
                "status": str(todo.get("status", "pending")),
            }
        return {"content": str(todo), "status": "pending"}
