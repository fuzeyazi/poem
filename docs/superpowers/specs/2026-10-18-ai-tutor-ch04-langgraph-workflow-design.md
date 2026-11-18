# AI 伴学系统 · 第四章(LangGraph Workflow 确定性编排)设计

日期:2026-10-18
状态:已定稿(brainstorm 设计逐节通过)
落地位置:`potry-ai-agent/`(延续 Ch01–Ch03,就地扩展)
章节编号说明:需求原文写"本章 = Ch05、复用第 2 章工具 / 第 3-4 章检索器",但本项目实际只有 Ch01(聊天)/Ch02(Function Calling 工具)/Ch03(知识库+向量检索),**经用户确认按实际顺序作为 Ch04 实现**(无 Ch04 空缺)。

## 1. 目标与范围

把 Ch02 的**单轮 Function Calling**升级为**确定性 Workflow 编排**:以 **LangGraph 图骨架**为编排层,主力 Agent 作为骨架内的 **ReAct 执行节点**。

1. **先无框架原生实现**:手写最基础 Agent 循环(LLM 调用 → 工具调用 → 结果回传 → 无工具调用即收敛),证明 Agent 本质是"带工具调用能力的循环",**完成后再基于 LangGraph 重构**;
2. **LangGraph 图骨架**,节点顺序固定:指代消解 → 意图识别 → 意图分流 → 知识检索 → 置信度闸 → 主力 Agent → 日志记录;
3. **意图分流规则硬编码**:七类意图 → 四个固定出口(见 §4);
4. **主力 Agent 用 ReAct 循环**:简单问题单次工具调用即收敛,复杂问题多轮迭代,信息缺失主动追问;必须有**明确停止判定 + token 上限**;复用 Ch02 三个诗词工具,**本章不新增业务类工具**(唯一偏差见 §12);
5. **全会话状态**经 LangGraph 原生 State 贯穿,持久化用 LangGraph 自带 checkpointer;
6. 指代消解/意图识别**本章仅最简版**(透传 / 简单 Prompt 输出严格 JSON);
7. **置信度闸**仅作用于"知识类检索后、进 Agent 前";证据不足 → 兜底话术 + 记录待处理问题;业务类不经过;最简阈值,正式逻辑留待可观测性章节;
8. **转人工 / 提交反馈**为两个**独立**操作,后端不自动触发,仅在回复中携带可选操作标识,由前端渲染按钮;两按钮互不绑定,不点击则对话照常推进。

### 非目标(本章不做,需求明确排除)

- 意图识别与指代消解的**正式优化版**;
- 上下文管理策略升级、MCP 接入、**数据飞轮入库逻辑**;
- Langfuse 可观测性(留待"可观测性章节")。

### 领域映射(需求文本为客服模板,经用户确认映射为诗词域)

需求原文的「客服系统 / 物流 / 订单 / 商品咨询 / 退款退货 / 售后 / 投诉 / 客服小猫 / 工单(tickets 表)」为**客服模板话术**,本项目本体为**诗词伴学**(Ch02 已确立该口径):

| 客服原文 | 诗词域映射 |
|---|---|
| 商品咨询 / 退款退货 | **诗词释义/赏析**、**典故/出处查询**(知识类,强制 RAG) |
| 物流 / 订单 / 售后 | **查诗词 / 查诗人 / 查朝代**(业务数据类,直传 Agent) |
| 投诉 | **纠错/不满**(答得不对、不满意) |
| 闲聊 | 闲聊 |
| 客服小猫 | 人设仍为「**青莲**」 |
| 工单(tickets 表) | 写 **`feedback`** 表(库中无 `tickets` 表) |
| 第2章工具(查订单/查物流) | Ch02 的 `query_poem`/`query_poet`/`query_dynasty_poems` |
| 第3/4章检索器、第4章证据阈值 | Ch03 的向量检索(`embeddings.embed` + `vector_store.search`)与相似度得分 |

### 验收标准(映射后的诗词域版本)

1. **强制检索可观测**:用户发送**知识类**问题(如「《静夜思》表达了什么感情」「举头望明月出自哪首诗」)→ 系统日志可明确观测到**知识检索节点被正常执行**(含检索得分与是否过闸)。
2. **业务类由 Agent 自主调工具**:用户发送「《静夜思》是谁写的」「李白是什么朝代的」类问题 → 日志可观测 **主力 Agent 自主调用** `query_poem`/`query_poet`/`query_dynasty_poems` 并据此作答。
3. **投诉类两个独立按钮**:用户发送「答得不对,我不满意」→ 前端**同时出现**「转人工」「提交反馈」两个独立按钮;
   - 点「转人工」→ 前端展示「已转接人工客服」+ 青莲版问候「您好,我是青莲,请问有什么可以帮您的」(**仅前端模拟,不对接真人**);
   - 点「提交反馈」→ 调用 `submit_feedback` 写入 **`feedback`** 表;
   - **两操作互不干扰**;**用户未点击任何按钮继续发消息时,按正常对话流程处理,不执行任何额外操作**(须显式验证:未点击时 `feedback` 表行数不变)。
4. **闲聊固定话术**:用户发送闲聊内容 → 返回**预设固定话术**,日志可见**未调用任何模型与工具**。
5. **ReAct 多轮迭代可观测**:触发"需先查 A 再查 B"的复杂问题(如「李白写月亮的那首诗讲了什么」→ 先查诗词再取释义/赏析)→ 日志可观测 **ReAct 循环迭代 > 1 轮**。

## 2. 技术选型(用户定死,不得自行更换)

| 项 | 结论 | 说明 |
|---|---|---|
| 编排层 | **LangGraph**(`StateGraph` + `TypedDict` 状态 + `add_conditional_edges`) | 图编排、状态管理、checkpointer 持久化全部用 LangGraph;官方 API 已过 Context7 核对 |
| 持久化 | **`AsyncSqliteSaver`**(`langgraph-checkpoint-sqlite`,`langgraph.checkpoint.sqlite.aio`) | 官方自带 checkpointer 组件;文件放 `potry-ai-agent/checkpoints/graph.sqlite`。⚠️ **原定同步版 `SqliteSaver` 实测不支持异步图(`await graph.ainvoke` 抛 `NotImplementedError`),经用户批准改用同类异步变体 `AsyncSqliteSaver`;存储后端仍为 SQLite 文件,未变更。** ⚠️ LangGraph **无官方 MySQL checkpointer**,故本设计存在"SQLite(图状态)+ MySQL(业务数据)"双存储 |
| ReAct | **手写子循环**(`agent` 节点 + `tool_node` + `should_continue` 条件边) | 官方文档标准写法;便于显式控制停止判定/token 上限,并与"无框架手写版"对照 |
| LLM | 沿用 Ch01–Ch03(DeepSeek,`.env`) | |
| 工具 | **复用 Ch02 三个诗词工具**(+ 1 个偏差项 `submit_feedback`,见 §12) | |
| 检索器 | **复用 Ch03**(`embeddings.embed` + `vector_store.search` + `knowledge.get_chunk`) | |
| 前端 | 原生 HTML/CSS/JS(沿用 `static/chat.html`) | Vibe Coding 例外(同 Ch01/Ch02) |

## 3. 架构与数据流

### 3.1 图骨架(节点顺序按需求固定)

```
START → 指代消解 → 意图识别 → 意图分流 ─┬─ 知识类: 知识检索 → 置信度闸 ─┬─ 证据足 → 主力Agent(ReAct) ─┐
                                        │                              └─ 不足  → 兜底话术 + 记录待处理 ─┤
                                        ├─ 业务类: ──────────────────────── 主力Agent(ReAct) ────────────┤
                                        ├─ 投诉类: 安抚话术 + ["handoff","feedback"] ────────────────────┤
                                        └─ 闲聊类: 固定话术(不调模型/工具) ─────────────────────────────┴→ 日志记录 → END
```

### 3.2 模块划分(`potry-ai-agent/` 内,延续扁平风格)

| 模块 | 动作 | 职责 |
|---|---|---|
| `naive_agent.py` | Create | **无框架原生 Agent 循环**(需求第 1 条先行验证:LLM → tool_calls → 执行 → 回灌 → 收敛),带单测 |
| `workflow/state.py` | Create | `WorkflowState(TypedDict)` 定义 |
| `workflow/nodes.py` | Create | 七个节点的实现(指代消解/意图识别/意图分流/知识检索/置信度闸/主力Agent/日志记录) |
| `workflow/graph.py` | Create | 组装 `StateGraph` + 条件边 + `SqliteSaver` compile |
| `workflow/intent.py` | Create | 七类意图定义 + **硬编码**分流映射表(七类→四出口) |
| `workflow/agent_react.py` | Create | 主力 Agent 的 ReAct 子循环(停止判定 + token 上限) |
| `workflow/confidence.py` | Create | 置信度闸(复用 Ch03 检索,固定阈值) |
| `knowledge.py` | Modify | 新增 `pending_questions` 极简表模型 + 写入方法 |
| `tools/feedback_tool.py` | Create | `submit_feedback`(写 `feedback` 表) |
| `main.py` | Modify | 新增 `/agent/workflow`(SSE)与 `POST /agent/feedback`;保留原 `/agent/chat` |
| `static/chat.html` | Modify | 两个按钮 + action 事件处理(Vibe Coding) |
| `chat_service.py` | 不动 | 原单轮编排保留(Ch01–Ch03 回归不受影响) |

### 3.3 数据流(一次请求)

```
POST /agent/workflow {sessionId, message}
  → SSE: meta
  → 图执行(thread_id = sessionId)
     指代消解(透传) → 意图识别(LLM 输出 JSON 七类) → 意图分流(硬编码查表)
       ├ 知识类 → 知识检索(Ch03 检索器) → 置信度闸(阈值判定)
       │           ├ 足 → 主力Agent(ReAct: 可多轮调工具) → answer
       │           └ 不足 → 兜底话术 + 写 pending_questions → answer
       ├ 业务类 → 主力Agent(ReAct)
       ├ 投诉类 → 安抚话术 + actions=["handoff","feedback"]
       └ 闲聊类 → 固定话术
     → 日志记录节点(落本轮意图/路由/迭代数/tokens/是否过闸/耗时)
  → SSE: token* → (action 事件,若有可选操作) → done
```

## 4. 意图识别与分流(硬编码)

**七类意图**(最简版:由 Prompt 输出严格 JSON,仅取 `intent` 字段):

| # | 意图标签 | 出口 | 行为 |
|---|---|---|---|
| 1 | `poem_explain`(诗词释义/赏析) | **知识类** | 强制 RAG → 置信度闸 → 证据足才传 Agent |
| 2 | `reference_lookup`(典故/出处查询) | **知识类** | 同上;**先检索知识再传 Agent,Agent 执行中仍可自主调诗词工具** |
| 3 | `find_poem`(查诗词) | **业务类** | 不预检索,直传 Agent |
| 4 | `find_poet`(查诗人) | **业务类** | 同上 |
| 5 | `find_dynasty`(查朝代) | **业务类** | 同上 |
| 6 | `complaint`(纠错/不满) | **投诉类** | 不进入 Agent |
| 7 | `chitchat`(闲聊) | **闲聊类** | 不调模型/工具 |

**分流规则硬编码**在 `workflow/intent.py` 的常量映射表中(`INTENT_TO_ROUTE`),不交给模型决策;意图识别只负责产出标签。

**约束**:意图识别 Prompt 必须**只输出 JSON**(如 `{"intent": "find_poet"}`);解析失败 → 降级为 `chitchat` 并记录告警(不抛异常、不阻断流程)。

## 5. 状态与持久化

`WorkflowState(TypedDict)`:

| 字段 | 说明 |
|---|---|
| `session_id` | 会话标识(沿用现有 sessionId;作为 checkpointer 的 `thread_id`) |
| `user_input` / `resolved_input` | 原始输入 / 指代消解后输入(本章透传,两者相同) |
| `intent` / `route` | 意图标签 / 出口(知识类/业务类/投诉类/闲聊类) |
| `retrieved` / `evidence_score` | 检索证据(list)/ 证据强度(top1 相似度) |
| `messages` | `Annotated[list, operator.add]`,LangGraph 消息累积 |
| `answer` / `actions` | 最终回答 / 可选操作标识(如 `["handoff","feedback"]`) |
| `iterations` / `tokens_used` | ReAct 迭代数 / token 累计 |
| `fallback_reason` | 兜底原因(证据不足等) |

**checkpointer**:`SqliteSaver(sqlite3.connect("potry-ai-agent/checkpoints/graph.sqlite", check_same_thread=False))`;调用带 `config={"configurable": {"thread_id": session_id}}`。SQLite 文件加入 `.gitignore`。

## 6. 主力 Agent(ReAct 子循环)

- 节点内部为 `agent_node`(调 LLM、bind Ch02 工具)→ `should_continue` 条件边 → `tool_node`(执行工具)→ 回到 `agent_node` 的循环;
- **停止判定(三条,任一满足即收敛)**:
  1. 模型响应**不含 tool_calls**(自然收敛);
  2. `iterations >= MAX_ITER`(默认 4):强制收敛,基于已有信息作答并说明未完成部分;
  3. `tokens_used >= MAX_TOKENS`(默认 8000):同上。
- **信息缺失** → 以"追问"作为 answer 收敛(如「你是想查哪位诗人的作品?」),不空转;
- 工具集 = Ch02 三个诗词工具 +(`submit_feedback`,见 §12);**工具契约不变**;
- 应答复用 Ch01 的人设("青莲")与 Ch02 的工具使用约束。

## 7. 置信度闸(仅知识类,Agent 之前)

- 实现:复用 Ch03 `embeddings.embed` + `vector_store.search` 取 top-k;**检索范围为全库**——对 `poem`/`poet`/`qa` 三类 `source_type` **各取 top-k 后合并、按相似度降序**取前 k(最简实现;`vector_store.search` 单次只接受一个 `source_type`,故需三次调用后合并);
- `evidence_score = 合并后的最高相似度`;
- **阈值复用 Ch03 已有配置**`settings.similarity_threshold`(`.env` 的 `SIMILARITY_THRESHOLD`,默认 0.5),**不新增环境变量**;`evidence_score >= 阈值` 判定"证据充足";
- 充足 → 把**检索到的原文片段(`raw_text`/`chunk_text`)+ 用户问题**一并传入主力 Agent;
- 不足 → **兜底话术**(如「这块我暂时没查到确切的资料,要不换个问法?」)+ 写 `pending_questions`(问题原文 + 时间 + 会话 id),**不进入 Agent 节点**;
- **业务类/投诉类/闲聊类不经过本节点**(分支图中直接绕过)。

## 8. 前端(两个按钮,Vibe Coding 例外)

- SSE 新增 `action` 事件:`data: {"actions": ["handoff","feedback"]}`(在 `done` 之前发送);
- 前端渲染两个**独立按钮**;点击行为:
  - 「转人工」→ **纯前端**:在消息区展示「已转接人工客服」+ 青莲版问候「您好,我是青莲,请问有什么可以帮您的」(不对接真人系统);
  - 「提交反馈」→ `POST /agent/feedback {sessionId, message}` → 后端调 `submit_feedback` 写 `feedback` 表,前端提示「已提交,感谢反馈」;
  - **两按钮互不绑定**;不点击而直接继续发消息 → **走正常对话流程,后端不执行任何额外操作**。

## 9. 落库

- **新增** `pending_questions`(极简表):`id` / `question`(text)/ `session_id` / `created_at`;归属 `KnowledgeBase`(与知识库表同 Base,便于 `build_kb`/`main` 的 `create_all`);
- **复用** `feedback`(id / userid / messsage / creatime,注意原表列名的拼写即为 `messsage`、`creatime`):`submit_feedback` 写入 `messsage` 为反馈内容;`userid` 在无登录态时留空;
- 本轮编排日志:**不新增日志表**。日志记录节点输出一行**结构化日志**(便于验收用 grep 观测),格式固定为:
  `[wf] intent=<意图> route=<出口> gate=<pass|insufficient|skip> score=<相似度或-> iters=<迭代数> tokens=<token数> elapsed=<毫秒>`
  同时沿用 Ch02 把本轮对话落 `messages` 表;**验收 1/2/4/5 均以这行日志为观测点**(grep `\[wf\]`)。
  注:结构化日志用于验收观测,与"后续可观测性章节用 Langfuse 做正式追踪"不冲突。

## 10. 错误处理与降级

- 意图识别 JSON 解析失败 → 降级 `chitchat` + 告警,不阻断;
- 知识检索失败(模型/向量库不可用)→ 视为**证据不足**,走兜底话术 + 记录待处理;
- 主力 Agent 达到上限 → 强制收敛并说明,不无限循环;
- 工具执行失败 → 沿用 Ch02 `{"ok":false,"error"}` 契约,由模型组织回答;
- 单节点异常 → 该请求降级为兜底话术 + 结构化错误日志,SSE 补 `error` 帧,服务不崩;
- 日志不打印密钥,异常串截断 `[:200]`。

## 11. 测试与验收策略

**可单测(TDD)**:

- `workflow/intent.py`:七类意图 → 四出口**映射表完整性**(7 类齐全、出口取值合法);
- `workflow/confidence.py`:阈值判定(≥阈值过闸 / <阈值兜底)、兜底写入 `pending_questions`;
- `workflow/agent_react.py`:停止判定三条(无 tool_calls / 迭代上限 / token 上限)、迭代计数递增;
- `workflow/graph.py`:图可编译、节点齐备、条件边路由正确(四种出口各走对分支;可用 stub 节点替换 LLM/工具);
- `naive_agent.py`:手写循环的收敛与多轮迭代(与 ReAct 版行为一致);
- `submit_feedback`:写 `feedback` 表(字段映射、行数 +1);
- `pending_questions`:写入幂等/字段。

**纯 Prompt / 数据类 → 标注样例替代 TDD**(按用户工作要求 1):

- **意图识别 Prompt**:标注样例(七类各 ≥3 句 → 期望 JSON 标签),跑真实模型比对照表;
- 投诉安抚话术、闲聊固定话术:标注样例核对(固定话术为常量,直接断言)。

**验收**:§1 五条逐条真跑(含日志观测点)。

**依赖新增**:`langgraph`、`langgraph-checkpoint-sqlite`(版本以实际安装为准,安装前先过 Context7 核对 API 与 Python 3.11 兼容性)。

## 12. 已确认决策与偏差留痕

| 决策点 | 结论 |
|---|---|
| 领域映射 | 客服模板 → **诗词域**(用户确认,同 Ch02 口径) |
| 章节编号 | 按实际顺序作为 **Ch04**(需求原文写 Ch05;无 Ch04 空缺) |
| ReAct 实现 | **手写子循环**(用户确认) |
| checkpointer(初定) | **SqliteSaver**(用户确认;LangGraph 无官方 MySQL checkpointer) |
| checkpointer(落地修正) | 写计划期实测发现**官方 `SqliteSaver` 是同步专用类**,本项目 asyncio 服务用 `await graph.ainvoke` 直接抛 `NotImplementedError: The SqliteSaver does not support async methods`。按"选型定死、矛盾即暂停反馈"停下请示,用户拍板**改用 `AsyncSqliteSaver`**(同类异步变体,存储后端仍 SQLite 文件 `checkpoints/graph.sqlite`) |
| 转人工话术 | 改**青莲版**(用户确认):「您好,我是青莲,请问有什么可以帮您的」 |
| 建工单落点 | 写 **`feedback`** 表(库中无 `tickets`) |
| `submit_feedback` 工具 | **用户选择"注册给 Agent"**,⚠️ 与需求第 8 条"后端不自动触发"存在张力:`Agent` 可能自行调用写库。**缓解措施**:①在主力 Agent 的 system prompt 中**明确约束**"不得主动提交反馈,仅当用户明确要求提交时才调用";②验收③**显式验证"未点击按钮时 `feedback` 表行数不变"**;③该偏差在本节留痕 |
| 待处理问题记录 | **新建极简表 `pending_questions`**(用户确认) |
| 建库时机 | **先用现有 ~50% 语料**做(用户确认);故验收①的检索覆盖"诗人全量 + 约一半诗词",未嵌入的诗检索不到属预期,须在交付中说明 |
| 前端 | Vibe Coding 例外(不套 brainstorm/TDD/code review),同 Ch01/Ch02 |
| 原 `/agent/chat` | **保留不动**,新增 `/agent/workflow`,保证 Ch01–Ch03 回归不受影响 |
