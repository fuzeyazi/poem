# AI 伴学系统 · 第一章(纯对话)设计

日期:2026-10-13
状态:已定稿(brainstorm 通过,用户口头确认"没有调整,启动")
落地位置:`potry-ai-agent/`(就地扩展现有 FastAPI 骨架)

## 1. 目标与范围

第一章只跑通**纯对话**:

1. 对话接口支持多轮对话,SSE 流式输出、逐 token 推送;
2. Prompt 用 `PromptTemplate` 模板化,System Prompt 写清诗人角色设定和行为约束;
3. 多轮上下文做最简版:历史消息裁剪 + token 预算控制。

### 非目标(本章不做)

- 工具调用、Agent 循环;
- 售后描述结构化 JSON 提取(验收项之一,已被用户确认为笔误并删除);
- 持久化会话存储(Redis/DB)、鉴权、用户体系对接;
- LangGraph / checkpointer 等 Agent 框架。

### 验收标准

1. `curl` 调对话接口能看到流式回复(SSE 逐 token 推送);
2. 连续问两轮,第二轮能续上第一轮的上下文;
3. 后端验收通过后,用 Vibe Coding 方式做一个简单聊天页面(不套 brainstorm/TDD/code review 流程,用户描述效果、直接改)。

## 2. 技术选型(用户定死,不得自行更换)

- Python + FastAPI + LangChain;
- 模型接入直连上游,应用侧统一按 OpenAI 协议对待:地址、模型名、密钥全部放 `.env`,GPT / Claude / DeepSeek / Ollama 可切换;
- 本章实测上游:DeepSeek(OpenAI 兼容接口),密钥由用户提供、写入 `.env`,**不入库、不写进任何文档**;
- SSE 用 FastAPI 内置 `fastapi.sse.EventSourceResponse` + `ServerSentEvent`(经查证为官方推荐 POST + SSE 写法;`fastapi==0.115.0` 需升级);
- 流式与历史裁剪用 LangChain 一等 API:`ChatOpenAI.astream()`、`trim_messages`、`count_tokens_approximately`(均经 Context7 查证存在且为当前官方用法)。

实现路线:方案 A —— LangChain 惯用法全家桶(与"薄 LangChain 手拼流式"的方案 B 对比后选定,理由:官方一等 API、与 PromptTemplate 要求一致、后续章节可平滑升级)。

## 3. 架构与数据流

组件划分(`potry-ai-agent/` 内扁平模块):

| 模块 | 职责 | 依赖 |
|---|---|---|
| `config.py` | 从 `.env` 读配置:上游 base_url / model / api_key、历史 token 预算、温度 | python-dotenv |
| `prompts.py` | `PromptTemplate` 化的 System Prompt(诗人角色设定 + 行为约束),组装 `ChatPromptTemplate` | langchain-core |
| `memory.py` | `SessionStore`:内存 dict 按 sessionId 存 `BaseMessage` 列表;`trim_messages` 做历史裁剪 + token 预算 | langchain-core |
| `chat_service.py` | `ChatOpenAI` 工厂 + 流式生成管线(prompt → 裁剪 → astream) | langchain-openai |
| `main.py` | FastAPI 入口、SSE 路由、Nacos 注册(保留不动) | fastapi |

一次对话的数据流:

```
POST /agent/chat {sessionId?, message}
  → 取/建 sessionId,查 SessionStore 得历史
  → trim_messages(历史+新消息, token预算)         ← 裁剪发生在请求时,不改存储;新消息在裁剪输入内、保证保留
  → ChatPromptTemplate 渲染(System Prompt + 裁剪后的消息列表)
  → ChatOpenAI.astream() 逐 chunk
  → SSE: meta → token* → done                      ← 逐 token 推送
  → 本轮 user + assistant 完整消息落回 SessionStore
```

接口形态:把现有 `/agent/chat` 的 TODO stub **就地改造**为 SSE 流式端点(路径不变,gateway `lb://potry-ai-agent` 路由不用动;stub 无存量调用方)。

## 4. Prompt 设计

- `prompts.py` 中 `SYSTEM_PROMPT_TEMPLATE: PromptTemplate`:诗人角色设定(以诗人视角伴学)与行为约束(不越界、不编造出处、口吻一致等),预留少量模板变量(如学段/风格),第一章默认值即可;
- `build_chat_prompt()` 组装 `ChatPromptTemplate`:system 模板 + `MessagesPlaceholder("messages")`,其中 `messages` 即"历史 + 新消息"经 `trim_messages` 裁剪后的完整列表(裁剪策略保证最新用户消息必在内);
- System Prompt 不进历史存储,每轮由模板注入,天然被 `trim_messages` 保留。

## 5. 上下文管理(最简版)

- `SessionStore`:进程内 `dict[str, list[BaseMessage]]`,按 sessionId 存全量历史;服务重启即丢(接受);
- sessionId 由客户端传入;未传时服务端生成并在 SSE `meta` 事件返回;
- 裁剪:`trim_messages(messages, strategy="last", token_counter="count_tokens_approximately", max_tokens=HISTORY_MAX_TOKENS, start_on="human", end_on="human")`,预算从 `.env` 读(默认约 2000 token),**请求时裁剪、存储不动**;
- 防内存膨胀:每个会话存储消息数设上限(如 50 条),超出丢最旧。

## 6. 接口契约

`POST /agent/chat`(改造原 stub),请求体:

```json
{ "userId": "可选", "sessionId": "可选", "message": "必填" }
```

SSE 响应(`text/event-stream`):

| 事件 | data | 说明 |
|---|---|---|
| `meta` | `{"sessionId": "..."}` | 流开始,回传本次会话 id |
| `token` | `{"content": "..."}` | 逐 token(实际为上游流式 chunk)推送 |
| `done` | `{"sessionId": "..."}` | 流正常结束 |
| `error` | `{"message": "..."}` | 中途失败时推送,随后结束流 |

`/health` 保留不动。

## 7. 配置(.env,不入库)

```
LLM_BASE_URL=上游 OpenAI 协议地址(DeepSeek 兼容地址)
LLM_API_KEY=密钥(用户提供,仅存本地 .env)
LLM_MODEL=模型名(默认 deepseek-chat,可换)
HISTORY_MAX_TOKENS=2000
LLM_TEMPERATURE=0.7
```

启动时缺关键配置直接报错退出(fail fast),错误信息指明缺哪个变量。

## 8. 错误处理

- 请求体不合法:FastAPI/Pydantic 标准 422;
- 上游连接失败(未开始流):HTTP 502,响应体 JSON 含错误信息与上游地址、不含密钥;
- 上游中途断流:已推送的 token 保留,补发 `error` 事件后结束;
- 任何日志/报错不得打印 API key。

## 9. 测试与验证策略

按用户工作要求,可单测的部分走 TDD;纯 Prompt/数据类用标注样例验证:

- **单测(TDD)**:`memory.py`(裁剪边界、token 预算、会话存取、条数上限)、`config.py`(缺配置 fail fast);`chat_service` 管线用 LangChain 假模型/桩验证"裁剪 → 渲染 → 流式"的接线;SSE 接口用 httpx 内存客户端 + 桩服务验证事件序列;
- **Prompt 评估样例(替代 TDD)**:`potry-ai-agent/evals/chat_eval_cases.md` 放标注样例(角色一致性、约束遵守、多轮上下文续接),实现后拿真实 DeepSeek 跑一遍人工比对;
- **验收**:curl 实测流式 + 两轮上下文续接(见验收标准 1、2)。

## 10. 交付物

- 功能演示命令(curl 流式示例、两轮对话示例);
- 测试结果(pytest 输出摘要);
- `dev-notes/ch01.md` 过程留痕(每阶段追记:用户关键原话、关键产出、拒绝/纠偏、翻车与返工)。

## 11. 已确认的决策记录

| 决策点 | 结论 |
|---|---|
| 代码位置 | 就地扩展 `potry-ai-agent`,Nacos 注册保留 |
| 结构化 JSON(售后) | **删除**——用户确认"那是意外",验收只留流式 + 上下文两条 |
| 实测上游 | 用户提供 DeepSeek 密钥(仅入 `.env`) |
| 历史存储 | 服务端内存按 sessionId 存 |
| 实现路线 | 方案 A:LangChain 全家桶 |
| 聊天页面 | 后端验收通过后 Vibe Coding 顺带做,不套流程 |
| 设计评审 | S1 曾答"有调整意见",随后撤回("好像没有了,启动吧"),按原设计执行 |
