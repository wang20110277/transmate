# Skill 集成与用户云工作区 · 设计文档

日期:2026-08-26
状态:已与用户逐节确认

## 1. 背景与目标

TransMate 的 agent 能力目前基于 deepagents 0.7.8 的 `DeepAgentHarness`(虚拟文件系统 + TodoList 规划 + stock 子智能体)。本期要补上两块:

1. **Skill 集成**:从可配置的 GitHub 仓库(默认 `anthropics/skills`)浏览、安装技能;对话时把已装技能的 name+description 注入 system prompt,模型自动判断适用后用 `read_file` 读取 SKILL.md 全文并照做(渐进式披露)。
2. **用户云工作区(最小闭环)**:产品定位是"账号即工作空间,一切跟随账号漫游"——前端(Electron/Web)只是壳,工作成果跟账号走。为此引入服务器端每用户沙箱、云端技能库(PG 清单 + MinIO 文件)、最小制品链路(`save_artifact` + 列表/下载)。

**不在本期**:知识库 pgvector 迁移、记忆、MCP 配置云端化、多副本部署(见第 10 节技术债)。

## 2. 总体架构

```
┌─ 前端(Electron/Web,纯壳)────────────────────────────┐
│  会话页(无目录选择器) · 技能页 Skills.vue · 制品面板      │
└──────────────┬────────────────────────────────────┘
               │ REST/WS(现有鉴权,user_id 贯穿所有新接口)
┌──────────────▼────────────────────────────────────┐
│ FastAPI 后端(单实例 docker)                         │
│ ① SkillService    GitHub 注册表 + 安装/卸载            │
│ ② 沙箱管理         store/sandbox/{user_id}/...        │
│ ③ 制品服务         save_artifact 工具 + 列表/下载 API   │
│ ④ DeepAgentHarness agent 工厂缓存键 = user_id          │
└───┬──────────────────┬────────────────────────────┘
    │                  │
  MinIO               PG
  skills/{uid}/{name}/   trans_user_skill(安装清单,含版本)
  artifacts/{uid}/...    trans_artifact(制品清单)
                         trans_conversation / trans_chat_message(对话,已有)
```

两个核心概念拆分:

- **工作沙箱 ≠ 制品库**。沙箱是"热的、过程性的"(agent 正在编辑/查找的文件,要低延迟、支持 glob/grep/edit),放服务器真实目录;制品库是"冷的、成果性的"(PPT 等交付物),显式保存到 MinIO,跨设备浏览/下载。过程在沙箱,成果进 MinIO。
- **Skill 的"存"和"用"是两条链路**。存:GitHub 下载 → 该用户的 MinIO 技能空间 + PG 安装清单(跨设备漫游)。用:构建 agent 时物化到服务器本地缓存目录,v1 用物化(简单可靠),后续可换 MinIO 直读 backend。

## 3. 组件设计

### 3.1 SkillService(新增 `app/services/skill_service.py`)

- `list_registry()`:GitHub Contents API 列出仓库技能目录(配置:owner/repo/ref/子目录前缀,默认 `anthropics/skills` @ main),读取每个 SKILL.md frontmatter 返回 name/description/license;TTL 缓存。
- `list_installed(user_id)`:读 PG `trans_user_skill`。
- `install(user_id, name, source)`:定位仓库目录 → 逐文件下载(单文件 ≤10MB、单技能 ≤200 文件、跳过软链接)→ 先传 MinIO 临时前缀,全部成功后落到 `skills/{user_id}/{name}/` 并写 PG 清单(版本=仓库 ref sha);失败清理临时对象。
- `uninstall(user_id, name)`:PG 名称正则校验(`^[a-z0-9-]+$`,杜绝路径拼接)→ 删 MinIO 前缀 + PG 清单,物化缓存失效。
- 配置(GitHub token 可选、代理可选、仓库地址、MinIO endpoint/凭据、缓存 TTL)进 `app/core/config.py`,沿用现有 env 方式。

### 3.2 沙箱管理

- 每用户根:`store/sandbox/{user_id}/`;会话子目录:`sessions/{conv-id}/`,首轮消息惰性创建,前端**无目录选择器**。
- backend root = **用户根**(非会话子目录):跨会话成果互相可见,支持"上次那个 PPT 再改改";当前会话默认工作目录写入 system prompt。

### 3.3 Harness 接线(改造 `app/llm/harness/deep_agent_harness.py`)

```python
backend = CompositeBackend(
    default=FilesystemBackend(root_dir=用户沙箱根, virtual_mode=True),
    routes={"/skills/": FilesystemBackend(root_dir=用户技能物化缓存)},
)
agent = create_deep_agent(
    ..., skills=["/skills/"], backend=backend,
    tools=[现有工具..., save_artifact], middleware=[TodoListMiddleware()],
    subagents=[stock...], checkpointer=AsyncSqliteSaver(共享),
)
```

- `astream()` 增加 user 上下文参数;agent **工厂缓存键 = user_id**(LRU,上限 8;`user_id` 缺失时保持现状虚拟文件系统路径,向后兼容)。
- checkpointer 全局共享,agent 重建不丢对话状态。
- 首次构建某用户 agent 或 PG 清单版本变化时,把 MinIO 技能物化到 `store/skill_cache/{user_id}/`;物化失败降级为无 skills 运行(警告日志),不阻塞对话。
- system prompt 补充:当前会话工作目录、其他会话成果位置、技能库 `/skills/` 只读、产出可交付文件后调用 `save_artifact`。

### 3.4 制品链路(最小)

- `save_artifact` 工具(agent 调用):参数(沙箱内源路径、可选名称/描述)→ 上传 MinIO `artifacts/{user_id}/{artifact_id}/{filename}` → PG `trans_artifact` 记录(名称、大小、来源会话、时间)→ 返回制品 ID。上限:单制品 200MB、每用户 500 个。
- API:`GET /api/artifacts`(分页)、`GET /api/artifacts/{id}/download`(预签名 URL,1 小时时效)。

### 3.5 数据模型(alembic 迁移)

- `trans_user_skill`:id、user_id、name、version(ref sha)、source(仓库配置快照)、metadata JSON、installed_at。
- `trans_artifact`:id、user_id、conversation_id、filename、size、storage_key、description、created_at。
- 现有表不改(会话沙箱路径由 `conv-{id}` 规则派生,无需加列)。

### 3.6 前端(Vue 3 + Element Plus)

- `views/Skills.vue` 独立技能页:仓库浏览+搜索 / 已安装列表 / 安装、卸载操作;配套 `services/skills.ts`、路由项、i18n 中英文。
- 会话页制品面板:列表 + 下载。
- 文件与技能工具调用(`read_file`/`edit_file`/`save_artifact` 等)沿用现有 `tool_call` 事件展示,无需大改。

## 4. 数据流

- **安装**:UI → `POST /api/skills/install` → GitHub 定位目录 → 逐文件下载 → MinIO(临时前缀→正式)+ PG 清单 → 物化缓存版本失效 → 返回元数据 → UI 刷新。
- **会话首轮**:`astream(user 上下文)` → 工厂按 user_id 取/建 agent(必要时重新物化)→ system prompt 注入工作目录/技能库/制品指引。
- **对话**(渐进式披露):SkillsMiddleware 扫描 `/skills/` → 全部已装技能 name+description 进 system prompt → 模型匹配任务 → `read_file("/skills/{name}/SKILL.md", limit=1000)` → 在沙箱用 `ls/glob/grep/read_file/write_file/edit_file` 干活(可引用兄弟会话成果)→ 成品 `save_artifact` → 事件流照常透传。
- **漫游**:任何设备登录同一账号 → 同一 user_id → 同一沙箱/技能/制品/对话。

## 5. 错误处理

| 场景 | 处理 |
|---|---|
| GitHub API 失败/限流 | registry TTL 缓存降级返回旧值;无缓存返回结构化错误,UI 可重试 |
| SKILL.md 解析失败/名称不合规 | 安装时校验(`^[a-z0-9-]+$` 且与目录名一致),不合格拒绝入库;运行时 deepagents warn+skip 兜底 |
| 安装中途失败 | 临时前缀 + 成功后才写清单;失败清理临时对象 |
| MinIO 不可用 | 安装/保存制品返回结构化错误;物化失败该用户 agent 降级无 skills 运行,不阻塞对话 |
| 物化一致性 | PG 清单版本比对:未变用缓存,变了重同步,卸载即失效 |
| 制品保存失败 | 工具返回错误消息,模型自纠;超上限拒绝并提示 |
| 沙箱目录缺失 | 首轮消息惰性创建 |
| 模型越界路径 | `virtual_mode=True` 拦截(`..`/绝对路径),工具报错自纠 |

## 6. 安全边界

- **多用户隔离**(最重要):沙箱、技能物化缓存、MinIO 前缀全部按 user_id 分隔;不同用户 agent 是不同 backend 实例;所有新接口挂现有鉴权,资源查询强制 user_id 过滤。
- **`/skills/` 只读**:v1 以 system prompt 声明约束,后续换只读 backend 加固(技术债)。
- **提示注入**:SKILL.md 是第三方提示词,与 Claude Code 装第三方技能同级风险;安装界面展示 description/license 供人工判断,后续可加来源白名单。
- **下载防护**:单文件 10MB / 单技能 200 文件 / 跳过软链;PG 名称正则校验;MinIO 前缀操作,无本地路径拼接。
- **凭据**:GitHub token、MinIO access key 仅存后端 env;预签名 URL 1 小时时效。

## 7. 测试策略

- **单元**(pytest,fixture 伪造 GitHub API 与 MinIO):SkillService 列表/安装/卸载/上限/临时前缀清理;物化同步(版本变/不变);`save_artifact` 成功/源缺失/超大;harness 工厂按 user_id 缓存、物化失败降级。
- **集成**:fixture 技能全链路——安装(假仓库)→ 物化 → 断言 skill 元数据注入 system prompt → 沙箱文件读写 → 越界拒绝 → `save_artifact` → PG/MinIO 断言 → 制品列表/下载(预签名 URL 可访问)。
- **前端**:`vue-tsc` 通过;技能页/制品面板手工验收(无组件测试基建,不为此新引)。
- **回归**:user_id 缺失/旧会话(无 skill 场景)走原路径不炸。

## 8. 关键技术决策记录

| 决策 | 理由 |
|---|---|
| 用 `create_deep_agent(skills=, backend=)` 官方参数 + `CompositeBackend` 路由 | 官方路径自定义代码最少;deepagents 文档有同型示例;手动组装 middleware 会与内建 FilesystemMiddleware 按名冲突 |
| 沙箱=服务器真实目录,不放 MinIO | read/edit/glob/grep 在对象存储上延迟高、语义别扭;MinIO 只承载成果 |
| backend root=用户根而非会话子目录 | 跨会话成果互见,兑现"每用户一沙箱"的选择 |
| skills 运行时物化而非 MinIO 直读 | v1 简单可靠;SkillsMiddleware 只需 ls+download,后续做 MinIO 版 backend 工作量可控 |
| checkpoint 留 SQLite(单实例) | 半年内单实例部署,状态在服务器即可漫游;迁 PostgresSaver 列入多副本前技术债 |
| 安装走 GitHub 逐文件 API 而非 tarball | httpx 已有依赖,无解包代码,天然支持 token/代理 |
| 每用户一沙箱(而非每会话) | 跨会话协作与配额管理最自然;会话子目录提供逻辑分区 |
| 实现期首个验证点 | CompositeBackend 路由是否剥离 `/skills/` 前缀再交给子 backend,直接影响 SkillsMiddleware sources 的写法;实现第一步先写冒烟测试钉住该行为 |

## 9. 新增依赖

- 后端:`minio`(Python SDK)。
- 前端:无新增。

## 10. 技术债与后续路线(明确不在本期)

1. checkpoint SQLite → PostgresSaver(多副本前必须)
2. 知识库 ChromaDB → pgvector
3. MemoryMiddleware + PostgresStore(记忆云端化)
4. MCP 配置云端化
5. `/skills/` 只读 backend 加固
6. MinIO 直读 SkillsBackend(免物化)
7. 沙箱配额统计与清理策略
8. 技能来源白名单 / 审核机制
