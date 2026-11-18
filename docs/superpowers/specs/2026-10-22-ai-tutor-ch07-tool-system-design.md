# AI 伴学系统 · 第七章(工具系统:注册中心 · JSON Schema 校验 · 权限 · 执行引擎 · 审计 · MCP · 建单确认流)设计

日期:2026-10-22
状态:brainstorm 逐节通过,待用户复审 spec
落地位置:`potry-ai-agent/`(延续 Ch01–Ch06,就地扩展)
章节编号说明:需求原文要求留痕 `dev-notes/ch08.md`;仓库实际下一章为 Ch07,经用户确认**记为 Ch07**,留痕写 `dev-notes/ch07.md`。

## 1. 目标与范围

把 Ch02 以来"几个写死的内置工具 + 简易 ToolRegistry"升级为**即插即用的工具系统**:统一工具表、JSON Schema 校验、读写权限门、统一执行引擎、全量审计、两个独立 MCP Server 接入、写操作 `create_ticket` 的 LangGraph interrupt 人工确认流。

本章要做:

1. **工具注册中心**:内置 / MCP 工具统一登记"名称 + 用途 + JSON Schema";内置插件热加载,MCP 工具按 TTL 动态发现;新增工具不改核心代码、不重启客服服务。
2. **参数校验**:执行前统一 JSON Schema 校验;失败包成工具结果回灌模型,不抛异常。
3. **权限控制**:只读 / 写两类;写操作由执行引擎把门,`create_ticket` 必须经前端确认;外部 MCP 工具的权限只认本侧规则。
4. **执行引擎**:统一超时、重试、错误分诊、结果格式化;只读暂时性故障才重试,写操作不自动重试,业务空结果不重试。
5. **审计**:`tool_audit_logs` 记录每次调用(含校验拦下、权限拒绝);审计失败不阻断工具执行。
6. **MCP 接入**:自建诗词档案 MCP(9101)与判定/纠错 MCP(9102),Streamable HTTP,独立进程,mock 数据;客服侧用 `MultiServerMCPClient` 多 Server 接入。
7. **建单确认流**:`create_ticket` 先校验信息完整性,缺问题描述就追问;发起后 `interrupt` 推工单预览,前端确认/取消,确认落 `tickets` 表并返回工单号,取消记 `permission_denied` 审计;投诉页原按钮路径不动。

### 非目标(需求明确排除)

- **Skill 机制**不落代码;
- 不接仓储等更多外部系统,两个业务 MCP 足够;
- 不改旧 `/agent/chat` 单轮路径的工具行为(它保留自己的 `ToolRegistry`);
- 不做工具级 RBAC、多租户、审计报表。

### 术语映射(需求原文为客服模板,经用户确认映射为诗词域)

| 客服模板 | Ch07 落地 |
|---|---|
| 物流 MCP / 查物流轨迹 | **诗词档案 MCP**(9101):`poem_archive_lookup` / `poet_archive_lookup` |
| 售后 MCP / 查在保、查退货进度 | **判定与纠错 MCP**(9102):`judgement_status_lookup` / `correction_progress_lookup` |
| `query_logistics` 从清单下线 | 内置 `query_poem` 从**主力 Agent 工具清单**下线,由档案 MCP 接管;旧 `/agent/chat` 路径不动 |
| `create_ticket` / tickets 表 | 内置写工具 `create_ticket`,落新 `tickets` 表;类型:内容纠错 / 功能异常 / 其他 |
| 第 5 章投诉流程按钮建单 | 保持 `/agent/feedback` 原路;`submit_feedback` 从 Agent 清单移除,写操作只剩 `create_ticket` |

### 需求→设计对照

| 需求 | 落地 |
|---|---|
| 1 注册中心 / 三样信息 / 内置登记 / MCP 动态发现 / 不改核心不重启 | §3(**ToolSpec、热加载插件、MCP TTL 发现、重名规则**) |
| 2 JSON Schema 校验 / 错误回灌 | §4(**校验时机、错误结果形状**)、§5 |
| 3 只读写两类 / 写操作把门 / create_ticket 确认 / 外部声明不可信 | §6(**权限策略、双层门**) |
| 4 统一执行 / 超时重试 / 错误分诊 / 结果格式化 / 写不重试 | §5 |
| 5 审计表 / 含拦截与拒绝 / 不挂外键 / 失败不阻断 | §7 |
| 6 两个 MCP Server / 独立进程 / mock 数据 / 多 Server 接入 / 下线 query_poem | §8 |
| 7 建单确认流 / 追问补齐 / interrupt / 预览卡 / 确认落库 / 取消失败审计 / 旧按钮不动 | §9、§10 |
| 验收 1–6 | §13 |

## 2. 技术栈与依赖(用户定死)

| 项 | 结论 |
|---|---|
| MCP Server | 官方 Python SDK `mcp==1.30.0`,`FastMCP`,`transport="streamable-http"`,`stateless_http=True`,`json_response=True` |
| MCP Client | `langchain-mcp-adapters==0.3.2` 的 `MultiServerMCPClient`,按 `server_name` 逐 Server 取工具 |
| JSON Schema | `jsonschema==4.26.0` |
| 编排 | 延用 LangGraph 1.2.16;`interrupt()` + `Command(resume=...)`(Context7 已核) |
| 存储 | 延用 MySQL / SQLAlchemy;新表 `tickets` / `tool_audit_logs` |

**版本约束与决策(用户拍板"最新版组合")**:`langchain-mcp-adapters 0.3.2` 要求 `mcp<2.0`,故不能用 mcp 2.x;选 `mcp 1.30.0`。该组合会把 `pydantic` 从 2.9.2 解析到 2.14.x,安装后必须跑全量回归;若回归失败,停下报告,不自行换栈。

**Context7 已核对(2026-10-22):**
- `MultiServerMCPClient({"name": {"transport": "streamable_http" | "http", "url": ...}})`;`await client.get_tools(server_name=...)`;工具为 `StructuredTool`,其 `args_schema` 来自 MCP `inputSchema`。
- `FastMCP` v1:`mcp = FastMCP(name, host=..., port=..., stateless_http=True, json_response=True); @mcp.tool(); mcp.run(transport="streamable-http")`(安装后以实际签名复核)。
- LangGraph:`from langgraph.types import interrupt, Command`;`graph.ainvoke(Command(resume=...), config={"configurable":{"thread_id":...}})`;恢复时**从节点开头重新执行**,节点内 `interrupt` 之前不得有副作用。

## 3. 工具注册中心

### 3.1 统一工具表

新包 `tool_system/`:

```text
tool_system/
  spec.py          ToolSpec / Permission / ToolInvocation
  catalog.py       ToolCatalog: 内置插件 + MCP,统一 get_tools / execute / 权限查询
  engine.py        ToolEngine: 校验 → 权限 → 超时/重试 → 格式化 → 审计
  formatter.py     result_fields / enum_labels / JSON 不转义
  mcp_provider.py  MultiServerMCPClient 封装、逐 Server 发现、TTL 合并
  plugins.py       tools/extensions/*.py 热加载与卸载
  audit.py         审计写入(可注入 AppStorage)
```

`ToolSpec` 字段:

| 字段 | 说明 |
|---|---|
| `name` | 工具名(全局唯一) |
| `description` | 用途描述(给模型) |
| `input_schema` | JSON Schema object |
| `source` | `builtin` 或 `mcp:<server>` |
| `permission` | `read` / `write` |
| `requires_confirmation` | 写操作是否为 `true` |
| `handler` | LangChain `BaseTool`(内置或适配后的 MCP 工具) |
| `timeout` / `max_retries` | 可选覆盖全局配置 |
| `result_fields` | 结果只保留的字段(可选) |
| `enum_labels` | 内部码→中文(可选) |

### 3.2 内置工具热加载

- 目录 `tools/extensions/`,模块暴露 `register(catalog: ToolCatalog) -> None`,内部调用 `catalog.register_builtin(tool, permission="read")`。
- `ToolCatalog.get_tools()` 每次调用前扫描目录:
  - 新文件(路径 + mtime 未见过)→ `importlib.util.spec_from_file_location` 载入,执行 `register`;模块名唯一(`plugin_<stem>_<mtime>`),避免缓存冲突;
  - 已见过但 mtime 变化 → 以新模块名重载,先注销该插件旧工具再登记新工具;
  - 文件删除 → 注销该插件登记的全部工具;
  - 导入/注册失败 → 打印 `[tools] plugin fail <file>: <err[:200]>`,跳过,不影响其他工具。
- 扫描与加载包在 `asyncio.Lock` 内,避免并发请求重复导入。
- 样例插件:`tools/extensions/poem_length.py`,工具 `poem_length(text: str)`,返回字数,只读;用于验收 1。

### 3.3 MCP 动态发现

- 配置两个 Server(§8),`mcp_provider` 持有 `MultiServerMCPClient`。
- `refresh(force=False)`:
  - TTL `MCP_TOOL_REFRESH_SECONDS=5`;
  - 逐 Server `await client.get_tools(server_name=...)`;
  - 每个工具构造 `ToolSpec`:name/description/inputSchema 来自适配器;source=`mcp:<server>`;permission 由本侧 `MCP_SERVER_POLICIES` 决定;
  - 某 Server 失败 → 打印 `[mcp] <server> unreachable: ...`,保留该 Server 上一次成功清单;从未成功则该 Server 本次无工具;
  - 与内置工具重名 → 跳过 MCP 工具并打印 `[mcp] skip duplicate <name>`,内置优先。
- 这样验收 3 只需重启对应 MCP Server;客服侧下一轮(≤5 秒)自动看到新工具,不重启客服服务。

### 3.4 主力 Agent 工具清单(Ch07 后)

- 内置:`query_poet`、`query_dynasty_poems`、`create_ticket`、`poem_length`(插件样例)。
- MCP:`poem_archive_lookup`、`poet_archive_lookup`(档案);`judgement_status_lookup`、`correction_progress_lookup`(判定/纠错)。
- 下线:`query_poem`(档案 MCP 接管)、`submit_feedback`(写操作只留 `create_ticket`;投诉页按钮仍走 `/agent/feedback`)。
- 旧 `/agent/chat` 的 `ToolRegistry` 保持 Ch01–Ch03 三工具不变。

## 4. 参数校验

- 执行前 `jsonschema.validate(instance=args, schema=spec.input_schema)`;支持 `type`、`required`、`enum`、`minLength`、`minimum/maximum`、`additionalProperties` 等标准关键字。
- 失败返回结构化结果(不抛异常):
  ```json
  {
    "ok": false,
    "error_type": "invalid_arguments",
    "message": "参数校验失败: description 不能为空",
    "details": ["description: 'description' is a required property"]
  }
  ```
- `details` 最多取前 5 条,避免 ToolMessage 过长。
- 审计状态 `validation_error`;`retry_count=0`;不执行 handler。
- `create_ticket` 若参数不合法(如缺 description),`should_continue` 不进确认节点,直接走 `tool_node` 让引擎回校验错误,Agent 据此追问用户。

## 5. 执行引擎

`ToolEngine.execute(spec, args, *, session_id, tool_call_id, approved=False)` 固定流程:

```text
1. Schema 校验 → 失败：审计 validation_error，返回错误结果
2. 权限门：permission=="write" 且 approved is not True
           → 审计 permission_denied，返回 {"ok":false,"error_type":"permission_denied",...}
3. 执行：asyncio.wait_for(handler.ainvoke(args), timeout=spec.timeout or TOOL_TIMEOUT_SECONDS)
4. 失败重试：
   - 只读工具 + 暂时性故障（TimeoutError/ConnectionError/OSError/HTTP 传输错误/消息含
     "timeout"/"connection"/"temporarily"/"unavailable"）→ 最多 TOOL_MAX_RETRIES 次；
   - 写工具一律不重试；
   - 业务空结果（ok=true/found=false）不重试；
   - 参数类错误不重试。
5. 结果格式化：dict/tuple/文本归一 → result_fields 裁剪 → enum_labels 翻译 → JSON ensure_ascii=False
6. 审计：success / error / timeout；记录实际 retry_count 与 duration_ms
7. 返回格式化 dict（永不抛异常）
```

- 结果形状:
  - 成功:`{"ok": true, "found": true, "data": {...}, "summary": "..."}`(具体字段按工具);
  - 业务空:`{"ok": true, "found": false, "message": "未查到..."}`;
  - 故障:`{"ok": false, "error_type": "fault" | "timeout", "message": "..."}`。
- **写操作超时**:`retry_count=0`,状态 `timeout`;不自动重试,避免重复落库。
- `tool_node` 负责把结果包成 `ToolMessage`;引擎本身不碰 LangChain 消息层,便于单测。

## 6. 权限控制

- 内置注册时声明:`create_ticket` = `write` + `requires_confirmation=True`;其余内置 = `read`。
- MCP 权限只认本侧:

  ```python
  MCP_SERVER_POLICIES = {
      "poetry_archive": "read",
      "judgement": "read",
  }
  ```

  不在策略表中的 Server 一律按 `write` + 需确认处理(默认拒绝写);Server 自己声明的 `readOnlyHint`/annotations **不参与判定**。
- **双层门**:
  1. `should_continue` 识别 `requires_confirmation` → 进 `ticket_confirm` 节点,
     `interrupt` 等前端确认;
  2. 引擎再次检查 `approved`;即使模型绕过图路径直接调 `create_ticket`,没有确认也返回 `permission_denied`。
- `PER_TURN_RESET` 增加 `ticket_confirmed=None` / `ticket_preview=None`,确认态不跨轮复用。

## 7. 审计

`tool_audit_logs`(AppBase,无外键):

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | int PK auto | |
| `session_id` | varchar(64) null | 所属会话 |
| `tool_call_id` | varchar(64) null | 模型给出的 tool_call id |
| `tool_name` | varchar(128) | |
| `source` | varchar(64) | `builtin` / `mcp:<server>` |
| `arguments` | text | JSON,ensure_ascii=False |
| `result_summary` | text | 格式化结果前 300 字 |
| `status` | varchar(32) | success / error / timeout / validation_error / permission_denied |
| `error` | text null | 错误说明 |
| `retry_count` | int default 0 | 实际重试次数 |
| `duration_ms` | int | 从校验开始到返回 |
| `created_at` | datetime | |

- 校验拦下、权限拒绝、用户取消建单**同样落审计**;未知工具名也落一条 `error`(source=`unknown`);
- 审计写入独立 session + try/except;失败打印 `[audit] fail: ...`,不影响工具结果;
- 不挂外键,会话删除不级联。

## 8. MCP Server

### 8.1 诗词档案 MCP(9101)

文件 `mcp_servers/poetry_archive_server.py`:

- `FastMCP("poetry-archive", host="127.0.0.1", port=9101, stateless_http=True, json_response=True)`;
- 工具:
  - `poem_archive_lookup(title: str = "", poet: str = "") -> dict`:
    从内置的 5 首诗词池(静夜思/春望/登鹳雀楼/江雪/山居秋暝)按标题或诗人匹配;匹配不到随机取一首;
    返回 `{"ok": true, "found": true, "archive": {title, writer, dynasty, content, translation, archive_status}}`;
  - `poet_archive_lookup(name: str) -> dict`:诗人档案(姓名/朝代/字号/简介),同样 mock。
- 数据每次调用随机扰动(`archive_status` 在 `在库/整理中` 中随机),不接 MySQL、不建表。

### 8.2 判定与纠错 MCP(9102)

文件 `mcp_servers/judgement_server.py`:

- `FastMCP("judgement", host="127.0.0.1", port=9102, stateless_http=True, json_response=True)`;
- 工具:
  - `judgement_status_lookup(title: str) -> dict`:返回最近一次判定(类型 meter/verify、结果 pass/fail、结论、日期);
  - `correction_progress_lookup(ticket_no: str) -> dict`:返回纠错单进度(received/reviewing/done、更新时间、处理说明)。
- 全部 mock 随机;不落库。

### 8.3 客户端接入

`WorkflowDeps` 持有 `ToolCatalog`,其 `McpProvider` 配置:

```python
{
  "poetry_archive": {"transport": "streamable_http", "url": settings.mcp_poetry_archive_url},
  "judgement":      {"transport": "streamable_http", "url": settings.mcp_judgement_url},
}
```

- Server 未启动:客服照常起,日志 `[mcp] ... unreachable`,只影响对应工具;
- 新增/修改工具:重启对应 Server,TTL 到期后自动出现在工具表,客服服务不重启。

### 8.4 与意图路由的配合(关键)

MCP 工具与 `create_ticket` 只有在**进了 Agent 的出口**才会被调用;必须避免被现有分流器截走:

- "帮我建个工单 / 提交纠错单 / 我要反馈问题" → 归 `other`(进 Agent,由 `create_ticket` 工具处理),**不得归 complaint**(complaint 走预设话术,不进 Agent);
- "查一下《静夜思》的诗库档案 / 诗人在诗库里的资料" → 归 `find_poem` / `find_poet`(业务类,进 Agent);
- "查一下我的判定记录 / 纠错单进度" → 归 `other` 或 `find_poem`(业务类,进 Agent);
- 在 `INTENT_PROMPT` 增补上述 few-shot,并用 Ch07 意图评估样例(≥8 条)跑真实模型验证;若误判,只调 Prompt,不改分流表。
- 知识类(poem_explain)仍走 RAG,不预检索 MCP;用户若要档案/记录,应按业务类问法表达。

## 9. 建工单确认流

### 9.1 数据与工具

`tickets` 表(AppBase):

| 列 | 说明 |
|---|---|
| `id` / `ticket_no` | `ticket_no = f"TK{id:06d}"`(落库后回填) |
| `userid` / `session_id` | 匿名用户 / 会话 |
| `ticket_type` | 内容纠错 / 功能异常 / 其他 |
| `description` | 问题描述 |
| `status` | submitted |
| `created_at` | |

内置工具 `create_ticket(ticket_type, description)`:

- JSON Schema:`ticket_type` 三选一枚举;`description` string,`minLength: 4`;
- 描述强调:**仅当用户明确要求建工单/提交纠错单时调用;信息不足先追问,不得编造**;
- 返回 `{"ok": true, "ticket_no": "TK000123", "ticket_id": 123}`。

### 9.2 图与 interrupt

State 新增:`ticket_confirmed: bool | None`、`ticket_preview: dict | None`;均进 `PER_TURN_RESET`。

`should_continue`(agent 后):

```text
无 tool_calls → log
有 requires_confirmation 且参数通过 Schema 校验 → ticket_confirm
其它 → tool_node（原有迭代/token 上限判定保留）
```

新节点 `ticket_confirm_node`:

```python
last = state["messages"][-1]
call = 第一个 requires_confirmation 的 tool_call
preview = {"ticketType": call.args["ticket_type"], "description": call.args["description"]}
decision = interrupt({"action": "confirm_ticket", "preview": preview, "toolCallId": call["id"]})
return {"ticket_confirmed": bool(decision and decision.get("confirmed")),
        "ticket_preview": preview}
```

- `interrupt` 前**无副作用**;恢复时从节点开头重跑,只重新计算预览并读取 resume 值;
- 恢复后边到 `tool_node`;引擎根据 `ticket_confirmed` 执行或拒绝;
- 取消时工具结果:`{"ok": false, "error_type": "permission_denied", "message": "用户取消建单"}`,
  审计 `permission_denied`;Agent 据此回复"已取消"。

### 9.3 HTTP / SSE

`POST /agent/workflow`(原接口):

- 图返回 `__interrupt__` 时:
  - 发 `action` 帧:`{"action":"confirm_ticket","preview":{"ticketType":...,"description":...},"toolCallId":...}`;
  - `done` 帧:`{"sessionId":..., "status":"awaiting_confirmation"}`;
- 若有待确认 interrupt 时又收到普通消息 → 409 `{"message":"请先确认或取消当前工单"}`。

`POST /agent/workflow/resume`(新增):

```json
{"sessionId": "...", "confirmed": true}
```

- 无待确认 interrupt → 409;
- `await _workflow.ainvoke(Command(resume={"confirmed": req.confirmed}), config=thread_id)`;
- 输出与 `/agent/workflow` 相同 SSE 帧序(meta → trace → tool_status* → token* → done);
- 确认成功后回复文本含工单号;取消后回复"已取消"。

### 9.4 前端(Vibe Coding 例外)

- 收到 `action: confirm_ticket` → 在气泡下渲染预览卡:
  - 标题「工单预览」;两行:工单类型、问题描述;
  - 按钮「确认提交」「取消」;
- 确认 → `POST /agent/workflow/resume {sessionId, confirmed:true}`,复用 SSE 解析,新建助手气泡接收回复;
- 取消 → `confirmed:false`,同样接收回复;
- 等待确认期间禁用输入框与发送;完成后恢复;
- 旧「转人工」「提交反馈」、诗词卡片、纠错单表单保持不变。

## 10. 与既有代码的接入点

| 文件 | 改动 |
|---|---|
| `tool_system/*` | 新建(§3) |
| `tools/extensions/poem_length.py` | 新建样例插件 |
| `mcp_servers/*` | 新建两个 Server |
| `app_storage.py` | 新增 `Ticket` / `ToolAuditLog` 模型 + `add_ticket` / `add_tool_audit` |
| `config.py` | 新增 MCP URL / 刷新 TTL 配置 |
| `workflow/deps.py` | `registry` → `tools: ToolCatalog` |
| `workflow/state.py` | 新增 `ticket_confirmed` / `ticket_preview`,加入 `PER_TURN_RESET` |
| `workflow/agent_react.py` | `await deps.tools.get_tools()` 绑定;`tool_node` 走 `deps.tools.execute` |
| `workflow/nodes.py` | 新增 `ticket_confirm_node` |
| `workflow/graph.py` | agent 条件边增加 `ticket_confirm`;`ticket_confirm → tool_node` |
| `main.py` | 装配 ToolCatalog/MCP;`/agent/workflow` 处理 interrupt;新增 `/agent/workflow/resume` |
| `static/chat.html` | 工单预览卡 + resume 调用(Vibe Coding) |
| `requirements.txt` | mcp / adapters / jsonschema;pydantic 版本随解析更新 |

旧 `/agent/chat` 与 `ChatService` 不动;`ToolRegistry` 保留给旧路径。

## 11. 错误处理与降级

| 场景 | 处理 |
|---|---|
| MCP Server 未启动 | 告警,保留上次清单;内置工具照常;对应问题模型如实说查不到 |
| MCP 返回错误 | 引擎归一为 `fault`/`not_found`,审计记录 |
| Schema 不合法 | 返回 `invalid_arguments` + details,审计 |
| 写操作未确认 | `permission_denied`,审计 |
| 用户取消建单 | `permission_denied`,审计,Agent 回"已取消" |
| 读工具超时 | 重试 `TOOL_MAX_RETRIES` 次,最终 `timeout`,审计 retry_count |
| 写工具超时 | 不重试,`timeout`,审计 retry_count=0 |
| 审计写失败 | 只告警,不影响工具结果 |
| 插件导入失败 | 只告警,跳过该插件 |
| 待确认时收到新消息 | 409,前端保持等待确认 |
| `/agent/workflow/resume` 无待确认 | 409 |

## 12. 测试策略

**可单测(TDD)**:

- `ToolCatalog`:内置注册、JSON Schema 生成、插件新增/修改/删除热加载、重名跳过、MCP 失败保留旧清单;
- `ToolEngine`:校验失败、权限拒绝、只读超时重试、写超时零重试、业务空不重试、结果字段裁剪/枚举翻译/中文不转义、审计失败不阻断;
- 审计:`tool_audit_logs` 各状态落行、无外键、失败不抛;
- 图:`interrupt` 确认 → `tickets` 落行 + 审计 success;取消 → 无票 + 审计 permission_denied;`ticket_confirmed` 跨轮重置;待确认时新消息 409;
- API:interrupt 帧、resume 帧序、无待确认 409;
- MCP Provider:假 Client 的逐 Server 归属、TTL 刷新、重名。

**纯 Prompt / 数据类**:`create_ticket` 的"何时调用/如何追问"用标注样例跑真实模型验证(≥6 条:明确建单/信息不全/只是抱怨/只是问诗/取消/重复建单),Prompt 不放宽断言。

**端到端(验收 1–6)**:见 §13;前端卡片 Vibe Coding 人工验证。

## 13. 验收策略(诗词域)

1. **插件即插即用**:新增 `tools/extensions/poem_length.py`(已内置样例);再在运行中新增一个插件文件(如 `poem_reverse.py`),不重启 API,追问对应问题,Agent 调新工具;日志/审计有记录。
2. **两个 MCP Server 被真实调用**:分别启动 9101/9102;问「查一下《静夜思》的诗库档案」→ `poem_archive_lookup`;问「查一下《春望》的判定记录」→ `judgement_status_lookup`;回答含 MCP 返回的数据,审计 source=`mcp:*`。问句须先通过意图路由评估(§8.4),确认进 Agent 而非 RAG/预设话术。
3. **MCP 侧新增工具**:在 `poetry_archive_server.py` 增加 `poem_line_count`,只重启 9101;客服不重启,≤5 秒后问对应问题,Agent 用上新工具。
4. **建单确认**:说「帮我建个工单」但缺描述 → Agent 追问;补齐后出现预览卡 → 确认 → `tickets` 新增一行,回复带 `TKxxxxxx`;审计 success。
5. **取消**:同样到预览 → 取消 → `tickets` 无新行,`tool_audit_logs` 该 `create_ticket` 状态 `permission_denied`。
6. **超时与重试**:验收脚本用慢读工具(超时)→ 审计 `timeout`、retry_count=TOOL_MAX_RETRIES;慢写工具 → `timeout`、retry_count=0;回复有兜底说明。

## 14. 已确认决策与偏差留痕

| 决策点 | 结论 |
|---|---|
| 章节编号 | 需求写 `dev-notes/ch08.md`;仓库下一章为 Ch07,用户确认记为 **Ch07 / dev-notes/ch07.md** |
| 领域映射 | 物流→诗词档案 MCP;售后→判定与纠错 MCP;create_ticket→建纠错/反馈工单(用户确认) |
| MCP 接管 | 档案 MCP 接管内置 `query_poem`;`query_poet`/`query_dynasty_poems` 仍内置(用户确认) |
| submit_feedback | 从 Agent 清单移除;投诉页按钮仍走 `/agent/feedback`(用户确认) |
| 工单类型 | 内容纠错 / 功能异常 / 其他(用户确认) |
| resume 接口 | 新增 `POST /agent/workflow/resume`(用户确认) |
| 依赖组合 | `mcp 1.30.0` + `langchain-mcp-adapters 0.3.2` + `jsonschema 4.26.0`;pydantic 随解析升级,必须全量回归(用户确认"最新版组合") |
| 确认机制 | LangGraph `interrupt` + `Command(resume=...)`;专用 `ticket_confirm` 节点,interrupt 前无副作用 |
| 建单路由 | "帮我建个工单"等明确建单请求归 `other`(进 Agent),不得归 complaint;需补 INTENT_PROMPT few-shot + 评估样例 |
| 权限默认 | 两个自建 MCP Server 只读;未知 Server 默认写 + 需确认;MCP 声明不作为权限依据 |
| 审计失败 | 只告警,不影响工具执行 |
| 前端卡片 | Vibe Coding 例外,不做 brainstorm/TDD/code review |

## 15. 模块划分

| 模块 | 动作 | 职责 |
|---|---|---|
| `tool_system/spec.py` | Create | ToolSpec / 权限 / 调用上下文 |
| `tool_system/plugins.py` | Create | `tools/extensions` 热加载/卸载 |
| `tool_system/mcp_provider.py` | Create | 多 Server 发现、TTL、来源归属 |
| `tool_system/catalog.py` | Create | 统一工具表、`get_tools`、`execute`、权限/预览查询 |
| `tool_system/engine.py` | Create | 校验、权限、超时重试、错误分诊 |
| `tool_system/formatter.py` | Create | 字段裁剪、枚举翻译、JSON 序列化 |
| `tool_system/audit.py` | Create | 审计写入(注入 AppStorage) |
| `tools/extensions/poem_length.py` | Create | 样例只读插件 |
| `mcp_servers/poetry_archive_server.py` | Create | 档案 MCP(9101) |
| `mcp_servers/judgement_server.py` | Create | 判定/纠错 MCP(9102) |
| `tools/ticket_tool.py` | Create | `create_ticket` 内置写工具 |
| `app_storage.py` | Modify | `Ticket` / `ToolAuditLog` + 写入方法 |
| `config.py` | Modify | MCP URL / 刷新 TTL |
| `workflow/state.py` | Modify | `ticket_confirmed` / `ticket_preview` |
| `workflow/deps.py` | Modify | 注入 `ToolCatalog` |
| `workflow/agent_react.py` | Modify | 异步取工具、引擎执行、确认参数 |
| `workflow/nodes.py` | Modify | `ticket_confirm_node` |
| `workflow/graph.py` | Modify | 确认节点与条件边 |
| `main.py` | Modify | 装配、interrupt 帧、resume 接口 |
| `static/chat.html` | Modify | 工单预览卡与 resume |
| `tests/test_tool_*.py`、`tests/test_ticket_flow.py`、`tests/test_mcp_*.py` | Create | §12 单测 |
| `evals/demo_ch07.py`、`evals/tool_audit_probe.py` | Create | 验收脚本 |
