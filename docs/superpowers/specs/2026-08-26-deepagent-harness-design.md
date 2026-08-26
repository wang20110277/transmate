# TransMate 后端集成 deepagents 作为 Agent Harness — 设计文档

日期：2026-08-26
状态：已确认（三节设计均经用户逐节确认）

## 1. 背景与目标

TransMate 后端（`trans-mate/`，FastAPI + LangChain 1.2.0 + LangGraph 1.0.2）当前的
agent 架构是 `app/llm/router.py` 里的 LangGraph 路由图：RAG 优先短路 → 关键词意图
分类 → base_agent（天气/搜索）/ stock_agent。该架构路由逻辑硬编码、无规划能力、
无子 agent 调度、多轮状态仅靠消息拼接。

目标：用 LangChain `deepagents`（v0.7.8）替换 router 成为主 agent harness，
获得规划（todo）、子 agent（task）、虚拟文件系统等能力，同时保持现有 WS 事件流
协议与消息持久化基本不变，前端增加规划面板与子 agent 状态展示。

## 2. 已确认的决策记录

| # | 决策 | 选择 |
|---|---|---|
| 1 | deepagents 定位 | **替换 router 成为主 harness**；stock/RAG 降级为工具/子 agent，删除关键词分类路由 |
| 2 | 模型接入 | 主 agent 与子 agent **全部用默认 Qwen**（`DEFAULT_*` 配置，复用 `ModelPool`） |
| 3 | 工具划分 | RAG/天气/搜索做主 agent 工具；**stock 整体作为一个子 agent**（6 个 tushare 工具 + 现有提示词） |
| 4 | 状态持久化 | **加 langgraph checkpointer**（AsyncSqliteSaver，`langgraph-checkpoint-sqlite` 已在依赖中） |
| 5 | 前端对接 | **同步扩展前后端**：后端新增专用事件，前端加 todo 面板与子 agent 状态展示 |
| 6 | 集成方案 | **抽象 harness 层**：`app/llm/harness/` 接口 + DeepAgentHarness 实现，上层只依赖接口 |

## 3. 架构

### 3.1 新增 harness 包

```
app/llm/harness/
├── __init__.py            # get_agent_harness() → DeepAgentHarness 单例
├── base.py                # AgentHarness 抽象基类 + clear_thread 接口
├── events.py              # 归一化事件协议（事件类型常量 + TypedDict）
└── deep_agent_harness.py  # DeepAgentHarness：基于 deepagents 的实现
```

### 3.2 抽象接口（base.py）

```python
class AgentHarness(ABC):
    """agent harness 抽象：上层只依赖此接口，未来可替换实现"""

    @abstractmethod
    def astream(
        self, history: list[BaseMessage], thread_id: str
    ) -> AsyncGenerator[dict, None]:
        """驱动 agent 执行一轮，产出归一化事件（见 events.py）。

        history 为 DB 拼出的完整消息列表（含本次 user 输入，构建方式与现状
        相同）；是否全量注入由实现根据 checkpoint 状态决定（见 3.5）。
        """

    @abstractmethod
    async def clear_thread(self, thread_id: str) -> None:
        """清除某个会话的持久化状态（会话删除时调用）"""
```

### 3.3 DeepAgentHarness 组装（deep_agent_harness.py）

- `model=ModelPool()`（duck-type `bind_tools`，与现有 base_agent 用法一致）
- `tools=[search_knowledge_base, get_weather, web_search]`
  - `search_knowledge_base`：包装 `rag_agent.retrieve`，沿用 15s 超时 +
    `asyncio.to_thread` 保护；超时/异常返回"知识库暂不可用"文案（不抛错，agent
    可转用 web_search）
- `subagents=[stock_subagent]`：6 个 tushare 工具（get_stock_info /
  get_stock_daily / get_stock_realtime / get_index_daily /
  get_stock_daily_basic / search_stock）+ 迁移现有 stock_agent 系统提示词
- `middleware=[TodoListMiddleware()]` — **显式启用**（deepagents v0.7 起默认关闭）
- `checkpointer=AsyncSqliteSaver`，库文件 `store/agent_checkpoints.sqlite`
  （`store/` 已被 git 忽略），路径经 `app/core/config.py` 配置
- 系统提示词：迁移 base_agent 提示词并增加工具使用指引（何时查知识库、何时派
  stock 子 agent、何时用 todo 规划复杂任务）

### 3.4 调用链

```
main.py (/ws) → streaming.py（通用层：聚合 tool_events、done 兜底、错误包装）
             → get_agent_harness().astream(本次 user 消息, thread_id)
             → DeepAgentHarness → deepagents → Qwen + 工具/子 agent
```

- `streaming.py`：不再 import `router.py`；原子事件来自 harness，`stream_agent_events`
  保留 token 累积、`tool_events` 聚合、`done`/`error` 兜底与非流式路径补发逻辑
- `router.py` / `base_agent.py` / `stock_agent.py` 停用不删（不再被引用，保留回滚
  便利）；stock 提示词与工具清单迁入 harness 子 agent 定义

### 3.5 上下文来源（关键决策）

启用 checkpointer 后，多轮上下文由 checkpoint 累积（config
`{"configurable": {"thread_id": ...}}`），避免历史重复注入：

- **thread 已有 checkpoint 状态**：harness 只把 history 的**最后一条**（本次
  user 输入）注入 agent，其余上下文来自 checkpoint
- **thread 无状态**（新会话首次调用，或无 checkpoint 的存量会话）：harness 把
  全量 history 注入 agent

该决策封装在 DeepAgentHarness 内（调 checkpoint 读一次 thread 状态判断），
上层 streaming.py / main.py 的 history 构建逻辑与现状完全相同。

## 4. 事件协议

### 4.1 新增事件（events.py 定义，WS 透传）

| 事件 | 载荷 | 触发时机 |
|---|---|---|
| `plan_update` | `{todos: [{content, status}]}`，status ∈ pending/in_progress/completed | 主 agent 调用 `write_todos` |
| `subagent_start` | `{name, description, task}` | 主 agent 调用 `task` 派发子 agent |
| `subagent_end` | `{name, result}` | 子 agent 完成，`task` 返回 |

### 4.2 适配规则（DeepAgentHarness.astream 内，astream_events v2）

- `on_tool_start` 按工具名分流：`write_todos` → `plan_update`（从 args 解析）；
  `task` → `subagent_start`；其余 → 普通 `tool_call`
- `on_tool_end` 对应：`task` → `subagent_end`；其余 → `tool_result`
- `write_todos`/`task` **同时保留**普通 `tool_call/tool_result` 事件（前端可不
  渲染），保证 `tool_events` 落库完整
- 现有事件 `status/agent_start/token/tool_call/tool_result/done/stopped/error/
  conversation_created` 全部不变，但来源调整（原 router 节点映射随 router 一起
  消失）：
  - `agent_start`：deep agent 主图启动时发一次（`agent="deep_agent"`）
  - `status`：`on_tool_start` 时发 `"正在调用工具 {name}..."`，替代原
    `"正在检索知识库/正在分析意图"` 路由阶段提示

## 5. 前端改动（trans-mate-web-ui）

1. `types/index.ts`：`AgentEvent` 联合类型加 3 种事件；`Message` 加
   `todos?: TodoItem[]`、`activeSubagent?: string`
2. `useAgentChat.ts`：
   - `plan_update` → 整组替换当前流式 assistant 消息的 `todos`（write_todos
     每次全量写）
   - `subagent_start` → 置 `activeSubagent`；`subagent_end` → 清除
   - `done` 时最终 `todos` 随消息保留；刷新后从 `tool_events` 恢复留待后续迭代
3. 新组件 `src/components/agent/TodoPanel.vue`：计划清单（checkbox 样式区分
   pending/in_progress/completed），`MessageList.vue` 中 assistant 消息的
   `todos` 非空时显示
4. `MessageList.vue`：assistant 消息头部加子 agent 运行徽标（复用
   `processingStatus` 样式风格）
5. `ToolCallBlockView.vue`：`write_todos`/`task` 工具块默认折叠（已有专用 UI）
6. i18n（`zh.ts`/`en.ts`）：新增计划/子 agent 文案

验证：`vue-tsc` 类型检查 + Electron dev 手工联调（项目无前端测试设施）。

## 6. 持久化（双轨）

- **消息落库（不变）**：`run_agent_stream` 照旧存 user/assistant 消息 +
  `tool_events`，前端历史加载 REST 不动
- **agent 状态（新增）**：`AsyncSqliteSaver` 存 todo/虚拟文件系统/子 agent 上下文，
  `thread_id = conv-{conversation_id}`
  - `AsyncSqliteSaver` 需异步上下文管理器初始化：harness 模块级持有，FastAPI
    `lifespan`（现有）里进入/退出
  - **会话删除联动**：`chat_service.delete_conversation` 成功后调
    `harness.clear_thread(thread_id)`，避免孤儿 checkpoint

## 7. 错误处理

- RAG 工具：超时/异常返回降级文案，不阻断主流程
- 工具异常：deepagents 将工具错误回传模型自行处理；harness 层 catch 全局异常 →
  `error` 事件（现有路径不变）
- `stop` 中断：现有 `asyncio.CancelledError` → `stopped` 事件路径保持
- SQLite checkpoint 写失败：记日志降级（不落 checkpoint），对话仍完成 —— 消息
  落库是持久化主轨

## 8. 测试（pytest，沿用现有 tests/ 结构）

1. `tests/test_harness_events.py`：fake model（预设 tool_calls）驱动
   `DeepAgentHarness.astream`，断言事件序列（write_todos→plan_update、
   task→subagent_start/end、普通工具→tool_call/tool_result）
2. `tests/test_rag_tool.py`：RAG 工具超时降级与正常检索两条路径（mock
   `rag_agent.retrieve`）
3. `tests/test_chat_ws.py`：`TestClient.websocket_connect` 全链路 —— 发消息 →
   收事件 → done，assistant 消息落库；`delete_conversation` 后 checkpoint 清除
4. 手工联调清单：规划面板、子 agent 徽标、停止生成、断线重连后继续同会话

## 9. 依赖变更

- `requirements.txt` 新增 `deepagents==0.7.8`（要求 langchain>=1.0，与现有
  langchain 1.2.0 / langgraph 1.0.2 兼容）
- `langgraph-checkpoint-sqlite==3.0.3` 已存在，无需新增

## 10. 风险与边界

- Qwen 工具调用质量决定 RAG/子 agent 触发时机：系统提示词写明工具使用指引；
  原"RAG 优先短路"行为被"LLM 自主决定"取代是既定决策的必然结果
- 虚拟文件系统是 checkpoint 内的会话内存态，不接触真实磁盘，无安全面
- 单进程 SQLite checkpoint 不支持多 worker：当前部署形态（单进程/Electron 本地）
  够用；未来多 worker 可切 `langgraph-checkpoint-redis`（Redis 基础设施已有）
- deepagents v0.7 移除了旧版兼容 shim，`TodoListMiddleware` 必须显式加入
