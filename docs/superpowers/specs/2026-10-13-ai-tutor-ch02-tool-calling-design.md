# AI 伴学系统 · 第二章(Function Calling 查数据)设计

日期:2026-10-13
状态:已定稿(brainstorm 四节设计逐节通过)
落地位置:`potry-ai-agent/`(延续 Ch01,就地扩展)

## 1. 目标与范围

给现有聊天装上查数据能力:用 LangChain `@tool` 装饰器定义业务工具,模型经 Function Calling 自己决定调什么,工具链长在客服聊天本身——用户在聊天页问一句即触发。

1. 项目基建搭正式(Docker MySQL + SQLAlchemy);
2. `@tool` 装饰器定义业务工具;
3. 工具基础设施:注册管理、参数 Schema 校验、执行错误处理、超时重试,工具结果回灌给模型组织回答;
4. 工具链接进现有 SSE 流式聊天入口:「模型定工具 → 执行 → 回灌收敛」,最终回答逐 token 流式,工具执行段先推状态帧;聊天记录(含工具调用与结果)落 conversations/messages 表;聊天页气泡带工具轨迹小徽章;
5. 只做单轮调用:模型调一次工具就收敛。

### 非目标(本章不做)

- 多轮自动循环 Agent Loop;
- 向量检索、RAG;
- 工具写操作(全部只读查询)。

### 验收标准(诗词域,经用户确认把客服域换为本项目诗词域)

1. 浏览器打开聊天页,问「《静夜思》是谁写的」,能看到模型选中工具(气泡带工具徽章)并按返回结果作答;
2. 问「李白是什么样的诗人」(或类似问法),`query_poet` 查得到并作答;
3. 换个含糊指代的说法问(如「那首讲月亮的叫啥」),确认关键词查表查不出来——这个漏召回是预期结果,记下来留给下一步升级。

## 2. 技术选型(用户定死,不得自行更换)

- Python + FastAPI + LangChain(`@tool` 装饰器)+ SQLAlchemy + MySQL(Docker 起);
- 模型:沿用 Ch01 OpenAI 协议直连(DeepSeek,`.env` 配置);
- 编排:方案 A「手动单轮编排」——`bind_tools` 两次调用(非流式取 `tool_calls` → 工具执行回灌 → `astream` 流式收敛),无 LangGraph 依赖(方案 B 引入新依赖且与"单轮"拧着,排除;方案 C 违背 @tool 技术栈,排除);
- 数据:**复用已有诗词表**——现有数据在 H2 文件库(`./data/shi-pick`,`poem.potry` / `poem.writer`,初始化脚本 `potry-service/src/main/resources/sql/poemmax-h2.sql`),经用户确认:**Docker 起 MySQL,把 poemmax-h2.sql 导入**(H2 语法差异手工修),表名字段与 Java 侧保持一致,不新建诗词表。

## 3. 架构与数据流

模块划分(`potry-ai-agent/` 内,延续 Ch01 扁平风格):

| 模块 | 职责 | 依赖 |
|---|---|---|
| `tools/registry.py` | 工具注册表:登记 `@tool` 工具,统一执行入口(Schema 校验、超时、重试、错误包装) | langchain-core |
| `tools/poetry_tools.py` | 三个业务工具,`@tool` 定义,查 MySQL | sqlalchemy |
| `db.py` | SQLAlchemy engine/session(连 MySQL),`Potry`/`Writer` 表映射(只读) | sqlalchemy + pymysql |
| `storage.py` | conversations/messages 表模型 + 写入(repo) | sqlalchemy |
| `chat_service.py` | 改造:单轮 Function Calling 编排 + 每轮落库 | langchain-openai |
| `prompts.py` | System Prompt 追加工具使用指引 | langchain-core |
| `main.py` | SSE 增加 `tool_status` 帧;路由与 Ch01 一致 | fastapi |

一次带工具调用的数据流:

```
POST /agent/chat {sessionId, message}
  → SSE: meta
  → LLM.bind_tools(工具集).ainvoke(历史+新消息)          ← 非流式,拿 tool_calls
  → 若无 tool_calls: 直接进入流式收敛(同 Ch01 路径)
  → 若有 tool_calls(单轮,只取第一个):
      SSE: tool_status {tool, status:"calling", args}
      → 工具注册表执行(校验→超时→重试→错误包装)
      SSE: tool_status {tool, status:"done"|"error", durationMs}
      → ToolMessage(结果 JSON)回灌进消息列表
  → 第二次调用 LLM.astream(...)                           ← 流式逐 token
  → SSE: token* → done
  → 本轮 messages(user / AIMessage(tool_calls) / ToolMessage / 最终 AIMessage)落 conversations/messages
```

单轮收敛语义:模型第二次调用若再发起 tool_calls,**不执行**、不循环,直接按已有上下文流式收敛回答(不做 Agent Loop)。

## 4. 工具基础设施

- **注册管理**:工具用 `@tool` 定义(签名 + docstring 生成 JSON Schema);`ToolRegistry.register()` 登记,`get_tools()` 返回列表给 `bind_tools`,`execute(name, args)` 统一执行;新增工具不动编排代码;
- **参数 Schema 校验**:执行前用工具 `args_schema`(Pydantic)校验入参,失败返回结构化错误(不抛崩),回灌给模型自行修正说法;
- **执行错误处理**:工具函数不吞异常;`execute()` 统一捕获包装为 `{"ok": false, "error": "..."}` 回灌;"查不到"是业务正常结果 `{"ok": true, "found": false}`,与执行失败区分;
- **超时重试**:每工具执行包 `asyncio.wait_for`(`TOOL_TIMEOUT_SECONDS`,默认 5s,.env 可配);失败重试 `TOOL_MAX_RETRIES` 次(默认 1),固定间隔不搞指数退避(YAGNI);仍失败才回灌错误;
- **结果回灌**:结果序列化 JSON 字符串进 `ToolMessage`(tool_call_id 对齐),随消息列表进第二次 LLM 调用。

## 5. 工具明细(查 MySQL 复用表)

| 工具 | 参数 | 返回(回灌 JSON) |
|---|---|---|
| `query_poem` | `keyword: str`(标题/作者/名句模糊匹配) | `{"ok":true,"found":true,"poem":{title,dynasty,writer,content,translation,...}}` |
| `query_poet` | `name: str` | 诗人信息(来自 `writer` 表)+ 代表作列表 |
| `query_dynasty_poems` | `dynasty: str` | 该朝代诗词标题列表(限条数,防回灌爆炸) |

## 6. 数据层与落库

**MySQL(Docker)**:
- `potry-ai-agent/docker-compose.yml` 起 MySQL 8(端口 3306,库名 `poem`,root 密码走 `.env` 不入库);
- `poemmax-h2.sql` 转导入 MySQL(H2 语法差异手工修:自增/引号/引擎),含存量数据,表结构与 Java 侧一致;
- `db.py`:`create_engine(MYSQL_URL)`,`Potry`/`Writer` 显式列映射(只读查询);连接串在 `.env` 的 `MYSQL_URL`。

**conversations / messages(新表,SQLAlchemy `create_all`)**:

| conversations | 类型 | 说明 |
|---|---|---|
| id | bigint PK auto | |
| session_id | varchar(64) idx | 对应 SSE 的 sessionId |
| created_at | datetime | |

| messages | 类型 | 说明 |
|---|---|---|
| id | bigint PK auto | |
| conversation_id | bigint FK | |
| role | varchar(16) | user / assistant / tool |
| content | text | assistant 为完整回答,tool 为结果 JSON |
| tool_name | varchar(64) null | 涉及的工具名 |
| tool_call_id | varchar(64) null | 对齐 tool_call 与结果 |
| tool_args | text null | 模型入参 JSON(追溯用) |
| created_at | datetime | |

每轮对话(含 tool_calls AIMessage、ToolMessage、最终 AIMessage)整体落 messages,可完整还原工具调用过程。Ch01 内存 `SessionStore` 保留不动(上下文裁剪继续用),落库是并行持久化。

## 7. SSE 契约(相对 Ch01 扩展)

| 事件 | data | 时机 |
|---|---|---|
| `meta` | `{"sessionId"}` | 流开始(同 Ch01) |
| `tool_status` | `{"tool","status":"calling"\|"done"\|"error","args":{},"durationMs"}` | 选定工具后推 calling;执行完成/失败再推一条 |
| `token` | `{"content"}` | 最终回答逐 token(同 Ch01) |
| `done` | `{"sessionId"}` | 正常结束(同 Ch01) |
| `error` | `{"message"}` | 中途失败(同 Ch01) |

## 8. Prompt 调整(`prompts.py`)

System Prompt 追加工具使用指引:查数据类问题(诗词出处/诗人/朝代)先用工具,拿到结果再回答;拿不准指代或查不到,如实说不确定,不编造(沿用 Ch01 约束);「青莲」人设不变。

## 9. 错误处理

- 工具执行失败/超时:回灌 `{"ok":false,"error"}`,`tool_status` 推 `error`,最终回答由模型基于失败信息组织(如"这会儿查不了");
- 上游 LLM 失败:沿用 Ch01(流前 502、流中 error 事件);
- MySQL 不可用:工具执行失败同上路径,服务本身不崩(连接懒建,查询时才失败);
- 日志不得打印 MySQL 密码、API key。

## 10. 测试与验证策略

- **TDD(可单测代码)**:工具注册表(注册/校验/超时/重试/错误包装)、三工具对测试库查询、编排单轮收敛(fake LLM 模拟 tool_calls → 断言 ToolMessage 回灌与落库)、SSE `tool_status` 事件序列;
- **评估样例(纯 Prompt/验收行为)**:验收 3 句 + 闲聊句不触发工具的负例,拿真实 DeepSeek 跑人工比对;
- **聊天页改造**:Vibe Coding(工具轨迹小徽章),不套 brainstorm/TDD/code review 流程。

## 11. 已确认的决策记录

| 决策点 | 结论 |
|---|---|
| 人设/领域 | 保持诗人「青莲」;工具不做客服域,做**本项目诗词域**(用户纠正:"工具搞错了不是客服域,而是本体的这个项目") |
| 工具集 | `query_poem` / `query_poet` / `query_dynasty_poems` |
| 业务数据 | 复用已有表(`poem.potry` / `poem.writer`) |
| H2 vs MySQL 冲突 | 停下确认后选「导入 MySQL」:Docker 起 MySQL,导入 `poemmax-h2.sql`(表名字段不变) |
| 漏召回验收句 | 含糊指代句(如「那首讲月亮的叫啥」),关键词查不到但语义上有所指 |
| 编排路线 | 方案 A:手动单轮编排(bind_tools 两次调用),不引 LangGraph |
| 验收句客服域表述 | 用户需求原文的「订单物流/退货/邮费」为客服域示例,经确认换为诗词域等价问句(见 §1) |
