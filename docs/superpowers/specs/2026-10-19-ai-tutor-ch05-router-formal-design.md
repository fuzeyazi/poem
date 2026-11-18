# AI 伴学系统 · 第五章(分流器正式版:指代消解 · Query 改写/扩写 · 意图识别 · 分流精化 · 槽位处理)设计

日期:2026-10-19
状态:已定稿(brainstorm 设计逐节通过与用户三处拍板)
落地位置:`potry-ai-agent/`(延续 Ch01–Ch04,就地扩展)
章节编号说明:需求原文写"本章 = 第6章、dev-notes/ch06.md";但本项目实际只有 Ch01(聊天)/Ch02(Function Calling)/Ch03(知识库+向量检索)/Ch04(LangGraph Workflow 编排),**经用户确认按实际顺序作为 Ch05 实现**,留痕写 `dev-notes/ch05.md`(无 Ch05 空缺;与 Ch04 当初"需求写第5章→记为 Ch04"的既定口径一致)。

## 1. 目标与范围

把 Ch04 里**占位的分流器**做成正式版。Ch04 的 `resolve` 节点是"直接透传"、`classify` 是"简单 Prompt 输出 JSON、解析失败降级 chitchat"、分流只有四出口、且**没有槽位处理**;本章把这四件事做实。

本章要做:

1. **指代消解 + Query 改写**(合成一个 LLM 环节):结合**本会话对话历史**,把「它合律吗」这类带指代的话补全成不依赖上下文也能看懂的完整问题;口语模糊问法归一成标准问法;**问题本身已完整、指代已明确的原样透传,不强行改写**。
2. **Query 扩写**(仅判定子流程用):把一句问题泛化成多条侧重点不同的检索查询(强制 JSON,字段只有 `queries` 数组),多条一起检索后**去重合并**;扩写放在**检索侧现查现用**,知识库只留一份,不在入库侧拆存多份。
3. **意图识别正式版**:LLM prompt 路线(不训分类模型),prompt 按**四件套**写 —— 枚举成选择题 / 强制 JSON(`intent` + `confidence`)/ 边界 few-shot / `other` 兜底类。拿不准归 `other`,不硬塞进业务意图。
4. **分流精化**:`格律/体裁合规` 与 `诗作校勘核对` 两条走**确定性子流程** —— 先取**对象数据**(该诗作权威数据),再做 Query 扩写并**强制检索规则条款**(新增 `policy` 知识),最后**只把「能不能 / 对不对」交给主力 Agent 判断**。
5. **槽位处理**:缺对象(没说是哪首诗/哪句)不让模型猜 → 执行阶段下发可点选的**诗词卡片**(订单选择器的诗词域等价物)让用户点选回填;**原因类目**不追问,用户提交**纠错/复核单**时从固定类目下拉自选;**需求澄清**留在主力 Agent 里做,意图识别只判"要干什么"。
6. **前端配套(Vibe Coding 例外)**:聊天流里的可点选诗词卡片 + 纠错/复核单表单(类目下拉)。

### 非目标(本章不做,需求明确排除)

- **微调小模型 / BERT 做意图分类**;
- **跨会话记忆**:指代消解只用**本会话**历史,不跨会话;
- 意图识别的**两级降级实际启用**(见 §11 决策:本章只做单级大模型 + 预留口子);
- 正式可观测性(Langfuse)、混合检索升级、上下文裁剪策略升级。

### 术语映射(需求文本为客服模板,经用户确认映射为诗词域)

| 客服模板 | 诗词域映射 |
|---|---|
| 订单 / 订单号 | **诗作对象**(某首诗 / 某句诗);"单号" = 诗题或诗句 |
| 订单数据 | 该诗作的**权威数据**(`potry` / `writer` 表 + 知识库 chunk) |
| 政策条款 | 新增知识类型 **`policy`**:格律·词牌规则 / 校勘准则文档 |
| 退款退货 | **格律/体裁合规判定**("能不能":这句合不合律、这首是不是七律) |
| 售后 | **诗作校勘核对**("对不对":作者/原文/朝代是否与权威数据一致) |
| 订单选择器 | **诗词卡片选择器**(候选诗作卡片,点选回填) |
| 退款单 + 退款原因类目 | **纠错/复核单** + 固定类目(格律错误 / 作者张冠李戴 / 原文有误 / 译文有误 / 赏析不认同) |
| 商品咨询 | 诗词释义/赏析 |
| 物流 / 订单(查状态/查单据) | 查诗词 / 查诗人 |
| 投诉 | 纠错/不满 |
| 闲聊 | 闲聊 |

### 验收标准(映射后的诗词域版本)

1. **多轮意图与指代**:造一组多轮对话用例 —— 用户从**问诗人**切到**要判格律**再聊回**查诗词**,每轮:①意图判对;②带指代的那轮(如「它合律吗」)指代补全正确。
2. **JSON 稳定 + `other` 兜底**:意图输出 JSON 稳定可解析(断言可解析率);拿不准的怪问题落到 `other`。
3. **先消解、再子流程**:问「这句合不合律」→ 日志可观测到①指代消解/改写产出(含补全结果)②随后进入判定子流程、取到诗作数据并检索到 policy 条款。
4. **前端卡片回填**:浏览器里**不说哪首诗**只问「这句合不合律」→ 聊天页弹出**诗词卡片**;点选后子流程**接着走完**并给出判定。

## 2. 技术栈(用户定死,不得自行更换)

| 项 | 结论 | 说明 |
|---|---|---|
| 上游模型 | **延用现有聊天上游**(DeepSeek,`.env`),**无新增组件** | 需求明确"无新增组件,延用现有聊天上游" |
| 意图识别路线 | **LLM prompt 路线** | 不训分类模型、不引入 BERT |
| 编排层 | 延用 **LangGraph**(`StateGraph` + `AsyncSqliteSaver`) | Ch04 已落地;本章只加节点/边 |
| 检索 | 延用 Ch03(`embeddings.embed` + `vector_store.search` + `knowledge.get_chunk`) | 新增 `source_type="policy"` 一类;`search` 单次只吃一个 source_type,故多查询需多次调用后合并 |
| 落库 | MySQL(唯一权威源);新增极简表 `corrections` | 需求原文的"退款单"落到此表 |
| 前端 | 原生 HTML/CSS/JS(沿用 `static/chat.html`) | **Vibe Coding 例外**(用户原话:前端"我描述效果你改",不套 brainstorm/TDD/code review) |

## 3. 意图识别与分流

### 3.1 七类 + `other`(共 8 个选项,枚举成选择题)

| # | 意图标签 | 出口 | 行为 |
|---|---|---|---|
| 1 | `poem_explain`(诗词释义/赏析/**典故出处**) | **知识类** | 强制 RAG → 置信度闸 → 证据足才传 Agent(Ch04 已有) |
| 2 | `find_poem`(查诗词,含按朝代找) | **业务类** | 不预检索,直传 Agent |
| 3 | `find_poet`(查诗人) | **业务类** | 同上 |
| 4 | `poem_meter`(格律/体裁合规) | **判定子流程** | 槽位检查 → 取诗作数据 → Query 扩写 + 强制检索 `policy` 条款 → Agent 只判"合不合律" |
| 5 | `poem_verify`(诗作校勘核对) | **判定子流程** | 同上(规则文档换成校勘准则) |
| 6 | `complaint`(纠错/不满) | **投诉类** | 不进 Agent,安抚话术 + `["handoff","feedback"]` 两个按钮(Ch04 契约不变) |
| 7 | `chitchat`(闲聊) | **闲聊类** | 不调模型/工具,固定话术 |
| + | `other`(**其他**兜底) | **其他类** | 交主力 Agent 做**需求澄清**,不硬塞业务意图 |

**相对 Ch04 的意图集调整(用户拍板:归并)**:Ch04 的 `reference_lookup`(典故/出处)**并入** `poem_explain`;`find_dynasty`(查朝代)**并入** `find_poem`。两个工具(`query_poem` 按朝代结构化查、诗词检索)**均保留不动**,Agent 仍可自主调用;只是标签不再单列,腾出的位置给两条判定型意图。

**分流规则硬编码**在 `workflow/intent.py` 的 `INTENT_TO_ROUTE`(七类 → 六出口),不交给模型决定;意图识别只负责产出标签 + 置信度。

### 3.2 意图识别 prompt 四件套(逐条对应需求)

1. **选择题**:把七类 + `other` 枚举成选项,让模型"从选项里选"而非自由生成;
2. **强制 JSON**:只输出 `{"intent": "<标签>", "confidence": <0~1 小数>}` 两个字段,不要任何解释;
3. **边界 few-shot**:给易混对样例,至少覆盖
   - 「这句合不合律 / 这首是不是七律」→ `poem_meter`(不是 `poem_explain`);
   - 「作者是不是搞错了 / 原文是不是有讹字」→ `poem_verify`(不是 `complaint`);
   - 「这首诗什么意思 / 举头望明月出自哪首诗」→ `poem_explain`;
   - 「帮我找一首写月亮的」→ `find_poem`;「李白是什么朝代的」→ `find_poet`;
   - 「答得不对,我不满意」→ `complaint`;「今天天气不错」→ `chitchat`;
   - 与诗词无关或说不清的(「帮我写个 Java 排序」)→ `other`。
4. **`other` 兜底**:拿不准就归 `other`。

**解析失败/模型异常** → 归 `other` 且 `confidence=0`(Ch04 是降级 `chitchat`;本章改为 `other`,理由:需求明确"拿不准就归它,别硬塞进业务意图"),并打告警不阻断。

**置信度只用不判**:本章只把 `confidence` 记录下来(写进 trace 帧与结构化日志),**不据此改变分流**(阈值与升级逻辑留待 §11 的降级路)。

### 3.3 六出口

`knowledge` / `business` / `ruling`(判定子流程)/ `complaint` / `chitchat` / `other`。

## 4. 图骨架(相对 Ch04 的变化)

```
START
 → resolve       (正式版:LLM + 本会话历史 → 指代消解 + Query 改写;
                   已完整则原样透传。输出 query / changed)
 → after_resolve (条件边:有待回填槽位 → ruling 续跑;否则 → classify)
 → classify      (正式版:四件套 prompt → {intent, confidence})
 → route         (硬编码六出口)
    ├ knowledge → retrieve(三源合并) → gate ─足→ agent  ┐
    │                                       └不足→ log   │
    ├ business  → agent                                 │
    ├ ruling    → slot_check ─缺对象→ log(并下发 pick_poem)│
    │                        └有对象→ expand_query(JSON) │
    │                                 → retrieve_policy   │
    │                                 → agent(只判能不能) │
    ├ complaint → log(安抚话术 + 两按钮)                 │
    ├ chitchat  → log(固定话术)                          │
    └ other     → agent(需求澄清)                        │
 → log → END
```

**与 Ch04 的骨架差异**:新增 `slot_check` / `expand_query` / `retrieve_policy` 三个节点、`ruling` 与 `other` 两个出口,以及 `after_resolve` 条件边(支撑两段式续跑)。Ch04 的 `retrieve`(三源合并)/`gate`/`agent`(ReAct)/`log` 全部不动。

**知识类不做扩写**(需求原话:只对退款退货、售后这类高频、容错低的核心场景做,简单 FAQ 不扩)。

## 5. 两段式续跑(槽位回填,用户拍板方案 A)

需求原话:「执行阶段弹订单选择器让用户点选回填」「点选后自动回填、流程接着走」。

- **第一段**:`POST /agent/workflow {sessionId, message}` 跑到 `slot_check` 判定"缺对象"即收尾,**不发 token**;回答为一句**固定确认提示**(如「先确认一下,你说的是哪首诗?」)并附带 SSE 一帧
  `action` → `{"action": "pick_poem", "candidates": [{"poemId":..,"title":..,"writer":..,"dynasty":..,"score":..}, ...]}`(`done` 里带 `"status": "awaiting_slot"`)。
  (提示话术用固定常量,避免"空回答"让前端显示 `(空回复)`。)
- 同时把"待回填"写进 state(`pending_subflow=true` / `subflow_kind` / `candidates`)——Ch04 的 checkpointer 已能持久化 state,天然可存。
- **第二段**:用户点选卡片 → `POST /agent/workflow {sessionId, message:"", selectedPoemId: <int>}` → 图从 `resolve` 进入,`after_resolve` 见到 `pending_subflow` 直接走 `ruling` 的"已取对象"分支(跳过消解/分类),接着检索 policy、交 Agent 判定 → 正常 SSE 输出 `token*` + `done`。

**不选 LangGraph 官方 `interrupt()`/`Command(resume=...)` 的理由**:与"一次请求一条 SSE"的既有契约差异大(要么长连接挂起等用户点选,要么照样拆两段),且需额外核 API,复杂度和返工风险更高;两段式零新依赖且与现有契约兼容。

## 6. 状态字段(在 Ch04 `WorkflowState` 上新增)

| 字段 | 通道类型 | 说明 |
|---|---|---|
| `history` | **普通通道**(手工累积 + 截断) | 本会话最近 **3 轮**(常量 `HISTORY_TURNS = 3`,单一来源)的 `{role, content}` 记录(仅 user 原问 + 最终回答),供指代消解用;每轮由 `log_node` 追加并裁到最近 3 轮 |
| `resolved_input` / `query_changed` | 普通 | 消解/改写后的检索用问题(**复用 Ch04 既有 `resolved_input` 通道,不另开 `query` 字段**,见 §11);`query_changed` 标记是否真的改写过 |
| `intent` / `confidence` | 普通 | 意图标签与模型自评置信度(本章只记录,不据此分流) |
| `subflow_kind` | 普通 | `meter` / `verify`(哪条判定子流程) |
| `slot_target` | 普通 | 已确定的对象(诗作 `source_id` + 标题等);空 = 缺槽位 |
| `candidates` | 普通 | 缺槽位时下发的候选诗词列表 |
| `pending_subflow` | 普通 | 是否处于"等用户回填"状态(续跑入口判据) |
| `expanded_queries` | 普通 | 扩写出的多条查询(仅 ruling 用) |
| `policy_hits` | 普通 | 检索到的 policy 条款(供 Agent 判定依据) |
| `correction_categories` | 普通 | 纠错单固定类目(下发前端做下拉) |

`messages` / `tool_trace` 沿用 Ch04 语义(`messages` 是 add reducer 保留跨轮历史;`tool_trace` 每轮由 `resolve_node` 归零)。**新增字段全部在 `_PER_TURN_RESET` 里归零**,避免 Ch04 踩过的跨轮状态泄漏问题重演。

## 7. 模块划分

| 模块 | 动作 | 职责 |
|---|---|---|
| `workflow/resolve.py` | Create | 指代消解 + Query 改写(LLM + `history`;已完整则透传) |
| `workflow/expand.py` | Create | Query 扩写(强制 JSON `{"queries": [...]}`)+ 多查询检索去重合并 |
| `workflow/ruling.py` | Create | 判定子流程共用逻辑:槽位检查(取对象)/ 检索 policy 条款;两条子流程共用,差异只在 `subflow_kind` |
| `workflow/intent.py` | Modify | 七类 + `other` 标签、六出口硬编码映射 |
| `prompts.py` | Modify | 分类四件套 prompt / 消解改写 prompt / 扩写 prompt / 对象抽取 prompt |
| `workflow/state.py` | Modify | §6 新增字段 + 归零清单 |
| `workflow/nodes.py` | Modify | 新增 `slot_check` / `expand_query` / `retrieve_policy` 节点、`after_resolve` 条件边、六出口路由 |
| `workflow/graph.py` | Modify | 接新节点与新边 |
| `knowledge.py` | Modify | `source_type="policy"` 支持;`list_pending(source_type=...)` 过滤(只补 policy 用) |
| `build_kb.py` | Modify | 新增 `collect_policy_chunks` + `--only` 过滤(只切/只嵌 policy,避免连带把 1.1 万条 pending 诗词全嵌) |
| `chunking.py` | Modify | 新增 `chunk_policy_doc`(复用通用 `chunk_section`,按 markdown 标题层级切子节) |
| `main.py` | Modify | 续跑入参 `selectedPoemId`、`pick_poem` 帧、`POST /agent/correction` 纠错单落库、trace 帧补 `confidence`/`query_changed` |
| `static/chat.html` | Modify | 可点选诗词卡片 + 纠错/复核单表单(类目下拉) |
| `policy_docs/` | Create | `meter_rules.md`(格律·词牌规则)、`collation_rules.md`(校勘准则)——纯文档语料 |
| `corrections` 表 | Create | 见 §9 |

## 8. 判定子流程细节

两条子流程共用 §7 的 `ruling.py`,差异只有 `subflow_kind` + 检索哪类 policy:

1. **`slot_check`**:用 LLM 从 `query` 里抽取**对象**(诗题 / 诗句片段);抽不到 → 判"缺槽位" → 用 `query` 做一次 `poem` 源向量检索取 top-k 作为候选卡片下发,收尾等回填。
2. **取对象数据**:命中对象后用 Ch03 既有能力取该诗作的**权威数据**(`knowledge.get_chunk` + `potry`/`writer` 回查),塞进 Agent 的 prompt。
3. **`expand_query`**:把 `query` 泛化成 2–5 条侧重点不同的检索查询(强制 JSON,字段只有 `queries`);解析失败 → 降级为**单条原 query**(不阻断)。
4. **`retrieve_policy`**:对每条查询各查一次 `policy` 源,按 `chunk id` **去重**后按相似度降序合并;取 top-k 作为"规则条款依据"。
5. **交 Agent 判定**:prompt 明确"只判"能不能/对不对",依据 = 对象数据 + 规则条款;**证据不足要如实说不确定**,不得编造。
6. 判定子流程跑完即回复附带 `action: open_correction_form` + `correction_categories`(固定类目)—— **总是提供入口**(不再限于"数据存疑/与权威冲突"),点不点由用户决定(见 §11 实现口径留痕)。

## 9. 落库

- **新增** 极简表 `corrections`: `id` / `userid`(无登录态留空)/ `poem_id`(可空)/ `category`(固定类目之一)/ `detail`(text,用户补充)/ `session_id` / `creatime`。归属新的 `AppBase`(与 `feedback` 同 Base,`init_db` 已 `create_all`)。
- **固定类目**(单一来源常量,前后端共用):`格律错误` / `作者张冠李戴` / `原文有误` / `译文有误` / `赏析不认同`。
- **复用** Ch04 的 `feedback` 表与 `POST /agent/feedback`(投诉类"提交反馈"按钮) —— 二者并存,互不影响。
- **结构化日志**(沿用 Ch04 观测点格式,补两个字段,便于验收③):
  `[wf] intent=<意图> conf=<0~1> route=<出口> gate=<pass|insufficient|skip> score=<相似度或-> iters=<迭代数> tokens=<token数> elapsed=<毫秒>`
  另在 `resolve` 后补一行:`[wf] resolve changed=<true|false> query=<改写后问题>`;子流程补一行:`[wf] subflow kind=<meter|verify> target=<诗作标题或-> policy=<命中条数>`。

## 10. 错误处理与降级

- 消解/改写失败 → **原样透传**原文(`query_changed=false`)+ 告警,不阻断;
- 意图识别 JSON 解析失败/模型异常 → `other` + `confidence=0` + 告警;
- 扩写 JSON 解析失败 → 降级为单条原 query;
- policy 检索失败/为空 → 视为"规则条款不足",Agent 如实说明不确定,**不编造**;不写 pending(那是 Ch04 知识类闸的职责,本章不扩用);
- 槽位抽取失败 → 按"缺槽位"处理(下发候选卡片),不硬猜;
- 纠错单写入失败 → 接口返回错误、前端提示,不影响对话;
- 单请求异常 → SSE 补 `error` 帧,服务不崩;日志不打密钥、异常串截断 `[:200]`。

## 11. 已确认决策与偏差留痕

| 决策点 | 结论 |
|---|---|
| 章节编号 | 需求写"第6章 / ch06.md" → 按项目实际顺序记为 **Ch05 / dev-notes/ch05.md**(用户确认) |
| 领域映射 | 客服模板 → **诗词域等价物**(用户确认):订单↔诗作对象、政策条款↔格律·校勘规则、退款单↔纠错单、订单选择器↔诗词卡片 |
| 七类意图调整 | **归并**(用户确认):`reference_lookup` 并入 `poem_explain`;`find_dynasty` 并入 `find_poem`。工具全留,Agent 仍可调 |
| 两条判定子流程 | **格律/体裁合规 + 诗作校勘核对**(用户确认) |
| 续跑机制 | **两段式**(用户确认):第一段下发 `pick_poem` + 候选;点选后第二段带 `selectedPoemId`,经 checkpointer 的 state 续跑。不用官方 `interrupt()` |
| 模型分层 | **本章只做单级大模型 + 预留口子**(用户确认):只记录 `confidence`,阈值与"小模型升级大模型"逻辑留后续。⚠️ 与需求"成本吃紧时走降级路"的差额**已留痕** |
| 纠错单落点 | **新建 `corrections` 表**(用户确认),不复用 `feedback` |
| 落 `other` 而非 `chitchat` | ⚠️ **偏离 Ch04**:Ch04 分类解析失败降级 `chitchat`,本章改为 `other`(需求"拿不准就归它"),需同步改 Ch04 的 `classify` 相关单测期望 |
| `resolve` 新增 `changed` 标记 | 需求原文只说"补全/改写/不强行改写",`changed` 是为**可观测 + 评估集断言**而加的最小标记 |
| `history` 为何独立成通道 | 需求要"结合对话历史";`messages` 通道混有 ReAct 内部消息(AIMessage 带 tool_calls 等),直接喂给消解场景既脏又贵,故新开 `history` 通道只存 user 原问 + 最终回答,并裁到最近 3 轮(顺带避免无界增长) |
| ⚠️ 需同步改的既有测试 | ① `tests/test_workflow_intent.py` 断言 Ch04 的七类标签(含 `reference_lookup`/`find_dynasty`)→ 需按 §3.1 归并后的新标签表更新;② `tests/test_workflow_nodes.py` 的 `classify` 降级期望由 `chitchat` 改为 `other`;③ `tests/test_workflow_graph.py` 的分流分支需覆盖新增的 `ruling`/`other` 出口 |
| 范围规模提醒 | 本章体量明显大于 Ch04(6 个 LLM 环节 + 新语料入湖 + 两段式续跑 + 前端两类新 UI)。仍按用户要求做成**一份 spec 一章**,但在实现计划里把「**语料 + 评估集**」与「**代码**」分成两组排期,便于中途单独验收 |
| 前置条件 | ⚠️ 实现前需先**启动 MySQL**(本机 2026-10-19 重启后 3306 未监听);建 policy 索引时需**停掉 API 服务**(Milvus Lite 独占文件锁) |
| 实现口径:**不新增 `query` 状态字段** | `resolved_input` 已是同一语义的既有通道(retrieve_node / agent_react 都在消费),再开 `query` 会双写漂移;只新增 `query_changed` 标记 |
| 实现口径:**纠错单入口总是挂**(已请示用户获批) | 判定子流程跑完即给出「提交纠错单」入口 + 固定类目下拉,点不点由用户决定;spec §8.6 原有的"若数据存疑/与权威冲突才附带"条件语气**改为"总是提供入口"** |

## 12. 测试与验收策略

**可单测(TDD)**:
- `intent.py`:七类 + `other` 标签齐全、六出口映射合法;
- `resolve.py`:JSON 解析、"已完整问题原样透传"分支、失败降级透传(用 stub LLM);
- `expand.py`:`{"queries":[...]}` 解析、解析失败降级单条、多查询检索**去重合并**(用 fake store);
- `ruling.py`:槽位检查命中/未命中、候选卡片构造、policy 检索去重;
- `graph.py`:`after_resolve` 续跑分支、六出口各走对分支(用 stub LLM/工具,`InMemorySaver`);
- `corrections` 落库:字段映射、行数 +1、类目校验;
- `knowledge.list_pending(source_type=...)` 过滤;
- `build_kb` 的 `collect_policy_chunks` 幂等(source_id 稳定映射)。

**纯 Prompt / 数据类 → 标注样例替代 TDD**(按用户工作要求):
- **意图识别评估集**:≥30 条(七类 + `other`,含边界与怪问题),断言 intent 准确率 + JSON 可解析率;
- **指代消解评估集**:≥15 条多轮(含「它/这句/那首」指代,以及"已完整问题应原样透传"的负例),断言补全正确率 + 透传率;
- **Query 扩写评估集**:≥10 条(仅 ruling 场景),断言 JSON 可解析率 + 生成 2–5 条且语义不重复;
- **policy 语料质量**:人工核对规则条款文档的准确性与结构(纯数据任务)。

**端到端(验收)**:§1 四条逐条真跑,含结构化日志观测与浏览器真机卡片交互。

**依赖新增**:**无**。所有库(含 LangGraph)已在 Ch04 落地并钉版本。
