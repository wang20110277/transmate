# Deepagents Agent Harness 集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 deepagents 替换 trans-mate 后端的 LangGraph router，成为带规划/子 agent/checkpoint 持久化的主 agent harness，并扩展前端展示规划面板与子 agent 状态。

**Architecture:** 新增 `app/llm/harness/` 抽象层（`AgentHarness` 接口 + `DeepAgentHarness` 实现），`streaming.py` 改为驱动 harness 并聚合 WebSocket 事件协议（新增 `plan_update` / `subagent_start` / `subagent_end`），`AsyncSqliteSaver` 按 `conv-{conversation_id}` 做 thread 持久化，前端 Vue 组件渲染 todo 面板与子 agent 徽标。

**Tech Stack:** Python / FastAPI / LangChain 1.2.0 / LangGraph 1.0.2 / deepagents 0.7.8 / langgraph-checkpoint-sqlite 3.0.3；前端 Vue 3 + TypeScript + Electron。

**Spec:** `docs/superpowers/specs/2026-08-26-deepagent-harness-design.md`（含 2026-08-26 勘误：ModelPool 不兼容 deepagents `resolve_model`，harness 用 `init_chat_model` 创建 BaseChatModel）

## Global Constraints

- 依赖版本：`deepagents==0.7.8` 新增；`langchain==1.2.0`、`langgraph==1.0.2`、`langgraph-checkpoint-sqlite==3.0.3` 保持（Task 1 验证安装后版本未被破坏，若 pip 强制升级则同步更新 `trans-mate/requirements.txt` 并全量跑测试）
- 事件协议（前后端契约，不可改名）：`status` / `agent_start` / `token` / `tool_call` / `tool_result` / `plan_update` / `subagent_start` / `subagent_end` / `done` / `stopped` / `error` / `conversation_created`
- thread_id 格式：`conv-{conversation_id}`（conversation_id 为整数主键）
- checkpointer 库文件：`trans-mate/store/agent_checkpoints.sqlite`（`store/` 已被 git 忽略），路径可用环境变量 `CHECKPOINT_DB_PATH` 覆盖
- 后端代码注释、日志、文档全部中文（匹配现有代码风格）；提交信息中文
- 后端测试命令在 `/Users/lindaw/Documents/transmate/trans-mate` 目录执行：`python -m pytest tests/<file> -v`（若项目有 venv 先激活，如 `source .venv/bin/activate`）
- 前端命令在 `/Users/lindaw/Documents/transmate/trans-mate-web-ui` 执行：`npm run type-check`
- pytest 标记沿用现有约定：`@pytest.mark.unit` / `@pytest.mark.integration`；异步测试用 `@pytest.mark.asyncio`
- 不删除 `app/llm/router.py`、`app/llm/agents/base_agent.py`、`app/llm/agents/stock_agent.py`（停用不删，保留回滚便利）
- deepagents 的 `create_deep_agent` 的 `model` 参数只接受 `BaseChatModel` 或 str —— 严禁传 `ModelPool` 实例

---

### Task 1: 安装 deepagents 并验证 API 兼容性

**Files:**
- Modify: `trans-mate/requirements.txt`

**Interfaces:**
- Consumes: 无
- Produces: 已安装的 `deepagents==0.7.8` 环境；后续任务依赖的导入路径确认结果（`from deepagents import SubAgent, create_deep_agent`、`from langchain.agents.middleware import TodoListMiddleware`、SubAgent 字段名 `system_prompt`）

- [ ] **Step 1: 安装依赖**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate
# 若项目使用虚拟环境先激活（按实际情况）
pip install deepagents==0.7.8
```

- [ ] **Step 2: 验证版本与导入路径**

```bash
python -c "import deepagents, langchain, langgraph; print('deepagents', deepagents.__version__, '| langchain', langchain.__version__, '| langgraph', langgraph.__version__)"
python -c "from deepagents import create_deep_agent, SubAgent; print('deepagents top-level OK')"
python -c "from langchain.agents.middleware import TodoListMiddleware; print('TodoListMiddleware OK')"
python -c "from deepagents.middleware.subagents import SubAgent; print(SubAgent.__annotations__)"
python -c "from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver; from langgraph.checkpoint.memory import InMemorySaver; from langgraph.checkpoint.base import BaseCheckpointSaver; print('savers OK')"
```

Expected: 全部 OK；`SubAgent.__annotations__` 含 `system_prompt`（若无而有 `prompt`，后续任务中 STOCK_SUBAGENT 的 `system_prompt` 键改为 `prompt`）；langchain/langgraph 版本仍为 1.2.0 / 1.0.2。

- [ ] **Step 3: 验证未破坏现有依赖**

```bash
pip check
python -m pytest tests/ -v
```

Expected: `pip check` 无冲突；现有测试全部通过（与改动前一致）。若 pip 升级了 langchain/langgraph，更新 `requirements.txt` 中对应 pin 为实际安装版本，并确认测试通过。

- [ ] **Step 4: 写入 requirements.txt**

在 `trans-mate/requirements.txt` 的 `#langchain` 段（`langgraph-checkpoint-sqlite==3.0.3` 之后）新增一行：

```
deepagents==0.7.8
```

- [ ] **Step 5: Commit**

```bash
cd /Users/lindaw/Documents/transmate
git add trans-mate/requirements.txt
git commit -m "chore: 引入 deepagents 0.7.8 依赖"
```

---

### Task 2: harness 包骨架（events.py + base.py + 懒加载工厂）

**Files:**
- Create: `trans-mate/app/llm/harness/__init__.py`
- Create: `trans-mate/app/llm/harness/base.py`
- Create: `trans-mate/app/llm/harness/events.py`
- Test: `trans-mate/tests/test_harness_base.py`

**Interfaces:**
- Consumes: 无（deepagents 懒加载，本任务不 import deepagents）
- Produces:
  - `app.llm.harness.get_agent_harness() -> AgentHarness`（模块级单例工厂，懒加载 DeepAgentHarness）
  - `class AgentHarness(ABC)`：抽象方法 `astream(history: list[BaseMessage], thread_id: str) -> AsyncGenerator[dict, None]` 与 `async clear_thread(thread_id: str) -> None`；具体方法 `async initialize() -> None`、`async aclose() -> None`（默认空实现）
  - `app.llm.harness.events`：常量 `EVENT_STATUS/EVENT_AGENT_START/EVENT_TOKEN/EVENT_TOOL_CALL/EVENT_TOOL_RESULT/EVENT_PLAN_UPDATE/EVENT_SUBAGENT_START/EVENT_SUBAGENT_END/EVENT_DONE/EVENT_ERROR`（值为同名小写字符串）与 `TodoItem` TypedDict（`content: str`、`status: str`）

- [ ] **Step 1: Write the failing test**

创建 `trans-mate/tests/test_harness_base.py`：

```python
"""
harness 包骨架测试：抽象接口、事件常量与工厂单例
"""
import pytest

from app.llm.harness import get_agent_harness
from app.llm.harness.base import AgentHarness
from app.llm.harness import events


@pytest.mark.unit
def test_agent_harness_abc_cannot_instantiate():
    with pytest.raises(TypeError):
        AgentHarness()


@pytest.mark.unit
def test_event_constants():
    assert events.EVENT_STATUS == "status"
    assert events.EVENT_AGENT_START == "agent_start"
    assert events.EVENT_TOKEN == "token"
    assert events.EVENT_TOOL_CALL == "tool_call"
    assert events.EVENT_TOOL_RESULT == "tool_result"
    assert events.EVENT_PLAN_UPDATE == "plan_update"
    assert events.EVENT_SUBAGENT_START == "subagent_start"
    assert events.EVENT_SUBAGENT_END == "subagent_end"
    assert events.EVENT_DONE == "done"
    assert events.EVENT_ERROR == "error"
    todo: events.TodoItem = {"content": "查天气", "status": "pending"}
    assert todo["status"] == "pending"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate && python -m pytest tests/test_harness_base.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'app.llm.harness'`

- [ ] **Step 3: Write minimal implementation**

创建 `trans-mate/app/llm/harness/events.py`：

```python
"""
harness 归一化事件协议
上层（streaming/WebSocket）与前端依赖这些事件类型名，不可随意改动
"""
from typing import List, TypedDict


EVENT_STATUS = "status"
EVENT_AGENT_START = "agent_start"
EVENT_TOKEN = "token"
EVENT_TOOL_CALL = "tool_call"
EVENT_TOOL_RESULT = "tool_result"
EVENT_PLAN_UPDATE = "plan_update"
EVENT_SUBAGENT_START = "subagent_start"
EVENT_SUBAGENT_END = "subagent_end"
EVENT_DONE = "done"
EVENT_ERROR = "error"


class TodoItem(TypedDict):
    """计划项：status ∈ pending / in_progress / completed"""

    content: str
    status: str


class PlanUpdateEvent(TypedDict):
    type: str
    todos: List[TodoItem]
```

创建 `trans-mate/app/llm/harness/base.py`：

```python
"""
AgentHarness 抽象基类
上层（streaming/WebSocket）只依赖此接口，未来可替换 harness 实现
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, List

from langchain_core.messages import BaseMessage


class AgentHarness(ABC):
    """agent harness 抽象接口"""

    @abstractmethod
    def astream(
        self, history: List[BaseMessage], thread_id: str
    ) -> AsyncGenerator[dict, None]:
        """驱动 agent 执行一轮，产出归一化事件（见 events.py）。

        history 为 DB 拼出的完整消息列表（含本次 user 输入）；
        是否全量注入由实现根据 checkpoint 状态决定。
        实现为 async 生成器函数（async def + yield）。
        """
        raise NotImplementedError

    @abstractmethod
    async def clear_thread(self, thread_id: str) -> None:
        """清除某个会话的持久化状态（会话删除时调用）"""
        raise NotImplementedError

    async def initialize(self) -> None:
        """初始化重量级资源（模型/checkpoint 存储），默认无操作"""

    async def aclose(self) -> None:
        """释放资源（应用关停时调用），默认无操作"""
```

创建 `trans-mate/app/llm/harness/__init__.py`：

```python
"""
agent harness 包：对外暴露统一工厂
"""
from app.llm.harness.base import AgentHarness

_harness = None


def get_agent_harness() -> AgentHarness:
    """返回 harness 单例（懒加载 DeepAgentHarness，避免模块导入期拉起重量级依赖）"""
    global _harness
    if _harness is None:
        from app.llm.harness.deep_agent_harness import DeepAgentHarness

        _harness = DeepAgentHarness()
    return _harness
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate && python -m pytest tests/test_harness_base.py -v
```

Expected: 2 passed（工厂单例测试在 Task 4 补 —— 此时 `deep_agent_harness.py` 尚不存在，工厂懒导入不会触发）

- [ ] **Step 5: Commit**

```bash
cd /Users/lindaw/Documents/transmate
git add trans-mate/app/llm/harness/ trans-mate/tests/test_harness_base.py
git commit -m "feat: agent harness 抽象层骨架（事件协议/抽象接口/懒加载工厂）"
```

---

### Task 3: RAG 检索工具 search_knowledge_base

**Files:**
- Create: `trans-mate/app/llm/tools/rag_tool.py`
- Test: `trans-mate/tests/test_rag_tool.py`

**Interfaces:**
- Consumes: `app.llm.agents.rag_agent.rag_agent`（模块级 RAGAgent 单例，`retrieve(query: str) -> Tuple[bool, str]`）
- Produces: `search_knowledge_base`（langchain `@tool`，async，签名 `search_knowledge_base(query: str) -> str`）；模块常量 `RAG_TOOL_TIMEOUT = 15`（monkeypatch 用）

- [ ] **Step 1: Write the failing test**

创建 `trans-mate/tests/test_rag_tool.py`：

```python
"""
search_knowledge_base 工具测试：正常检索 / 未命中 / 超时降级 / 异常降级
"""
import time

import pytest

from app.llm.tools import rag_tool
from app.llm.tools.rag_tool import search_knowledge_base


@pytest.mark.asyncio
@pytest.mark.unit
async def test_rag_tool_success(monkeypatch):
    monkeypatch.setattr(rag_tool.rag_agent, "retrieve", lambda q: (True, "知识库答案"))
    result = await search_knowledge_base.ainvoke({"query": "问题"})
    assert result == "知识库答案"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_rag_tool_no_hit(monkeypatch):
    monkeypatch.setattr(rag_tool.rag_agent, "retrieve", lambda q: (False, ""))
    result = await search_knowledge_base.ainvoke({"query": "问题"})
    assert "没有找到" in result


@pytest.mark.asyncio
@pytest.mark.unit
async def test_rag_tool_timeout(monkeypatch):
    def slow_retrieve(query):
        time.sleep(1)
        return True, "不该到达"

    monkeypatch.setattr(rag_tool, "RAG_TOOL_TIMEOUT", 0.05)
    monkeypatch.setattr(rag_tool.rag_agent, "retrieve", slow_retrieve)
    result = await search_knowledge_base.ainvoke({"query": "问题"})
    assert "超时" in result


@pytest.mark.asyncio
@pytest.mark.unit
async def test_rag_tool_error(monkeypatch):
    def broken_retrieve(query):
        raise RuntimeError("chroma 挂了")

    monkeypatch.setattr(rag_tool.rag_agent, "retrieve", broken_retrieve)
    result = await search_knowledge_base.ainvoke({"query": "问题"})
    assert "失败" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate && python -m pytest tests/test_rag_tool.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'app.llm.tools.rag_tool'`

- [ ] **Step 3: Write minimal implementation**

创建 `trans-mate/app/llm/tools/rag_tool.py`：

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate && python -m pytest tests/test_rag_tool.py -v
```

Expected: 4 passed（timeout 用例约 1 秒内完成，后台线程残留 sleep 无碍）

- [ ] **Step 5: Commit**

```bash
cd /Users/lindaw/Documents/transmate
git add trans-mate/app/llm/tools/rag_tool.py trans-mate/tests/test_rag_tool.py
git commit -m "feat: RAG 检索工具 search_knowledge_base（超时/异常降级）"
```

---

### Task 4: DeepAgentHarness 构造与 thread 上下文决策

**Files:**
- Create: `trans-mate/app/llm/harness/deep_agent_harness.py`（若 Task 2 留了占位类则整体替换）
- Test: `trans-mate/tests/test_harness_events.py`

**Interfaces:**
- Consumes: `AgentHarness`（Task 2）、`events` 常量（Task 2）、`search_knowledge_base`（Task 3）、`app.llm.tools` 的 `get_weather/web_search` 与 stock 6 工具、config 的 `DEFAULT_MODEL/DEFAULT_PROVIDER/DEFAULT_API_URL/DEFAULT_API_KEY/CHECKPOINT_DB_PATH`（CHECKPOINT_DB_PATH 在 Task 7 加，本任务先在 config.py 一并加上，见 Step 3 开头）
- Produces:
  - `class DeepAgentHarness(AgentHarness)`，构造签名 `DeepAgentHarness(checkpointer=None, agent=None, model=None)`（agent/model 供测试注入；生产默认全 None → 懒初始化真实组件）
  - `async initialize() / aclose() / clear_thread(thread_id)`；`astream(history, thread_id)` 本任务先实现基础事件（agent_start/token/tool_call/tool_result/status），plan_update/subagent 在 Task 5 追加
  - 模块常量 `AGENT_NAME = "deep_agent"`、`SUBAGENT_NAMES = {"general-purpose", "stock_data_expert"}`、`STOCK_SUBAGENT_PROMPT`、`MAIN_AGENT_PROMPT`、`_build_model()`

- [ ] **Step 1: 在 config.py 增加 checkpoint 路径配置**

在 `trans-mate/app/core/config.py` 文件末尾（`TTS_PROMPT_WAV` 之后）追加：

```python
# Deep Agent Harness（langgraph checkpoint 持久化）
CHECKPOINT_DB_PATH = os.getenv(
    "CHECKPOINT_DB_PATH",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "store",
        "agent_checkpoints.sqlite",
    ),
)
```

- [ ] **Step 2: Write the failing test**

创建 `trans-mate/tests/test_harness_events.py`：

```python
"""
DeepAgentHarness 测试：构造注入、thread 上下文决策、基础事件
"""
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.llm.harness import get_agent_harness
from app.llm.harness.base import AgentHarness
from app.llm.harness.deep_agent_harness import DeepAgentHarness


@pytest.mark.unit
def test_get_agent_harness_singleton(monkeypatch):
    """工厂返回 DeepAgentHarness 单例"""
    import app.llm.harness as harness_module
    monkeypatch.setattr(harness_module, "_harness", None)
    try:
        first = get_agent_harness()
        second = get_agent_harness()
        assert first is second
        assert isinstance(first, AgentHarness)
        assert isinstance(first, DeepAgentHarness)
    finally:
        monkeypatch.setattr(harness_module, "_harness", None)


class StubAgent:
    """伪造 deep agent：回放预设 astream_events，记录收到的输入与 config"""

    def __init__(self, raw_events, state_values=None):
        self.raw_events = raw_events
        self.state_values = state_values if state_values is not None else {}
        self.received = None
        self.received_config = None

    async def astream_events(self, input_data, config=None, version=None):
        self.received = input_data
        self.received_config = config
        for event in self.raw_events:
            yield event

    async def aget_state(self, config):
        return SimpleNamespace(values=self.state_values)


def token_event(text, tags=None):
    return {
        "event": "on_chat_model_stream",
        "name": "ChatOpenAI",
        "tags": tags or [],
        "data": {"chunk": AIMessageChunk(content=text)},
        "run_id": "m1",
    }


@pytest.mark.asyncio
@pytest.mark.unit
async def test_full_history_when_thread_empty():
    """thread 无 checkpoint 状态（新会话/存量会话）→ 全量历史注入"""
    history = [
        HumanMessage(content="一"),
        AIMessage(content="答"),
        HumanMessage(content="二"),
    ]
    stub = StubAgent([], state_values={})
    harness = DeepAgentHarness(agent=stub, checkpointer=InMemorySaver())
    _ = [e async for e in harness.astream(history, "conv-1")]
    assert len(stub.received["messages"]) == 3


@pytest.mark.asyncio
@pytest.mark.unit
async def test_only_last_message_when_thread_has_state():
    """thread 已有 checkpoint 状态 → 只注入最后一条（本次 user 输入）"""
    history = [
        HumanMessage(content="一"),
        AIMessage(content="答"),
        HumanMessage(content="二"),
    ]
    stub = StubAgent([], state_values={"messages": [HumanMessage(content="历史")]})
    harness = DeepAgentHarness(agent=stub, checkpointer=InMemorySaver())
    _ = [e async for e in harness.astream(history, "conv-1")]
    assert stub.received["messages"] == [history[-1]]
    assert stub.received_config["configurable"]["thread_id"] == "conv-1"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_no_checkpointer_full_history():
    """未接 checkpointer（纯 stub 模式）→ 全量历史，且不触碰 aget_state"""
    history = [HumanMessage(content="一"), HumanMessage(content="二")]
    stub = StubAgent([], state_values={"messages": [HumanMessage(content="x")]})
    harness = DeepAgentHarness(agent=stub, checkpointer=None)
    _ = [e async for e in harness.astream(history, "conv-1")]
    assert len(stub.received["messages"]) == 2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_agent_start_then_token():
    """首个原始事件前发 agent_start；token 事件正常透传"""
    stub = StubAgent([token_event("你"), token_event("好")])
    harness = DeepAgentHarness(agent=stub, checkpointer=None)
    out = [e async for e in harness.astream([HumanMessage(content="hi")], "conv-1")]
    assert out[0] == {"type": "agent_start", "agent": "deep_agent"}
    assert out[1] == {"type": "token", "content": "你"}
    assert out[2] == {"type": "token", "content": "好"}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_clear_thread_delegates_to_checkpointer():
    class SpySaver(InMemorySaver):
        def __init__(self):
            super().__init__()
            self.deleted = []

        async def adelete_thread(self, thread_id):
            self.deleted.append(thread_id)

    spy = SpySaver()
    harness = DeepAgentHarness(agent=StubAgent([]), checkpointer=spy)
    await harness.initialize()
    await harness.clear_thread("conv-9")
    assert spy.deleted == ["conv-9"]
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate && python -m pytest tests/test_harness_events.py -v
```

Expected: FAIL，`ImportError: cannot import name 'DeepAgentHarness'`（或占位类缺方法）

- [ ] **Step 4: Write minimal implementation**

创建 `trans-mate/app/llm/harness/deep_agent_harness.py`：

```python
"""
DeepAgentHarness：基于 deepagents 的 agent harness 实现
组装主智能体（RAG/天气/搜索工具 + 规划 + 虚拟文件系统）与 stock 子智能体，
通过 AsyncSqliteSaver 按 thread 持久化 agent 内部状态
"""
import logging
from typing import Any, AsyncGenerator, List, Optional

from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.base import BaseCheckpointSaver

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
    EVENT_STATUS,
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


def _build_agent(model, checkpointer):
    """组装 deepagents 主智能体（deepagents 懒导入，避免模块导入期拉起依赖）"""
    from deepagents import create_deep_agent
    from langchain.agents.middleware import TodoListMiddleware

    return create_deep_agent(
        model=model,
        tools=[search_knowledge_base, get_weather, web_search],
        system_prompt=MAIN_AGENT_PROMPT,
        middleware=[TodoListMiddleware()],
        subagents=[_build_stock_subagent()],
        checkpointer=checkpointer,
        name=AGENT_NAME,
    )


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
        self._saver_cm = None
        self._initialized = False

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
        self, history: List[BaseMessage], thread_id: str
    ) -> AsyncGenerator[dict, None]:
        """驱动 agent 一轮：产出归一化事件（第一个事件前补 agent_start）"""
        await self.initialize()
        config = {"configurable": {"thread_id": thread_id}}
        messages = await self._resolve_input_messages(history, config)

        started = False
        async for raw in self._agent.astream_events(
            {"messages": messages}, config, version="v2"
        ):
            if not started:
                started = True
                yield {"type": EVENT_AGENT_START, "agent": AGENT_NAME}
            for event in self._adapt_event(raw, {}):
                yield event

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
        """原始 astream_events 事件 → 归一化协议事件（0..n 条）"""
        kind = raw.get("event")
        name = raw.get("name", "")
        data = raw.get("data") or {}

        if kind == "on_chat_model_stream":
            chunk = data.get("chunk")
            content = getattr(chunk, "content", None)
            if isinstance(content, str) and content:
                return [{"type": EVENT_TOKEN, "content": content}]
            return []

        if kind == "on_tool_start":
            tool_input = data.get("input")
            out = [
                {"type": EVENT_STATUS, "message": f"正在调用工具 {name}..."},
                {
                    "type": EVENT_TOOL_CALL,
                    "id": raw.get("run_id"),
                    "name": name,
                    "args": tool_input,
                },
            ]
            return out

        if kind == "on_tool_end":
            result = str(data.get("output", ""))
            return [
                {
                    "type": EVENT_TOOL_RESULT,
                    "id": raw.get("run_id"),
                    "name": name,
                    "result": result,
                }
            ]

        return []
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate && python -m pytest tests/test_harness_events.py -v
```

Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
cd /Users/lindaw/Documents/transmate
git add trans-mate/app/llm/harness/deep_agent_harness.py trans-mate/app/core/config.py trans-mate/tests/test_harness_events.py
git commit -m "feat: DeepAgentHarness 构造与 thread 上下文决策（checkpoint 有状态只注入末条消息）"
```

---

### Task 5: DeepAgentHarness 事件适配（plan_update / subagent / token 过滤）

**Files:**
- Modify: `trans-mate/app/llm/harness/deep_agent_harness.py`（`_adapt_event` 与 `astream`）
- Test: `trans-mate/tests/test_harness_events.py`（追加用例）

**Interfaces:**
- Consumes: Task 4 的 `DeepAgentHarness._adapt_event(raw, state)`、`SUBAGENT_NAMES`
- Produces: 完整事件适配 —— `write_todos` 工具 → `status + plan_update + tool_call`；`task` 工具 → `status + subagent_start + tool_call`（结束时 `subagent_end + tool_result`）；子 agent 的 token 事件被过滤；`state` dict 在多次 `_adapt_event` 调用间传递 `last_subagent_name`

- [ ] **Step 1: Write the failing test（追加到 tests/test_harness_events.py 末尾）**

```python
def tool_start_event(name, run_id, tool_input, tags=None):
    return {
        "event": "on_tool_start",
        "name": name,
        "tags": tags or [],
        "run_id": run_id,
        "data": {"input": tool_input},
    }


def tool_end_event(name, run_id, output, tags=None):
    return {
        "event": "on_tool_end",
        "name": name,
        "tags": tags or [],
        "run_id": run_id,
        "data": {"output": output},
    }


@pytest.mark.asyncio
@pytest.mark.unit
async def test_write_todos_emits_plan_update():
    stub = StubAgent(
        [
            tool_start_event(
                "write_todos",
                "t1",
                {"todos": [{"content": "查天气", "status": "pending"}]},
            ),
            tool_end_event("write_todos", "t1", "已更新"),
        ]
    )
    harness = DeepAgentHarness(agent=stub, checkpointer=None)
    out = [e async for e in harness.astream([HumanMessage(content="计划")], "conv-1")]

    types = [e["type"] for e in out]
    assert types == [
        "agent_start",
        "status",
        "plan_update",
        "tool_call",
        "tool_result",
    ]
    plan = out[2]
    assert plan["todos"] == [{"content": "查天气", "status": "pending"}]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_task_tool_emits_subagent_events():
    stub = StubAgent(
        [
            tool_start_event(
                "task",
                "t2",
                {"subagent_type": "stock_data_expert", "description": "查茅台日线"},
            ),
            tool_end_event("task", "t2", "日线数据已取回"),
        ]
    )
    harness = DeepAgentHarness(agent=stub, checkpointer=None)
    out = [e async for e in harness.astream([HumanMessage(content="茅台行情")], "conv-1")]

    types = [e["type"] for e in out]
    assert types == [
        "agent_start",
        "status",
        "subagent_start",
        "tool_call",
        "subagent_end",
        "tool_result",
    ]
    sub_start = out[2]
    assert sub_start["name"] == "stock_data_expert"
    assert sub_start["task"] == "查茅台日线"
    sub_end = out[4]
    assert sub_end["name"] == "stock_data_expert"
    assert "日线数据已取回" in sub_end["result"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_subagent_tokens_filtered():
    """子智能体的 LLM token 不进入主回复流，主智能体 token 正常透传"""
    stub = StubAgent(
        [
            token_event("主"),
            token_event("子", tags=["stock_data_expert"]),
            token_event("答"),
        ]
    )
    harness = DeepAgentHarness(agent=stub, checkpointer=None)
    out = [e async for e in harness.astream([HumanMessage(content="hi")], "conv-1")]
    tokens = [e["content"] for e in out if e["type"] == "token"]
    assert tokens == ["主", "答"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normal_tool_keeps_protocol():
    stub = StubAgent(
        [
            tool_start_event("get_weather", "t3", {"city": "北京"}),
            tool_end_event("get_weather", "t3", "北京晴"),
        ]
    )
    harness = DeepAgentHarness(agent=stub, checkpointer=None)
    out = [e async for e in harness.astream([HumanMessage(content="北京天气")], "conv-1")]

    types = [e["type"] for e in out]
    assert types == ["agent_start", "status", "tool_call", "tool_result"]
    assert out[2]["args"] == {"city": "北京"}
    assert out[3]["result"] == "北京晴"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate && python -m pytest tests/test_harness_events.py -v
```

Expected: 新增 4 条 FAIL（`plan_update` 等事件未产生 / 子 agent token 未过滤），原 5 条 PASS

- [ ] **Step 3: Write minimal implementation**

`deep_agent_harness.py` 顶部 events 导入改为：

```python
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
```

`astream` 中的循环把 `state` 提到循环外（同一轮内共享，记录最近的子智能体名）：

```python
        started = False
        state: dict = {}
        async for raw in self._agent.astream_events(
            {"messages": messages}, config, version="v2"
        ):
            if not started:
                started = True
                yield {"type": EVENT_AGENT_START, "agent": AGENT_NAME}
            for event in self._adapt_event(raw, state):
                yield event
```

整体替换 `_adapt_event` 为：

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate && python -m pytest tests/test_harness_events.py -v
```

Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/lindaw/Documents/transmate
git add trans-mate/app/llm/harness/deep_agent_harness.py trans-mate/tests/test_harness_events.py
git commit -m "feat: harness 事件适配（plan_update/subagent 事件、子agent token 过滤）"
```

---

### Task 6: streaming.py 切换到 harness + 更新流式测试

**Files:**
- Modify: `trans-mate/app/llm/streaming.py`（整体重写，`build_history_messages` 保持不变）
- Modify: `trans-mate/tests/test_streaming.py`（整体重写）

**Interfaces:**
- Consumes: `get_agent_harness()`（Task 2 工厂）、harness 事件（Task 5）
- Produces: `stream_agent_events(history: List[BaseMessage], thread_id: str) -> AsyncGenerator[dict, None]` —— 签名新增必填 `thread_id`；产出协议事件 + 聚合 `done`（`content` 为累计 token，`tool_events` 带配对结果）与 `error` 兜底；`build_history_messages` 不变。**main.py 此时签名不匹配，本任务结束时 `test_ws_protocol.py` 会失败 —— Task 7 一并修复（本任务提交前只跑 test_streaming.py）**

- [ ] **Step 1: 重写 tests/test_streaming.py（failing test）**

```python
"""
流式事件服务单元测试：harness 事件到 WebSocket 事件协议的聚合
"""
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.llm import streaming
from app.llm.streaming import stream_agent_events, build_history_messages


class StubHarness:
    """伪造 harness：回放预设事件，记录收到的 history 与 thread_id"""

    def __init__(self, events):
        self.events = events
        self.received = None

    async def astream(self, history, thread_id):
        self.received = (list(history), thread_id)
        for event in self.events:
            yield event


def stub_factory(harness):
    return lambda: harness


@pytest.mark.asyncio
@pytest.mark.unit
async def test_streaming_token_flow(monkeypatch):
    stub = StubHarness(
        [
            {"type": "agent_start", "agent": "deep_agent"},
            {"type": "token", "content": "你"},
            {"type": "token", "content": "好"},
        ]
    )
    monkeypatch.setattr(streaming, "get_agent_harness", stub_factory(stub))

    history = [HumanMessage(content="hi")]
    events = [e async for e in stream_agent_events(history, "conv-1")]

    assert [e["type"] for e in events] == ["agent_start", "token", "token", "done"]
    assert events[-1]["content"] == "你好"
    assert stub.received == ([HumanMessage(content="hi")], "conv-1")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_streaming_tool_call_pairing(monkeypatch):
    stub = StubHarness(
        [
            {"type": "agent_start", "agent": "deep_agent"},
            {"type": "token", "content": "我先查一下"},
            {"type": "tool_call", "id": "t1", "name": "get_weather", "args": {"city": "北京"}},
            {"type": "tool_result", "id": "t1", "name": "get_weather", "result": "北京晴，25度"},
            {"type": "token", "content": "查询完成"},
        ]
    )
    monkeypatch.setattr(streaming, "get_agent_harness", stub_factory(stub))

    events = [e async for e in stream_agent_events([HumanMessage(content="北京天气")], "conv-1")]

    types = [e["type"] for e in events]
    assert types == ["agent_start", "token", "tool_call", "tool_result", "token", "done"]

    done = events[-1]
    assert done["content"] == "我先查一下查询完成"
    assert done["tool_events"][0]["result"] == "北京晴，25度"
    # tool_result 事件本身也要透传给前端
    assert events[3]["result"] == "北京晴，25度"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_streaming_tool_result_truncated(monkeypatch):
    stub = StubHarness(
        [
            {"type": "tool_call", "id": "t1", "name": "web_search", "args": {"q": "x"}},
            {"type": "tool_result", "id": "t1", "name": "web_search", "result": "长" * 3000},
        ]
    )
    monkeypatch.setattr(streaming, "get_agent_harness", stub_factory(stub))

    events = [e async for e in stream_agent_events([HumanMessage(content="q")], "conv-1")]
    result = events[1]["result"]
    assert len(result) == streaming.MAX_TOOL_RESULT_LENGTH + len("...(截断)")
    assert result.endswith("...(截断)")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_streaming_exception_yields_error(monkeypatch):
    class BrokenHarness:
        async def astream(self, history, thread_id):
            yield {"type": "token", "content": "部分"}
            raise RuntimeError("LLM 炸了")

    monkeypatch.setattr(streaming, "get_agent_harness", stub_factory(BrokenHarness()))

    events = [e async for e in stream_agent_events([HumanMessage(content="hi")], "conv-1")]
    assert events[-1]["type"] == "error"
    assert "LLM 炸了" in events[-1]["message"]


@pytest.mark.unit
def test_build_history_messages():
    class Record:
        def __init__(self, role, content):
            self.role = role
            self.content = content

    history = build_history_messages(
        [Record("user", "第一问"), Record("assistant", "第一答"), Record("user", "第二问")]
    )
    assert len(history) == 3
    assert isinstance(history[0], HumanMessage)
    assert isinstance(history[1], AIMessage)
    assert history[-1].content == "第二问"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate && python -m pytest tests/test_streaming.py -v
```

Expected: FAIL（旧 `stream_agent_events` 只收 1 个参数、无 `get_agent_harness` 属性可 patch 时报 TypeError/AttributeError）

- [ ] **Step 3: 整体重写 app/llm/streaming.py**

```python
"""
智能体流式服务
将 agent harness 产出的事件流聚合为 WebSocket 事件协议（ZCode 式）
"""
import logging
from typing import AsyncGenerator, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.llm.harness import get_agent_harness

logger = logging.getLogger(__name__)

# 推送给前端的工具结果最大长度
MAX_TOOL_RESULT_LENGTH = 2000


def _truncate(text: str, limit: int = MAX_TOOL_RESULT_LENGTH) -> str:
    if len(text) > limit:
        return text[:limit] + "...(截断)"
    return text


async def stream_agent_events(
    history: List[BaseMessage], thread_id: str
) -> AsyncGenerator[dict, None]:
    """
    驱动 agent harness 执行一轮并聚合事件。

    history: 完整对话消息（含本次用户输入）
    thread_id: 会话 thread 标识（conv-{conversation_id}）
    依次产出事件 dict：
      - harness 归一化事件透传：status / agent_start / token /
        tool_call / tool_result / plan_update / subagent_start / subagent_end
      - {"type": "done", "content", "tool_events"}   完成，content 为累计 token
      - {"type": "error", "message"}        执行异常
    """
    streamed_answer = ""
    tool_events: List[dict] = []

    try:
        async for event in get_agent_harness().astream(history, thread_id):
            kind = event.get("type")

            if kind == "token":
                streamed_answer += event["content"]
            elif kind == "tool_call":
                tool_events.append(dict(event))
            elif kind == "tool_result":
                result = _truncate(str(event.get("result", "")))
                event["result"] = result
                for tool_event in tool_events:
                    if tool_event["id"] == event["id"]:
                        tool_event["result"] = result

            yield event

        yield {
            "type": "done",
            "content": streamed_answer,
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
```

注意：删除文件顶部对 `app.llm.router` 的 import —— 从此 `router.py` 停用（文件保留）。

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate && python -m pytest tests/test_streaming.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/lindaw/Documents/transmate
git add trans-mate/app/llm/streaming.py trans-mate/tests/test_streaming.py
git commit -m "refactor: streaming 切换到 agent harness 驱动（thread_id 透传、事件聚合）"
```

---

### Task 7: 应用接线（main.py lifespan/thread_id、会话删除联动）+ WS 测试

**Files:**
- Modify: `trans-mate/main.py`（imports、lifespan、`run_agent_stream`）
- Modify: `trans-mate/app/base/chat_routes.py`（删除会话清 checkpoint）
- Modify: `trans-mate/tests/test_ws_protocol.py`（签名适配）
- Test: `trans-mate/tests/test_chat_ws.py`（新建）

**Interfaces:**
- Consumes: `get_agent_harness()`（Task 2）、`stream_agent_events(history, thread_id)`（Task 6）、`harness.initialize()/aclose()/clear_thread()`（Task 4）
- Produces: WS 全链路（`/ws` → streaming → harness，thread_id = `conv-{conversation_id}`）；`DELETE /api/conversations/{id}` 成功后调用 `clear_thread(f"conv-{id}")`；应用启动时初始化 harness、关停时释放

- [ ] **Step 1: Write the failing test（新建 tests/test_chat_ws.py）**

```python
"""
WebSocket + harness 集成测试：streaming 聚合、thread_id 透传、会话删除清 checkpoint
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from conftest import make_sqlite_engine


@pytest.fixture
def client(monkeypatch):
    from app.models.user import User  # noqa: F401
    from app.models.conversation import Conversation, ChatMessage  # noqa: F401

    engine = make_sqlite_engine()
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    import main as main_module
    monkeypatch.setattr(main_module, "SessionLocal", TestSession)
    monkeypatch.setattr(main_module, "init_db", lambda: None)

    with TestClient(main_module.app) as test_client:
        yield test_client, engine


class StubHarness:
    """记录 thread_id 与 clear_thread 调用的 harness 替身"""

    def __init__(self):
        self.threads = []
        self.cleared = []

    async def astream(self, history, thread_id):
        self.threads.append(thread_id)
        yield {"type": "agent_start", "agent": "deep_agent"}
        yield {"type": "token", "content": "好的"}
        yield {"type": "tool_call", "id": "t1", "name": "get_weather", "args": {"city": "北京"}}
        yield {"type": "tool_result", "id": "t1", "name": "get_weather", "result": "晴"}
        yield {"type": "plan_update", "todos": [{"content": "查天气", "status": "completed"}]}
        yield {"type": "subagent_start", "name": "stock_data_expert", "task": "查行情"}
        yield {"type": "subagent_end", "name": "stock_data_expert", "result": "完成"}

    async def clear_thread(self, thread_id):
        self.cleared.append(thread_id)


@pytest.mark.integration
def test_ws_flow_uses_harness_thread(client, monkeypatch):
    test_client, engine = client
    stub = StubHarness()
    from app.llm import streaming
    monkeypatch.setattr(streaming, "get_agent_harness", lambda: stub)

    with test_client.websocket_connect("/ws?user_id=u1") as ws:
        ws.send_text(json.dumps({"type": "chat_message", "message": "北京天气", "user_id": "u1"}))
        events = []
        while True:
            e = json.loads(ws.receive_text())
            events.append(e)
            if e["type"] == "done":
                break

    types = [e["type"] for e in events]
    assert types[0] == "conversation_created"
    for expected in ["agent_start", "token", "tool_call", "tool_result",
                     "plan_update", "subagent_start", "subagent_end", "done"]:
        assert expected in types

    done = events[-1]
    assert done["content"] == "好的"
    assert done["tool_events"][0]["result"] == "晴"
    # thread_id 按会话 id 生成
    assert stub.threads == [f"conv-{events[0]['conversation_id']}"]


@pytest.mark.integration
def test_delete_conversation_clears_checkpoint(client, monkeypatch):
    test_client, engine = client
    stub = StubHarness()
    import app.base.chat_routes as chat_routes
    monkeypatch.setattr(chat_routes, "get_agent_harness", lambda: stub)

    conv = test_client.post(
        "/api/conversations", json={"user_id": "u1", "title": "测试"}
    ).json()
    resp = test_client.delete(f"/api/conversations/{conv['id']}")
    assert resp.status_code == 200
    assert stub.cleared == [f"conv-{conv['id']}"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate && python -m pytest tests/test_chat_ws.py -v
```

Expected: FAIL（`chat_routes` 无 `get_agent_harness` 属性可 patch / clear 未发生）

- [ ] **Step 3: 修改 main.py**

3 处修改：

(a) import 区（`from app.llm.streaming import ...` 之后）加：

```python
from app.llm.harness import get_agent_harness
```

(b) `lifespan` 整体替换为：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("正在初始化数据库...")
    init_db()
    logging.info("数据库初始化完成")

    try:
        await get_agent_harness().initialize()
        logging.info("agent harness 初始化完成")
    except Exception as e:
        logging.error(f"agent harness 初始化失败（首次调用时将重试）: {e}")

    yield
    logging.info("应用关闭，清理资源...")
    try:
        await get_agent_harness().aclose()
    except Exception as e:
        logging.warning(f"agent harness 关闭异常: {e}")
```

(c) `run_agent_stream` 中的调用行替换为：

```python
        async for event in stream_agent_events(history, f"conv-{conversation_id}"):
```

- [ ] **Step 4: 修改 chat_routes.py**

文件顶部 import 区加：

```python
import logging

from app.llm.harness import get_agent_harness
```

`logger = logging.getLogger(__name__)` 加在 import 之后。删除端点整体替换为：

```python
@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """删除会话及其全部消息，并清理 agent checkpoint"""
    if not chat_service.delete_conversation(db, conversation_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    try:
        await get_agent_harness().clear_thread(f"conv-{conversation_id}")
    except Exception as e:
        logger.warning(f"清除会话 checkpoint 失败 conversation_id={conversation_id}: {e}")
    return {"message": "会话已删除"}
```

- [ ] **Step 5: 适配 tests/test_ws_protocol.py 的 fake 签名**

3 处替换 —— 每个伪造流的函数签名 `async def fake_stream(history):` / `async def slow_stream(history):` 改为双参数，并在第一个测试里记录 thread_id：

(a) `test_ws_full_flow_with_auto_conversation` 中：

```python
    seen_threads = []

    async def fake_stream(history, thread_id):
        seen_threads.append(thread_id)
        yield {"type": "status", "message": "正在分析意图..."}
        yield {"type": "agent_start", "agent": "base_agent"}
        yield {"type": "token", "content": f"收到{len(history)}条历史。"}
        yield {"type": "tool_call", "id": "t1", "name": "get_weather", "args": {"city": "北京"}}
        yield {"type": "tool_result", "id": "t1", "name": "get_weather", "result": "北京晴"}
        yield {
            "type": "done",
            "content": "收到1条历史。",
            "tool_events": [{"id": "t1", "name": "get_weather", "args": {"city": "北京"}, "result": "北京晴"}],
        }
```

并在该测试 `finally:` 之前的断言末尾（`db.close()` 之前）追加：

```python
        # 两轮对话各自携带 conv-{conversation_id} 的 thread 标识
        assert seen_threads == [f"conv-{conversation_id}"] * 2
```

(b) `test_ws_stop_generation` 中：`async def slow_stream(history):` → `async def slow_stream(history, thread_id):`

(c) `test_ws_plain_text_compat` 中：`async def fake_stream(history):` → `async def fake_stream(history, thread_id):`

- [ ] **Step 6: Run test to verify it passes**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate && python -m pytest tests/test_chat_ws.py tests/test_ws_protocol.py -v
```

Expected: test_chat_ws 2 passed；test_ws_protocol 3 passed

- [ ] **Step 7: 后端全量回归**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate && python -m pytest tests/ -v
```

Expected: 全部通过（含 test_harness_base/test_rag_tool/test_harness_events/test_streaming/test_chat_service 等）

- [ ] **Step 8: Commit**

```bash
cd /Users/lindaw/Documents/transmate
git add trans-mate/main.py trans-mate/app/base/chat_routes.py trans-mate/tests/test_ws_protocol.py trans-mate/tests/test_chat_ws.py
git commit -m "feat: 应用接线 agent harness（lifespan 初始化、thread_id 透传、删除会话清 checkpoint）"
```

---

### Task 8: 前端类型与事件处理（types + useAgentChat + i18n）

**Files:**
- Modify: `trans-mate-web-ui/src/types/index.ts`
- Modify: `trans-mate-web-ui/src/composables/useAgentChat.ts`
- Modify: `trans-mate-web-ui/src/i18n/zh.ts`
- Modify: `trans-mate-web-ui/src/i18n/en.ts`

**Interfaces:**
- Consumes: 后端事件协议（Global Constraints 中的事件名）
- Produces:
  - `TodoStatus = 'pending' | 'in_progress' | 'completed'`；`TodoItem { content: string; status: TodoStatus }`（均从 `@/types` 导出）
  - `AgentEvent` 联合新增 `plan_update / subagent_start / subagent_end` 三种成员；`Message` 新增 `todos?: TodoItem[]`、`activeSubagent?: string`
  - `useAgentChat` 内 `handleAgentEvent` 处理 3 个新事件；i18n 新 key：`chat.planTitle` / `chat.subagentWorking` / `chat.toolNameTodos` / `chat.toolNameTask`

- [ ] **Step 1: 修改 types/index.ts**

(a) `ToolCallBlock` 接口之后新增：

```ts
type TodoStatus = 'pending' | 'in_progress' | 'completed'

interface TodoItem {
  content: string
  status: TodoStatus
}
```

(b) `Message` 接口末尾（`agent?: string;` 之后）追加：

```ts
  // deep agent 扩展：任务计划（write_todos）
  todos?: TodoItem[]
  // deep agent 扩展：正在执行的子智能体名
  activeSubagent?: string
```

(c) `AgentEvent` 联合中 `{ type: 'conversation_created' ... }` 之前插入：

```ts
  | { type: 'plan_update'; todos: TodoItem[] }
  | { type: 'subagent_start'; name: string; description?: string; task?: string }
  | { type: 'subagent_end'; name: string; result?: string }
```

(d) export 列表加 `TodoStatus, TodoItem`：

```ts
export type {
  Message,
  ToolCallBlock,
  TodoStatus,
  TodoItem,
  AgentEvent,
  Conversation,
  ConversationMessage,
  WebSocketMessage,
  ParsedWebSocketMessage
}
```

- [ ] **Step 2: 修改 useAgentChat.ts 的 handleAgentEvent**

在 `case 'tool_result':` 块之后插入：

```ts
      case 'plan_update': {
        const index = ensureAssistantMessage()
        dialogue.value[index].todos = event.todos
        break
      }
      case 'subagent_start': {
        const index = ensureAssistantMessage()
        dialogue.value[index].activeSubagent = event.name
        processingStatus.value = t('chat.subagentWorking', { agent: event.name })
        break
      }
      case 'subagent_end': {
        const last = dialogue.value[dialogue.value.length - 1]
        if (last?.role === 'assistant') last.activeSubagent = undefined
        break
      }
```

- [ ] **Step 3: i18n 文案**

`src/i18n/zh.ts` 的 `chat` 对象内 `agentWorking: '智能体 {agent} 正在工作...',` 之后追加：

```ts
    planTitle: '任务计划',
    subagentWorking: '子智能体 {agent} 执行中...',
    toolNameTodos: '更新任务计划',
    toolNameTask: '派发子智能体',
```

`src/i18n/en.ts` 同位置追加：

```ts
    planTitle: 'Task Plan',
    subagentWorking: 'Sub-agent {agent} running...',
    toolNameTodos: 'Update task plan',
    toolNameTask: 'Dispatch sub-agent',
```

- [ ] **Step 4: 类型检查**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate-web-ui && npm run type-check
```

Expected: 无错误（`vue-tsc` 退出码 0）

- [ ] **Step 5: Commit**

```bash
cd /Users/lindaw/Documents/transmate
git add trans-mate-web-ui/src/types/index.ts trans-mate-web-ui/src/composables/useAgentChat.ts trans-mate-web-ui/src/i18n/zh.ts trans-mate-web-ui/src/i18n/en.ts
git commit -m "feat(web-ui): 前端支持 plan_update/subagent 事件与类型定义"
```

---

### Task 9: TodoPanel 组件与消息列表集成

**Files:**
- Create: `trans-mate-web-ui/src/components/agent/TodoPanel.vue`
- Modify: `trans-mate-web-ui/src/components/agent/MessageList.vue`
- Modify: `trans-mate-web-ui/src/components/agent/ToolCallBlockView.vue`

**Interfaces:**
- Consumes: `TodoItem`（Task 8）、i18n key `chat.planTitle/chat.subagentWorking/toolNameTodos/toolNameTask`（Task 8）
- Produces: `TodoPanel`（props：`todos: TodoItem[]`）；MessageList 中 assistant 消息渲染 todo 面板与子 agent 徽标；ToolCallBlockView 对 `write_todos`/`task` 显示友好名（默认折叠已是现状，无需改展开逻辑）

- [ ] **Step 1: 创建 TodoPanel.vue**

```vue
<template>
  <div class="todo-panel">
    <div class="todo-title">
      <i class="fas fa-list-check"></i>
      <span>{{ t('chat.planTitle') }}</span>
    </div>
    <div
      v-for="(todo, index) in todos"
      :key="index"
      :class="['todo-item', `status-${todo.status}`]"
    >
      <span class="todo-icon">
        <i v-if="todo.status === 'completed'" class="fas fa-check-circle"></i>
        <i v-else-if="todo.status === 'in_progress'" class="fas fa-circle-half-stroke"></i>
        <i v-else class="fas fa-circle-dot"></i>
      </span>
      <span class="todo-content">{{ todo.content }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from '@/i18n'
import type { TodoItem } from '@/types'

const { t } = useI18n()

defineProps<{ todos: TodoItem[] }>()
</script>

<style scoped>
.todo-panel {
  width: 100%;
  margin-bottom: 8px;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-soft-bg);
  box-sizing: border-box;
}

.todo-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--color-text-muted);
}

.todo-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 3px 0;
  font-size: 13px;
  color: var(--color-text);
}

.todo-item.status-completed {
  color: var(--color-text-faint);
  text-decoration: line-through;
}

.todo-item.status-pending .todo-icon {
  color: var(--color-text-faint);
}

.todo-item.status-in_progress .todo-icon {
  color: var(--color-primary);
}

.todo-item.status-completed .todo-icon {
  color: var(--color-success);
}

.todo-content {
  flex: 1;
  line-height: 1.5;
}
</style>
```

- [ ] **Step 2: MessageList.vue 集成**

(a) template 中 `<!-- 工具调用块（ZCode 式折叠面板） -->` 的 div 之前插入：

```vue
        <!-- 任务计划面板（deep agent todos） -->
        <TodoPanel
          v-if="message.role === 'assistant' && message.todos && message.todos.length"
          :todos="message.todos"
        />

        <!-- 子智能体运行徽标 -->
        <div v-if="message.activeSubagent" class="subagent-badge">
          <span class="mini-spinner"></span>
          <span>{{ t('chat.subagentWorking', { agent: message.activeSubagent }) }}</span>
        </div>
```

(b) script 的 import 区（`import ToolCallBlockView from './ToolCallBlockView.vue'` 之后）加：

```ts
import TodoPanel from './TodoPanel.vue'
```

(c) style 末尾（`</style>` 前）追加：

```css
/* 子智能体运行徽标 */
.subagent-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--color-primary);
}

.mini-spinner {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 2px solid rgba(37, 99, 235, 0.25);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

- [ ] **Step 3: ToolCallBlockView.vue 友好工具名**

(a) template 中 `<span class="tool-name">{{ tool.name }}</span>` 替换为：

```vue
      <span class="tool-name">{{ displayName }}</span>
```

(b) script 中 `const expanded = ref(false)` 之后加：

```ts
// 内置工具显示友好名（write_todos/task 已有专用 UI，避免暴露内部工具名）
const displayName = computed(() => {
  const map: Record<string, string> = {
    write_todos: t('chat.toolNameTodos'),
    task: t('chat.toolNameTask')
  }
  return map[props.tool.name] || props.tool.name
})
```

（`computed` 已在文件 import 中。）

- [ ] **Step 4: 类型检查**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate-web-ui && npm run type-check
```

Expected: 无错误

- [ ] **Step 5: Commit**

```bash
cd /Users/lindaw/Documents/transmate
git add trans-mate-web-ui/src/components/agent/
git commit -m "feat(web-ui): 任务计划面板与子智能体运行徽标"
```

---

### Task 10: 全量回归与手工联调

**Files:**
- 无新文件（验证任务）

**Interfaces:**
- Consumes: 全部前序任务成果
- Produces: 验证结论（测试全绿 + 手工清单通过）

- [ ] **Step 1: 后端全量测试**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate && python -m pytest tests/ -v
```

Expected: 全部通过

- [ ] **Step 2: 前端类型检查**

```bash
cd /Users/lindaw/Documents/transmate/trans-mate-web-ui && npm run type-check
```

Expected: 无错误

- [ ] **Step 3: 手工联调清单**

启动后端（`cd trans-mate && uvicorn main:app --reload`，需 `.env` 配好 DEFAULT_* 指向 Qwen）与前端（`cd trans-mate-web-ui && npm run dev` 或 `npm run electron:dev`），逐项验证：

1. **规划面板**：发送复杂多步任务（如"帮我查北京天气，再总结成一段话，并搜一下明天的新闻"）→ 出现"任务计划"面板，条目状态随执行从 pending → in_progress → completed
2. **子 agent**：问股票问题（如"贵州茅台最近的日线行情"）→ 出现"子智能体 stock_data_expert 执行中..."徽标 + task 工具块（显示"派发子智能体"）+ 最终回答
3. **停止生成**：生成中途点停止 → 收到 stopped，前端流式消息正常收尾
4. **多轮上下文（checkpoint）**：同一会话追问（"那再看看它的市盈率"）→ 回答能衔接上文；确认 `trans-mate/store/agent_checkpoints.sqlite` 文件已生成
5. **会话删除**：删除会话无报错，日志无"清除会话 checkpoint 失败"
6. **token 流纯净性**：观察股票问题的回答文本中不混入子 agent 的中间输出（若混入，检查 deepagents astream_events 的 tags 实际值，调整 `SUBAGENT_NAMES` 过滤逻辑后重测）

- [ ] **Step 4: 汇总结果并收尾提交**

```bash
cd /Users/lindaw/Documents/transmate
git status   # 确认无未提交文件（store/ 与 .sqlite 应被忽略）
git log --oneline -10
```

如有手工联调产生的修正（如 tags 过滤调整），逐项提交后再收尾。

---

## Self-Review 记录

- **Spec 覆盖**：spec §3.1/3.2 → Task 2；§3.3（含 ModelPool 勘误）→ Task 4；§3.4 → Task 6/7；§3.5 → Task 4；§4 → Task 2/5；§5 前端 → Task 8/9（§5.5 折叠：现状已默认折叠，改为友好名）；§6 → Task 4/7；§7 → Task 3/5/6/7；§8 → 各任务 + Task 10；§9 → Task 1。无遗漏
- **占位符扫描**：无 TBD/TODO；所有代码步骤给出完整代码
- **类型一致性**：`astream(history, thread_id)` 全链一致（base.py / DeepAgentHarness / StubHarness / streaming / fake_stream）；thread_id 格式统一 `conv-{id}`；事件名与 Global Constraints 一致；`TodoItem` 前后端字段一致（content/status）
- **顺序修正**：工厂单例测试原在 Task 2（会触发尚不存在的 `DeepAgentHarness` 导入），已移至 Task 4 测试文件
