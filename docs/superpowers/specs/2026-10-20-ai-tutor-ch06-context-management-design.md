# AI 伴学系统 · 第六章(会话上下文管理:三层裁剪 · 异步摘要 · token 预算 · 多会话)设计

日期:2026-10-20
状态:已实现并完成五条验收,**325 passed**;演示配置真实跑出「降级 → 异步摘要两段 → 靠梗概回忆最早那首诗」,日志见 `potry-ai-agent/log/app.log`
落地位置:`potry-ai-agent/`(延续 Ch01–Ch05,就地扩展)
章节编号说明:需求原文写"本章 = 第7章、dev-notes/ch07.md";但项目实际只有 Ch01–Ch05(无 Ch06),**经用户确认按实际顺序作为 Ch06 实现**,留痕写 `dev-notes/ch06.md`(与 Ch05 当初"需求写第6章→记为 Ch05"的既定口径一致)。

## 1. 目标与范围

把第一版的"内存 dict + 按 token 截断"升级为**正经的会话上下文管理**:按远近三层、锚点驱动降级、后台异步摘要、从模型窗口倒推预算、上下文可观测、前端多会话。

本章要做:

1. **三层结构**:层 1(最近)原文不压;层 2(中间)按规则截短;层 3(最远)由后台异步压成一段段梗概。两个锚点(`summary_upto_msg_id` / `layer1_from_msg_id`)划边界,**降级只挪 id、不搬数据**。
2. **异步摘要**:层 2 攒到超预算 → 后台起一次摘要任务,把这一批压成新的一段**追加**进 `conversation_summaries`,边界追到层 1 起点;**全程不阻塞当前轮回复**。旧梗概只作背景、不参与合并。
3. **固定顺序拼装上下文**:system(人设 + 红线 + 工具定义)打头且每轮一致 → 层 2 截短对话 → 层 1 原文 → 当前用户句 → 梗概与检索证据**合成一条**挂在用户句之后。**梗概绝不单独占 system**。
4. **预算从窗口倒推**:扣固定开销与单轮 ReAct 峰值后归历史;层 1 拿七成、层 2 拿三成;启动自检,装不下一轮就告警。中文 token 口径与预算一起校准。
5. **State 与落库**:`messages` 挂 `add_messages` reducer;完整历史靠 checkpoint;调模型前另建精简版,两条路径互不影响。`conversations`/`messages` 承载历史与多会话。
6. **可观测**:每轮调模型前把实际上下文写进 `log/app.log`(`model_ctx` / `history_ctx`),摘要任务全生命周期留痕。
7. **前端多会话**:会话侧栏(新在前、首问预览、已摘要标记)、点击切换回载、新对话、两个只读接口;侧栏失败静默降级。

### 非目标(需求明确排除)

- **语义检索捞历史**、**主题重要度留关键事实**(理论篇三种选法里的另外两层)不实现;
- **跨会话长期记忆、用户画像**;
- 混合检索/重排升级、Langfuse 正式可观测性。

### 术语映射(需求文本为客服模板,经用户确认映射为诗词域)

| 客服模板 | 诗词域映射 |
|---|---|
| 订单号 / 手机号 | 诗题 / 诗句片段 / 诗人名 / 判定结论等**用户报过的线索** |
| 商品 | 某首诗 / 某位诗人 / 某次格律或校勘判定 |
| 订单数据 | 该诗作权威数据(`potry` / `writer` 表 + 知识库 chunk) |
| "最开始那个订单后来怎么说" | "最开始问的那首诗后来怎么说" |
| 客服答复 | 青莲的回答 |

### 验收标准(映射后的诗词域版本)

1. 连续聊 **20 轮以上**,token 不爆、系统不崩。
2. 用演示配置再聊一遍(只调窗口不够:固定开销与单轮峰值按默认的 X、Y、步数算,滑窗会归零并报「上下文预算不足」):
   `MODEL_CONTEXT_WINDOW=18000 MAX_OUTPUT_TOKENS=2000 MAX_USER_INPUT_TOKENS=2000 MAX_AGENT_STEPS=3 TOOL_RESULT_MAX_TOKENS=1200 RERANK_TOP_K=5`。
   这组算得**滑窗 5650、层 1 预算 3954、层 2 预算 1695**。日志能看到完整级联:层 1 超预算降级一批(`layer1 降级 X→Y`)→ 层 2 攒到超预算触发摘要(`summary trigger 层2 约 N token > 预算 M`)→ 压完落成新段(`summary done 第N段`)。此时问**「最开始问的那首诗后来怎么说」**,要能靠梗概里存下的诗题与诉求答对。
3. **默认窗口下聊 20 轮,不该触发任何降级与摘要**(装得下就不压;压缩是成本不是美德)。
4. 日志能看到早期轮次被后台摘要压缩的痕迹,且摘要**没有阻塞该轮回复**;`grep model_ctx / history_ctx` 能直接看到每轮发给模型的摘要与滑窗内容。
5. 前端侧栏能开多个会话对照、切回旧会话时**历史完整回载**、能接着聊。

### 需求→设计对照(逐条可追溯)

| 需求条目 | 落到 spec 的哪一节 |
|---|---|
| 1 三层结构 / 两个锚点 / 只挪 id | §3.1、§4(**锚点语义、降级批次、层 2 截短规则**) |
| 2 后台异步摘要 / 一段段攒 / 不回头重写 / 看用量 / prompt 只提炼事实 | §7(**触发、生命周期、批次、边界、prompt 对照表**) |
| 3 固定顺序拼装 / 梗概不单独占 system | §5(**6 步顺序、bind_tools 打头、稳定前缀**) |
| 4 窗口倒推预算 / 启动自检 / 中文 token 口径 | §6(**估算口径、公式、默认与演示逐项校验、自检**) |
| 5 两张表 + add_messages + checkpoint / 精简版另算 | §3.3、§8 |
| 6 model_ctx / history_ctx / 摘要全生命周期 | §9(**三条日志格式**) |
| 7 侧栏 / 切换回载 / 新对话 / 两个只读接口 / 静默降级 | §10、§11 |
| 验收 1(20 轮不爆) | §6.3 默认推导 + §13 端到端 |
| 验收 2(演示配置 5650/3954/1695 + 级联 + 靠梗概答对) | §6.3(**逐位推导**)+ §13 |
| 验收 3(默认 20 轮不降级不摘要) | §6.3(`layer1=11199 ≥ 8000`)+ §13 |
| 验收 4(压缩痕迹 + 不阻塞 + grep 两个 ctx) | §7.2、§9 + §13 |
| 验收 5(侧栏多会话 / 回载 / 续聊) | §10、§11 + §13 |

## 2. 技术栈(用户定死,不得自行更换)

| 项 | 结论 |
|---|---|
| 编排层 | 延用 **LangGraph**(`StateGraph` + `AsyncSqliteSaver`);`messages` 用 **`add_messages`** reducer |
| 裁剪 | 延用 **LangChain `trim_messages`**(`token_counter` 用自定义估算器 / `'approximate'`) |
| 落库 | **MySQL**(`conversations` / `messages` + 新增 `conversation_summaries`) |
| 异步 | 同进程 **`asyncio.create_task`** + 每会话 `asyncio.Lock` |
| 上游模型 | 延用现有聊天上游(DeepSeek,`.env`);**无新增依赖** |
| 前端 | 原生 HTML/CSS/JS(沿用 `static/chat.html`) |

**Context7 已核对(2026-10-20)**:`add_messages(left, right)` 按消息 id 合并、默认追加、同 id 覆盖;`trim_messages(messages, *, max_tokens, token_counter, strategy="last", allow_partial=False, start_on="human", end_on=None, include_end=True, include_system=False, ...)` 为当前签名。

## 3. 数据模型与迁移

### 3.1 `conversations`(扩展)

| 列 | 类型 | 说明 |
|---|---|---|
| `userid` | varchar(64) null | 前端 localStorage 的匿名 userId(侧栏按它过滤) |
| `summary_upto_msg_id` | bigint default 0 | **锚点 A**:摘要覆盖到的最后一条 `messages.id` |
| `layer1_from_msg_id` | bigint default 0 | **锚点 B**:层 1 起始 `messages.id`(层 2 右边界) |
| `updated_at` | datetime | 侧栏排序(新在前),每轮落库时更新 |

### 3.2 `conversation_summaries`(新建)

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | bigint PK auto | |
| `conversation_id` | bigint FK | 关联 `conversations.id` |
| `seq` | int | 段落序号,从 1 递增 |
| `upto_msg_id` | bigint | 本段覆盖到的最后一条消息 id |
| `content` | text | 梗概正文(40–200 字) |
| `created_at` | datetime | |

唯一键 `(conversation_id, seq)`,保证并发下不产生重复段。

### 3.3 `messages`(行为变更)

- **只写 `user` 与最终 `assistant` 两类行**;工具结果**不落表**(按用户拍板)。完整历史(含 `tool_calls` / `ToolMessage`)由 LangGraph checkpoint 保留。
- 只读接口回载时**只返回 `role in ('user','assistant')`**,过滤掉库里既有的 Ch04 遗留 `tool` 行(用户拍板:只回载 user+assistant)。

### 3.4 加列迁移 + Java 侧审计

`create_all` **不会**给已存在的 `conversations` 表加列。启动时执行 `ensure_schema(engine)`:
1. `Inspector.get_columns("conversations")` 取现有列;
2. 缺失列逐条 `ALTER TABLE conversations ADD COLUMN ...`;
3. 失败只告警(`[db] 迁移失败…`),不阻断启动;后续查询按缺列降级为默认值 0 / null。

SQLite(测试)由 `create_all` 直接建全,不触发 ALTER。

**Java 侧审计**:已 `Grep` 全仓 `potry-service` Java 源码,`conversations` / `messages` 未被 Java 读取或写入(仅在 `Chat.java` / `AiController.java` 用到 Spring AI 的 `Message` 抽象类,与 MySQL 表无关)。加列与只落 user/assistant 的安全前提成立。

## 4. 三层与锚点

设 `M` = 本会话全部 `messages`(按 `id` 升序),`S` = `conversation_summaries`(按 `seq` 升序):

```
层 3(远):  id ≤ summary_upto_msg_id          → S 的若干段拼接(只读,不回头重写)
层 2(中):  summary_upto < id ≤ layer1_from    → 按规则截短
层 1(近):  id > layer1_from_msg_id            → 原文,一个字不压
```

- **降级 = 只挪锚点 B**:层 1 实际 token > 层 1 预算 → 把最旧的一批消息划入层 2(`layer1_from_msg_id` 前移),日志 `[ctx] layer1 降级 X→Y`。**不复制、不删除、不改写任何消息行**。
  - **一批的定义**:从层 1 最旧处起,按**完整轮次**(`user` + 紧随的 `assistant`)搬移,直到层 1 估算 ≤ 预算;若单轮就超预算,至少搬 1 轮。搬移只更新锚点 B。
- **摘要 = 只挪锚点 A**:摘要任务成功后 `summary_upto_msg_id = 本批覆盖到的最末消息 id`。
- 两个锚点单调不减;新会话两值均为 0(层 1 覆盖全部)。

### 层 2 截短规则(确定性,不调模型)

| 消息类型 | 处理 |
|---|---|
| `user` | **原样保留**(用户原话不动) |
| `assistant` | 只保留开头 `LAYER2_ASSISTANT_PREFIX_CHARS = 40` 字;超长补 `…` |
| 大块内容(长度 > `LAYER2_BLOB_CHARS = 400`,含 Ch04 遗留 tool 行) | 替换为一行 `[工具结果:N字]` 标识 |

截短只作用于**喂给模型的副本**,不改库、不改 checkpoint。

## 5. 调模型的上下文拼装(固定顺序)

`context_builder.build_agent_context(state)` 每轮现拼:

```
1. SystemMessage(人设 + 红线)                      ← 与 bind_tools 的工具定义共同构成稳定前缀,每轮逐字一致
2. 层 2 截短消息(时间升序)
3. 层 1 原文消息(时间升序)
4. HumanMessage(用户当前这句)
5. HumanMessage("【早期梗概】…\n【检索资料】…")      ← 梗概与证据**合成一条**,挂在用户句之后
6. 本轮 ReAct 已产生的 AI / Tool 消息(循环内追加)
```

- **梗概不得单独成 `SystemMessage`**:上游模板会把所有 system 上提合并渲染,工具定义会被挤到可变内容之后,前缀缓存整段作废。
- **"工具定义打头"的落地方式**:工具定义仍通过 `bind_tools(...)` 传入(在消息列表之前由上游渲染),system 段只放**人设与红线**;二者共同构成每轮**逐字一致**的稳定前缀。builder **不得**把时间戳、轮次、摘要、证据等可变内容写进 system。
- `state.messages` **不写入** system / 梗概 / 证据;这些每轮由 builder 生成。
- **层 2 临时封顶**:摘要任务尚未完成时层 2 可能仍超预算;`build_agent_context` 从层 2 最旧处按完整轮临时不喂(数据仍留在库里等梗概),保证 `层1 + 层2 ≤ history_budget`。层 1 不动。
- **层 2 / 层 1 的数据来源是 `messages` 表**(表里的 id 才是锚点口径),只含已落库的前序轮次;本轮用户句与 ReAct 新消息从 `state.messages` 取,不重复计入层 1。精确取法:
  `messages[0:turn_message_start]` 中已落库部分已被 DB 覆盖,故 builder 实际拼接为
  `层2(DB) + 层1(DB) + state.messages[turn_message_start](本轮用户句) + 梗概/证据 + state.messages[turn_message_start+1:](本轮已产生的 AI/Tool 消息)`。
  这样锚点(DB id)与 State(完整历史)各管一段,互不串位。

`build_history_context(state)`(供指代消解/意图识别共用):

```
1. 若有梗概:一行「【早期梗概】…」+ 滑窗(层 2 截短 + 层 1 原文,按预算裁剪)
2. 无梗概:仅滑窗
```

- 滑窗口径与 Agent 侧**同源**(层 2 截短 + 层 1 原文),但另设上限 `HISTORY_CTX_MAX_TOKENS = 2000`(可配):消解/分类只需近期上下文,不必吃满 Agent 的历史预算;超限时从最旧处裁,裁到完整轮次。
- 若历史为空(首轮),`history_ctx` 仍打印一行 `(无)`(满足"每轮必打")。

### 5.1 每轮时序(实现与验收的共同基准)

```
1. resolve_node
   ├─ 读会话锚点(conversations) + 消息(messages) + 梗概(conversation_summaries)
   ├─ build_history_context → 打印 history_ctx
   ├─ 追加 HumanMessage(用户原问) 到 state.messages,记录 turn_message_start
   └─ 指代消解/改写(用 history_ctx,不用全量历史)
2. classify_node → route_node
3. 分支执行(知识检索/业务/判定子流程/投诉/闲聊/其他)
4. agent_node(需要时)
   ├─ build_agent_context → 打印 model_ctx(摘要全文 + 滑窗逐条 + 条数 + 估算)
   └─ ReAct 循环内只追加本轮 AI/Tool 消息
5. log_node
   ├─ 补 AIMessage(answer)(未入 messages 时)
   ├─ persist_turn(user + assistant 两类行,返回三 id)
   ├─ 层 1 实际 > layer1_budget → 按完整轮次前移 layer1_from_msg_id,打印 layer1 降级
   └─ 层 2 实际 > layer2_budget → 投递异步摘要(打印 summary trigger)
6. 响应返回后,后台任务继续跑;完成时打印 summary done 并推进 summary_upto_msg_id
```

## 6. token 预算(从模型窗口倒推)

### 6.1 token 估算口径

```
estimate_tokens(text) = ceil(CJK 字符数 × CJK_TOKENS_PER_CHAR + 其他字符数 / CHARS_PER_TOKEN)
CJK_TOKENS_PER_CHAR = 0.6 , CHARS_PER_TOKEN = 4.0
```

消息级估算 = 每条消息正文估算 + `MESSAGE_OVERHEAD_TOKENS = 4`(role/分隔等)。
**该口径与下面的预算常量一起校准**:400 字中文块 ≈ 240 token,与 `EVIDENCE_PER_CHUNK_TOKENS = 250` 对齐;只改其中一边会让净效果反向(估算偏小 → 实际超窗)。

### 6.2 推导公式

```
agent_peak      = MAX_AGENT_STEPS × TOOL_RESULT_MAX_TOKENS
fixed           = SYSTEM_RESERVE_TOKENS
                + RERANK_TOP_K × EVIDENCE_PER_CHUNK_TOKENS
                + SUMMARY_RESERVE_TOKENS
                + SAFETY_RESERVE_TOKENS
window_side     = MODEL_CONTEXT_WINDOW
                - MAX_OUTPUT_TOKENS
                - MAX_USER_INPUT_TOKENS
                - agent_peak
                - fixed
history_budget  = min(KEEP_TURNS × TURN_STEADY_TOKENS, window_side)   ← 需求原文:两个数取小
layer2_budget   = floor(history_budget × 0.3)                          ← 层 2 三成
layer1_budget   = history_budget - layer2_budget - BOUNDARY_RESERVE_TOKENS(1)  ← 层 1 七成(扣除 1 token 层间分隔)
```

> 公式严格照需求原文:**历史预算 = min(想留住的轮数 × 每轮稳态占用, 窗口匀得出来的),层 1 七成、层 2 三成**。`BOUNDARY_RESERVE_TOKENS=1` 只用于让三层预算与 `history_budget` 精确闭合(3954 + 1695 + 1 = 5650),不改变七三分语义。
>
> `KEEP_TURNS` 的取值原则:**保证默认配置下层 1 装得下验收 3 的 20 轮原文**。默认 `KEEP_TURNS=40 × TURN_STEADY_TOKENS=400 = 16000`,默认配置 `history_budget=16000`、`layer1_budget=11199 ≥ 20×400=8000`,故 20 轮不触发降级;演示配置下 `window_side=5650 < 16000`,取窗口侧,数字与验收 2 完全一致。

### 6.3 默认值与演示值校验

| 配置 | 默认 | 演示(验收 2) |
|---|---|---|
| `MODEL_CONTEXT_WINDOW` | 64000 | 18000 |
| `MAX_OUTPUT_TOKENS` | 4000 | 2000 |
| `MAX_USER_INPUT_TOKENS` | 2000 | 2000 |
| `MAX_AGENT_STEPS` | 4 | 3 |
| `TOOL_RESULT_MAX_TOKENS` | 1200 | 1200 |
| `RERANK_TOP_K` | 5 | 5 |
| `SYSTEM_RESERVE_TOKENS` | 1500 | 1500 |
| `EVIDENCE_PER_CHUNK_TOKENS` | 250 | 250 |
| `SUMMARY_RESERVE_TOKENS` | 500 | 500 |
| `SAFETY_RESERVE_TOKENS` | 1500 | 1500 |
| `KEEP_TURNS` | 40 | 40 |
| `TURN_STEADY_TOKENS` | 400 | 400 |

**演示配置推导(必须逐位一致)**:
`agent_peak = 3 × 1200 = 3600`;`fixed = 1500 + 5×250 + 500 + 1500 = 4750`;
`window_side = 18000 - 2000 - 2000 - 3600 - 4750 = 5650`;
`history_budget = min(40×400, 5650) = min(16000, 5650) = 5650`;
`layer2_budget = floor(5650×0.3) = 1695`;`layer1_budget = 5650 - 1695 - 1 = **3954**`。
→ **滑窗 5650 / 层 1 3954 / 层 2 1695** ✅

**默认配置推导**:
`agent_peak = 4 × 1200 = 4800`;`fixed = 1500 + 5×250 + 500 + 1500 = 4750`;
`window_side = 64000 - 4000 - 2000 - 4800 - 4750 = 48450`;
`history_budget = min(16000, 48450) = 16000`;`layer2 = 4800`;`layer1 = **11199**`。
→ 层 1 可装 `11199 / 400 ≈ 27` 轮原文,**20 轮(8000)远未触顶**,不发生降级;层 2 亦无内容,不触发摘要 ✅

**"光调窗口不够"的量化说明**:若只把 `MODEL_CONTEXT_WINDOW` 改成 18000 而保留默认
`MAX_OUTPUT_TOKENS=4000` / `MAX_AGENT_STEPS=4`,`window_side = 18000−4000−2000−4800−4750 = 2450`,
层 1 仅 `1714` token(约 4 轮),聊两轮就持续降级、摘要频繁触发,等同不可用;窗口再小或默认峰值再大,
`window_side` 会直接 ≤0 并触发 §6.4 的「上下文预算不足」。**验收 2 必须六个变量一起给**。

### 6.4 启动自检

- `history_budget ≤ 0` 或 `layer1_budget ≤ 0` → 打印
  `[ctx] 上下文预算不足:history_budget=0 …(请调大 MODEL_CONTEXT_WINDOW 或调小固定开销)`,滑窗归零、仅保留当前句(不崩服务)。
- 正常时打印一行 `[ctx] 预算:window=… history=… layer1=… layer2=…` 供验收比对。
- `MAX_AGENT_STEPS` 与既有 `WORKFLOW_MAX_ITER` 的关系:`MAX_AGENT_STEPS` 为单一来源;未配置时回退读 `WORKFLOW_MAX_ITER`(默认 4),并在启动日志注明回退,避免两套上限打架。
- **`WORKFLOW_MAX_TOKENS` 口径**:只约束**本轮 ReAct 增量**(`turn_message_start` 之后的消息 + 本轮 AI),不再统计整段历史;历史总量由上面的 `history_budget` 负责。否则长历史一进上下文就超过 8000,任何工具轮都会被立刻强制收敛。

## 7. 异步摘要

### 7.1 触发

每轮 `log_node` 落库后:
1. 计算**层 2 实际 token**(截短后的正文估算,不数条数);
2. 若 `layer2_actual > layer2_budget` → 投递摘要任务;否则不投递。
3. 每会话一把 `asyncio.Lock`;已有任务在跑 → `summary skip(已有任务)`。

### 7.2 流程与日志

```
summary trigger 会话=<sid> 层2 约 <N> token > 预算 <M>
summary start   会话=<sid> 覆盖 <from>..<to>(<k> 条)
   → LLM 生成梗概(40–200 字)
   → INSERT conversation_summaries(conversation_id, seq=last+1, upto_msg_id=to, content)
   → UPDATE conversations SET summary_upto_msg_id = to
summary done    会话=<sid> 第 <n> 段 覆盖到 <to> 耗时 <ms>ms
```

- **摘要输入取该批 `messages` 原文**,不是层 2 截短版:截短(客服答复只留 40 字、大块换标识)会先把订单号/诗题这类线索切掉,再压就压不出事实。截短只用于**喂给模型**的副本,摘要任务读库原文。
- **整批压一段**(用户拍板):取当前层 2 全部消息;若其 token 超过 `SUMMARY_BATCH_MAX_TOKENS = 3000`,只取最旧的部分,锚点只推进到**已压完的位置**(剩余下次再压)。
- **边界追到层 1 起点**:整批压完时,新段 `upto_msg_id` 必须等于当时的 `layer1_from_msg_id`(即层 2 右边界),不允许留缝;分批时则等于本批最后一条消息 id。
- **不阻塞**:`asyncio.create_task` 投递后立即返回;任务集合持引用防 GC;异常一律 `summary fail 会话=<sid>: <err[:200]>`,**锚点不动**,下一轮可重试。
- 无可压内容(层 2 为空)→ `summary skip(无内容)`。
- 服务关闭时取消未完成任务并记一行日志。

### 7.3 摘要 Prompt(纯 Prompt 任务)

只提炼**事实与诉求**,逐项对应需求原文(客服模板 → 诗词域):

| 需求原文要求保留的 | 诗词域口径 |
|---|---|
| 问过哪款商品 | 问过哪首诗 / 哪位诗人 / 哪句诗(诗题、作者、朝代) |
| 报过的订单号、手机号 | 用户报过的线索:诗题、诗句片段、诗人名、判定结论 |
| 明确诉求 | 想找什么样的诗、想判合不合律、想核对作者/原文/朝代 |
| 还没解决的问题 | 尚未得到结论的判定、没找到的诗、待补充的线索 |

硬约束:
- **对话里没出现的内容一个字不许编**(不得补全诗题、作者、朝代、结论);
- 寒暄、客套、感谢、重复表述**一律不留**;
- 长度 **40–200 字**;
- 只输出梗概正文,不要标题、不要解释、不要分点符号以外的格式。

## 8. LangGraph State

- `messages: Annotated[list, add_messages]`(替换 Ch04 的 `operator.add`);节点只返回**新增**消息,框架按 id 顺序并入。
- `resolve_node`:非续跑轮追加 `HumanMessage(用户原问)`;续跑轮不追加。
- `agent_node` / `tool_node`:只追加本轮 AI / Tool 消息。
- `log_node`:若最后一条不是内容相同的 `AIMessage`,补一条 `AIMessage(answer)`(投诉/闲聊/兜底/闸拦等不经 Agent 的出口),保证 checkpoint 里的历史完整。
- 新增 `turn_message_start: int`:`resolve_node` 记录**本轮 user 消息在 `messages` 中的下标**(追加前长度);`agent_node` 取 `messages[turn_message_start + 1:]` 作为"本轮已产生的 AI/Tool 消息",避免把上一轮混进当前轮。
- **完整历史**:全部在 `state.messages`,由 `AsyncSqliteSaver` 落盘。
- **精简版**:每轮由 `context_builder` 现算,不写回 state、不影响 checkpoint。
- Ch05 的 `history` 通道语义变更:不再手工累积最近 3 轮,改为**每轮由 `build_history_context` 生成**(= 摘要行 + 滑窗)。`HISTORY_TURNS` 与 `_next_history` 删除;`resolve_node` 从 `context_builder` 取历史,仍以 `list[{role, content}]` 传给 `resolve_input`。

## 9. 可观测

统一写入 `log/app.log`(UTF-8、追加、目录不存在则创建),同时打印 stdout;写文件失败只告警,不影响对话。

### 9.1 `model_ctx`(进 Agent 前,每轮一条)

```
[ctx] model_ctx 会话=<sid> 轮=<turn> 摘要=<梗概全文或(无)> 窗口=<k>条 估算=<n>token
  [system] <人设摘要,不含完整 prompt>
  [层2] <role>: <截短内容>
  ...
  [层1] <role>: <原文>
  ...
  [当前] user: <当前句>
  [梗概+证据] <合成条全文>
```

### 9.2 `history_ctx`(消解/意图共用的历史,每轮必打,含未进 Agent 的闲聊兜底轮)

```
[ctx] history_ctx 会话=<sid> 轮=<turn> 摘要=<一行或(无)> 滑窗=<k>条 估算=<n>token
  <role>: <内容>
  ...
```

### 9.3 其余

- 每个上下文块以 `[ctx] end model_ctx` / `[ctx] end history_ctx` 收尾,使 `grep -A 60 "model_ctx"` 能直接截到完整块(验收 4 的取证方式)。
- 预算:`[ctx] 预算:window=… history=… layer1=… layer2=…`
- 降级:`[ctx] layer1 降级 X→Y`
- 摘要:`summary trigger / start / done / skip / fail`

## 10. 落库与只读接口

### 10.1 写入(每轮)

`ChatStorage.persist_turn(session_id, user_text, answer, userid)`:
1. 按 `session_id` 取或建 `Conversation`(带上 `userid`,更新 `updated_at`);
2. 插入一行 `role='user'`(非空时)与一行 `role='assistant'`(最终答案);
3. **返回** `(conversation_id, user_msg_id, assistant_msg_id)`,供锚点与摘要使用。

首问预览由侧栏查询时取该会话最小 `messages.id` 的 user 内容前 30 字生成(不额外存列)。

### 10.2 只读接口(不加鉴权,单机演示)

```
GET /api/conversations?userId=<uid>
→ [{"sessionId":"…","preview":"…","updatedAt":"…","summarized":true|false}]
   按 updated_at 倒序;userId 为空时返回全部(演示兜底);查询失败返回 500,前端静默降级
   summarized = (conversations.summary_upto_msg_id > 0)
   preview   = 该会话最小 messages.id 的 user 内容前 30 字(无消息则为空串)

GET /api/conversations/{sessionId}/messages?userId=<uid>
→ [{"role":"user|assistant","content":"…","createdAt":"…"}]
   按 messages.id 升序;只返回 user/assistant(过滤遗留 tool 行);
   userId 不匹配 → 404(不泄露他人会话);不存在 → 404
```

### 10.3 会话标识

- 前端首次进入生成 `userId = crypto.randomUUID()` 存 localStorage;
- 「新对话」由前端生成新的 `sessionId`(不依赖后端 meta 分配),旧会话保留在侧栏;
- 每个请求都带 `userId`;`ChatRequest` 增加 `userId` 字段并透传落库。

## 11. 前端(原生 HTML/CSS/JS,Vibe 例外)

- 左侧会话侧栏:标题「对话」+「新对话」按钮 + 会话列表(首问预览、时间、`已摘要` 小标记、当前项高亮);当前项左侧竖线用暖金色,不用霓虹色。
- 点击会话 → `GET …/messages` 回载全部 user/assistant 原文渲染 → 后续消息沿用该 `sessionId` 继续聊。
- 「新对话」→ 清空消息区、生成新 `sessionId`、侧栏插入占位项(首问后刷新预览)。
- **侧栏加载失败静默降级**:只写一行 `console.warn`,不弹错误、不阻断发送;侧栏保持上次成功内容或空列表。
- **五种状态**:加载中(骨架/「载入中」)、空列表(「还没有对话」)、正常、加载失败(静默)、会话切换中(禁用重复点击)。
- 切换会话时未发出的输入框内容保留;发送中禁止切换,避免消息落到错误会话。
- 沿用现有宣纸/暖金配色与衬线字体;侧栏宽度 `240px`,窄屏(<900px)可收起(复用页头一个折叠按钮)。

## 12. 错误处理与降级

| 场景 | 处理 |
|---|---|
| 摘要 LLM 失败/超时 | `summary fail`,锚点不动,下一轮重试;用户回复不受影响 |
| 摘要写入冲突(唯一键) | 视为已有同段,`summary skip`,不重复插入 |
| 预算为 0 | 启动告警;滑窗归零,仅保留当前句与梗概 |
| `log/app.log` 写失败 | 只告警,继续对话 |
| 加列迁移失败 | 只告警;相关字段读默认 0 / null |
| 侧栏接口失败 | 前端静默降级 |
| checkpoint 消息过大 | 由预算裁剪保证调模型安全;checkpoint 保留完整历史(磁盘增长为已知代价) |

## 13. 测试与验收策略

**可单测(TDD)**:
- `estimate_tokens` 中英混排口径与消息级开销;
- 预算公式:**断言演示配置得到 5650 / 3954 / 1695**;默认配置 16000 / 11199 / 4800;预算为 0 的自检告警;
- 三层切分(锚点边界开闭)、层 2 截短(用户原话不动 / assistant 40 字 / 大块替换);
- 拼装顺序(system 首条、梗概不是 SystemMessage、梗概+证据合成一条且在用户句后);
- 摘要触发条件(层 2 超预算才触发)、并发锁去重、失败不改锚点、整批超 3000 时只压最旧部分;
- `persist_turn` 只写 user/assistant,返回三个 id;
- 加列迁移(缺列补列、失败不阻断);
- 两个只读接口(排序、预览、summarized 标记、tool 行过滤、userId 不匹配 404);
- `add_messages` reducer:同 id 覆盖、追加顺序。

**纯 Prompt / 数据类 → 标注样例替代 TDD**:
- 摘要质量评估集:**≥10 条多轮样例**(每条含诗题/诗人/诉求/未解决问题),真实模型跑批,断言:
  - 关键事实(诗题、诗人、明确诉求)在梗概中出现;
  - 梗概中**不出现源对话里没有的**专名(简单词表比对);
  - 长度 40–200 字;
  - 寒暄句(如"谢谢""你好")不出现在梗概中。

**端到端(验收)**:§1 五条逐条真跑,日志用 `grep model_ctx|history_ctx|summary|layer1 降级` 取证;前端侧栏人工验证。

## 14. 已确认决策与偏差留痕

| 决策点 | 结论 |
|---|---|
| 章节编号 | 需求写"第7章 / ch07.md" → 项目无 Ch06,按实际顺序记为 **Ch06 / dev-notes/ch06.md**(用户确认) |
| 领域映射 | 客服模板 → **诗词域等价物**(用户确认):订单号↔诗题/诗句/诗人/判定结论,商品↔诗作/诗人/判定 |
| 用户标识 | **前端 localStorage 匿名 userId**;`conversations.userid` 过滤侧栏(用户确认) |
| 工具结果落库 | **只落 user + 最终 assistant**;完整历史靠 checkpoint(用户确认,偏差于 Ch04 四段式) |
| 历史回载 | 只回载 user+assistant,**过滤库里遗留 tool 行**(用户确认) |
| 摘要载体 | **同进程 `asyncio.create_task` + 每会话锁**(用户确认) |
| 摘要批次 | **整批压一段**,超 3000 token 只压最旧部分(用户确认) |
| 默认窗口 | `MODEL_CONTEXT_WINDOW=64000`、`MAX_OUTPUT_TOKENS=4000`(用户确认) |
| 预算公式 | **严格按需求原文**(用户评审要求不偏离):`history = min(KEEP_TURNS×TURN_STEADY, window_side)`,层 1 七成、层 2 三成;`KEEP_TURNS=40`,使默认配置层 1 = 11199 装得下 20 轮(验收 3) |
| 层间 1 token | `BOUNDARY_RESERVE_TOKENS=1`,使 `3954 + 1695 + 1 = 5650` 自洽 |
| `WORKFLOW_MAX_TOKENS` | 只约束本轮 ReAct 增量,历史由 `history_budget` 管(实现计划 Task 8 明确) |
| `history` 通道语义 | 由"手工累积最近 3 轮"改为"每轮由 `build_history_context` 生成(摘要+滑窗)";删除 `HISTORY_TURNS` / `_next_history`,同步改 Ch05 相关测试 |
| ⚠️ 需同步改的既有测试 | ① `test_workflow_nodes.py::test_log_node_prints_structured_line_and_persists`(四段式 → 两段式);② 两个 `history` 相关用例;③ `test_workflow_graph.py` 中依赖 `messages` 累积细节的断言;④ `test_chat_service.py` 若受 `MAX_AGENT_STEPS` 回退影响 |
| 已知代价 | checkpoint 保留完整历史会持续增长(本章不做裁剪/归档);侧栏无鉴权(单机演示) |

## 15. 模块划分

| 模块 | 动作 | 职责 |
|---|---|---|
| `context_budget.py` | Create | token 估算、预算推导、启动自检 |
| `context_layers.py` | Create | 三层切分(锚点)、层 2 截短 |
| `context_builder.py` | Create | `build_agent_context` / `build_history_context`(固定顺序拼装) |
| `summarizer.py` | Create | 触发判定、异步任务、锁、段落追加、锚点推进、生命周期日志 |
| `context_log.py` | Create | `log/app.log` 追加写 + `model_ctx` / `history_ctx` 格式化 |
| `storage.py` | Modify | `Conversation` 加 4 列、`ConversationSummary` 模型、`persist_turn` 改两段式并返回 id、会话列表/消息回载查询、`ensure_schema` |
| `config.py` | Modify | 新增 §6.3 全部预算配置项 + `SUMMARY_BATCH_MAX_TOKENS` / `HISTORY_CTX_MAX_TOKENS` / `LAYER2_ASSISTANT_PREFIX_CHARS` / `LAYER2_BLOB_CHARS` / `BOUNDARY_RESERVE_TOKENS` |
| `workflow/state.py` | Modify | `messages` 改 `add_messages`;新增 `turn_message_start`;删除 `history`/`HISTORY_TURNS` |
| `workflow/nodes.py` | Modify | `resolve` 追加用户消息并记录 `turn_message_start`;`log` 补 AI 消息、写上下文日志、触发摘要 |
| `workflow/agent_react.py` | Modify | 用 `build_agent_context` 取代原 `_seed_messages`;ReAct 循环只追加新消息 |
| `workflow/resolve.py` | Modify | 接收 `build_history_context` 产物(签名不变) |
| `main.py` | Modify | `userId` 入参;两个只读接口;启动预算自检与迁移;`log/app.log` |
| `static/chat.html` | Modify | 会话侧栏、切换回载、新对话、userId 持久化 |
| `eval_summary.py` | Create | 摘要质量评估集(纯 Prompt 任务) |
| `tests/test_context_*.py`、`tests/test_summarizer.py`、`tests/test_conversations_api.py` | Create | §13 单测 |
