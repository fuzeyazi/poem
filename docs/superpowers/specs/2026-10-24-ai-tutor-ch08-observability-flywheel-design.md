# AI 伴学系统 · 第八章(观测 · 成本 · 数据飞轮 · 审核后台 · 评估流水线)设计

日期:2026-10-24
状态:brainstorm 分节通过(第 1–3 节已确认);Langfuse 部署暂缓,先实现飞轮与审核后台
落地位置:`potry-ai-agent/`(延续 Ch01–Ch07,就地扩展)
章节编号:需求原文写 `dev-notes/ch09.md`;仓库下一章为 Ch08,经用户确认**记为 Ch08**,留痕 `dev-notes/ch08.md`。

## 1. 目标与范围

本章给客服系统补上三件事:

1. **可观测与成本**:Langfuse 自部署接入,完整 trace 树 + 按意图的 token 花费统计。
2. **数据飞轮**:三个入口(检索置信度闸 / 模型自评 / 用户 👎)把答不上的问题送进问题池,带召回片段快照;后台异步完成标准化、查重、入待审队列;人工审核通过后写入知识库。
3. **评估流水线**:复用 Ch04 评估集,定期计算 Recall@K / MRR / Faithfulness,落 `eval_runs` 表并展示趋势。

### 用户已确认的决策

| 决策点 | 结论 |
|---|---|
| 章节编号 | 记为 Ch08,留痕 `dev-notes/ch08.md` |
| Langfuse 部署 | 本机 Docker Compose 自部署;当前 WSL 未装/下载超时,**部署与验收 1/5/6 暂缓**,代码先按环境变量接入 |
| 问题池 | 沿用 `pending_questions` 并加列,不新建 `low_confidence_questions` |
| RAG 评估集 | 扩展现有 `evals/chat_eval_cases.md` 加检索金标与 Faithfulness 要点 |
| 精排信号 | 不新增 reranker,用现有稠密检索分做代理 |
| 总体架构 | 请求内轻量入池 + 后台异步飞轮 |
| 👎 入口 | 每条助手回答下加 👍/👎 |
| 模型自评 | 回答后独立一次自评 LLM |
| 成本报表 | 后台页面/接口 |
| 审核页 | 独立 `/admin/review` 页 |
| 评估触发 | APScheduler 定时 + 手动脚本 |
| 审核编辑 | 允许编辑标准化问题/答案后通过 |

### 非目标

- 不做低置信度问题按主题归类的微调分类器。
- 不做审核后台登录鉴权(仅本地演示)。
- 不新增 cross-encoder 精排模型;`evidence_confidence` 用检索分代理。
- 不接 Langfuse Cloud;不把链路数据发到外部。

## 2. 需求→设计对照

| 需求 | 落地 |
|---|---|
| 1 Langfuse 接入 + 完整 trace 树 | §3(部署暂缓;`observability.py` + CallbackHandler + `@observe` 节点) |
| 2 意图元数据 + token 成本 | §3.3(Agent generation metadata + trace 根元数据 + `/api/admin/cost`) |
| 3 三入口入池 + 快照 + 新列 | §4(`pending_questions` 三列、`snapshot_hits`、闸升级、自评、👎) |
| 4 标准化/查重/待审队列/审核通过写库 | §5(`review_queue`、`flywheel.py`、审核 API、Ch03 落库) |
| 5 自动评估与趋势 | §6(`eval_runs`、评估脚本、定时任务、趋势接口) |
| 6 后台审核页 | §5.4(`/admin/review`) |
| 验收 1–6 | §9(1/5/6 依赖 Langfuse,暂缓) |

## 3. 可观测与成本(Langfuse,部署暂缓)

### 3.1 部署

- 官方 Docker Compose:web/worker + Postgres/ClickHouse/Redis/MinIO,默认 `http://localhost:3000`。
- 初始化组织/项目/API key,写入应用 `.env`:
  - `LANGFUSE_HOST=http://localhost:3000`
  - `LANGFUSE_PUBLIC_KEY`
  - `LANGFUSE_SECRET_KEY`
- 三项缺任一 → tracing 关闭并打印 `[langfuse] disabled: ...`;聊天不受影响。
- 当前 WSL 安装日志为“操作超时 / 正在下载 WSL 3.0.3”;需重试或重启后继续。**代码实现与验收分离**。

### 3.2 链路挂法

- `observability.py`:
  - `get_handler()` 懒加载 `langfuse.langchain.CallbackHandler`,环境不全返回 `None`。
  - `trace_turn(session_id, user_id, message)` 上下文管理器:创建 root observation(`name="chat-turn"`, `as_type="span"`, input=message),并 `propagate_attributes(session_id=..., user_id=..., trace_name="chat-turn")`。
  - `finish_turn(root, final)`:root.update(metadata={intent, route, gate, evidence_confidence}, output={answer})。
- `workflow/graph.py` 在编译产物上挂一次 `.with_config({"callbacks":[handler]})`;若包装后 `aget_state` 等图方法丢失,则改为在每次 `ainvoke` 的 config 注入,不换技术栈。
- 节点用 `@observe`:
  - `resolve/classify/route/retrieve/gate/agent/tool_node/log` 为 span;`retrieve` 标 `retriever`,`agent` 标 `agent`。
  - `ticket_confirm` 涉及 `interrupt`,不直接套 `@observe`(避免把中断记为错误),用手工 span 记录预览载荷。
- `retrieve_node` 输出包含命中 `title/writer/score/text`;`tool_node` 输出包含工具参数、结果摘要、耗时;Agent LLM 由 CallbackHandler 自动生成 generation(prompt/tool_calls/token usage/耗时)。

### 3.3 意图与成本

- `agent_node` 内用 `propagate_attributes(metadata={"intent": state.get("intent","")}, as_baggage=True)` 包住 LLM 调用,generation 带 intent。
- 回合结束 `finish_turn` 再把 `intent/route/gate` 写到 trace 根元数据。
- `GET /api/admin/cost?days=7`:用 Langfuse Observations API `type=GENERATION`、`fields=core,basic,usage,metadata`,按 `metadata.intent` 聚合 `totalUsage/totalCost`;返回 `{window, rows:[{intent, calls, tokens, cost}], total}`。
- Langfuse 不可达 → 503 + 明确 message;后台页显示“Langfuse 未就绪”。

## 4. 数据飞轮:问题池与三个入口

### 4.1 问题池契约

`pending_questions` 增加:

| 列 | 类型 | 说明 |
|---|---|---|
| `source_entry` | varchar(32) null | `retrieval_gate` / `model_self_eval` / `user_dislike` |
| `retrieved_snapshot` | text null | JSON:Top5 命中快照 |
| `matched_review_id` | bigint null | 对应 review_queue.id;非空即已处理 |

- `add_pending_question(question, session_id=None, source_entry="retrieval_gate", retrieved_snapshot=None) -> int`。
- `snapshot_hits(hits, top_n=5) -> str`:每项 `{id, source_type, title, writer, dynasty, score, text[:400]}`,`ensure_ascii=False`;无检索返回 `"[]"`。
- 入池只做一次 DB 写入;标准化/查重异步。

### 4.2 入口一:证据置信度闸

- 位置不变:知识类检索后、Agent 前。
- 代理信号(现有稠密检索分):
  - `top1` 截断到 [0,1];
  - `margin = max(0, top1-top2)`,`margin_norm = min(margin/0.20, 1)`;
  - `effective_count = 分数 >= EVIDENCE_MIN_SCORE 的命中数`,`count_norm = min(effective_count/3, 1)`;
  - `evidence_confidence = 0.5*top1 + 0.3*margin_norm + 0.2*count_norm`。
- 阈值 `EVIDENCE_CONFIDENCE_THRESHOLD`:由 `evals/calibrate_confidence.py` 在扩展评估集上扫描 0.30–0.95、按 F1 选定;输出写 `.env`,代码只读配置。
- 不足:`gate_status=insufficient`、兜底话术、`fallback_reason=insufficient_evidence`、`evidence_confidence` 与 `gate_signals` 入 state;写池(`retrieval_gate`)带 Top5 快照并 schedule。
- 充足:`gate_status=pass`,进 Agent。

### 4.3 入口二:模型自评

- `self_eval.py` + `SELF_EVAL_PROMPT`:输入问题、回答、Top5 证据,输出 JSON `{insufficient, reason}`;仅在回答**明确承认知识不足**时 `insufficient=true`。
- `main.py` 在 `ainvoke` 返回后 `asyncio.create_task(self_eval_after_turn(final, session_id))`,不进图、不延迟 SSE。
- 跳过条件:无 answer、`gate_status=="insufficient"`、`pending_subflow`、`route in (chitchat, complaint)`、`fallback_reason=="agent_error"`。
- 判定不足 → 写池(`model_self_eval`)带 `final["retrieved"]` Top5 快照并 schedule;LLM 失败只告警。

### 4.4 入口三:聊天页 👎

- 每条助手回答下加 👍/👎;👍 本地致谢,不落库。
- 👎 → `POST /agent/feedback/negative {sessionId, message}`:
  - `aget_state(config)`;若 `values["user_input"] == message`,取 `values["retrieved"]` 做快照;否则空快照(尽力回捞)。
  - 写池(`user_dislike`)并 schedule;返回 `{ok, pendingId}`。
  - workflow 未就绪 503;写库失败 500。

### 4.5 后台处理

- `flywheel.schedule(pending_id)`:当前事件循环 `asyncio.create_task`;无循环则由定时任务兜底。
- APScheduler 每 `FLYWHEEL_DRAIN_MINUTES=5` 分钟扫描 `matched_review_id IS NULL` 的行,逐条处理。
- 同一进程用 `asyncio.Lock` + 事务内复查;`matched_review_id` 非空即幂等返回。

## 5. 飞轮流水线与审核后台

### 5.1 review_queue

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | bigint PK | |
| `standard_question` | text | 标准化 FAQ 问题 |
| `example_answer` | text | 示例答案(待人工核准) |
| `occurrences` | int default 1 | 出现次数 |
| `status` | varchar(16) default pending | pending/approved/rejected |
| `approved_answer` | text null | 审核后的核准答案 |
| `created_at` / `updated_at` | datetime | |

不挂外键。`pending_questions.matched_review_id` 指向它。

### 5.2 流水线 `flywheel.py`

`process_pending(pending_id)`:

1. 读 pending;`matched_review_id` 非空 → 返回。
2. 标准化 `STANDARDIZE_PROMPT`:输入原话 + 快照片段,输出 `{standard_question, example_answer}`;示例答案标注“待人工核准”。
3. 查重 `DEDUP_PROMPT`:输入新标准问题 + `status=pending` 队列最多 50 条 `{id, question}`,输出 `{matched_id}`;只有同义才合并。
4. 命中 → `occurrences += 1`;未命中 → 新建 review 行(`occurrences=1`)。
5. `mark_pending_matched(pending_id, review_id)`。
6. 任一步失败 → 日志 + 保持未匹配,定时任务重试。

### 5.3 审核 API

- `GET /api/admin/review?status=pending&limit=50&offset=0`
- `GET /api/admin/review/{id}`:详情 + 关联 pending 行(原话、入口、快照解析)
- `POST /api/admin/review/{id}/approve` body `{standard_question?, approved_answer}`
- `POST /api/admin/review/{id}/reject`
- 非 pending 的 approve/reject 返回 409。

审核通过写库:

1. `upsert_chunks([{source_type:"qa", source_id:f"review-{id}", section:"faq", seq:0, chunk_text:"Q: ...\nA: ...", raw_text:..., title:standard_question}])`
2. `get_chunk_id(...)`
3. `embeddings.embed([text])` → `vector_store.upsert([chunk_id], [vec], [metadata])` → `mark_embedded([chunk_id])`
4. 成功后才置 `approved` 并保存 `approved_answer`;embed/向量库失败返回 503、保持 pending,可重试。
- Milvus 被建库进程占用同样 503。

### 5.4 后台页 `/admin/review`

- 左侧队列表(标准化问题、次数、示例答案、状态),右侧详情。
- 详情:关联用户原话 + 入池入口 + Top5 快照(title/writer/dynasty/score/text);空快照显示“该轮未走检索”。
- 通过前可编辑标准问题与核准答案;通过/驳回按钮;操作后刷新列表。
- 独立页面,不改聊天页布局(聊天页只加 👍/👎)。

## 6. 自动化评估流水线(设计已定,本批实现暂缓)

- 扩展 `evals/chat_eval_cases.md`:每条加 `gold_titles/gold_writers` 与 `faithfulness_points`,并补不足样本供置信度校准。
- `eval_pipeline.py`:
  - 检索段:对每条 case 调 `retrieve_evidence`,算 `Recall@K`、`MRR`。
  - 生成段:用真实图跑一遍(独立 session),再用 LLM-as-judge 按 `faithfulness_points` 判 `Faithfulness`。
  - 每轮写 `eval_runs`:id、trigger(manual/cron)、case_count、metrics JSON、created_at。
- `GET /api/admin/eval-runs?limit=10`:返回历史分数;后台页画三条趋势线。
- `scheduler.py` 加 `EVAL_CRON` 定时任务;保留 `evals/run_ch08_eval.py` 手动入口。
- 验收 6:至少跑两轮,趋势可比较。
- **本批(飞轮+审核)不实现本节**,等 Langfuse/评估批一起做。

## 7. 错误处理与降级

- 入池失败(闸/自评)只告警,回答不受影响;👎 写库失败返回 500。
- 标准化/查重失败保持未匹配,定时重试;不半成功建行。
- 审核通过必须等向量写入成功;失败保持 pending。
- Langfuse 不可达只告警;成本接口 503。
- 自评 LLM 失败不落池,不阻断聊天。
- 所有后台任务捕获异常并打印,不打断调度器。

## 8. 测试策略

- 可单测部分走 TDD:存储列/迁移、快照序列化、置信度公式、闸写池、飞轮标准化/查重/幂等、审核 API/写库、👎 接口。
- 纯 Prompt:标准化/查重/自评各配标注样例,真实模型跑一遍,记录结果;工单/审核页前端走 Vibe Coding 例外,不写 TDD、不做 code review。
- 全量回归保持既有 `pytest` 全绿。

## 9. 验收

| # | 场景 | 本批状态 |
|---|---|---|
| 1 | Langfuse 任意请求完整链路 | 暂缓(依赖 WSL/Docker) |
| 2 | 知识库没有的问题 → 兜底 + 待审队列 + 详情含原话/召回片段 | 本批实现并验收 |
| 3 | 审核通过后同一问题再问能答对 | 本批实现并验收 |
| 4 | 聊天页 👎 → 入池 → 标准化查重 → 待审队列 | 本批实现并验收 |
| 5 | 按意图 token 花费 | 暂缓(依赖 Langfuse) |
| 6 | 评估流水线两轮趋势 | 暂缓(下一批) |

## 10. 模块与文件

```text
flywheel.py          FlywheelService / snapshot_hits / schedule / drain(ReviewQueue 模型放 knowledge.py)
self_eval.py         自评 prompt 调用与入池
review_api.py        /api/admin/review 路由
knowledge.py         PendingQuestion 加列 / ReviewQueue / 审核写库辅助 / ensure_ch08_schema
workflow/confidence.py  evidence_confidence 信号
workflow/nodes.py    gate_node 升级 + 快照入池
workflow/deps.py     flywheel 依赖
main.py              装配、👎 接口、后台页路由、自评后台任务
scheduler.py         flywheel drain 定时任务
static/chat.html     👍/👎
static/admin_review.html  审核后台
evals/               chat_eval_cases 扩展、calibrate_confidence.py、自评标注样例
tests/               存储、飞轮、闸、审核 API、👎
```

## 11. 决策留痕

- 问题池沿用 `pending_questions`,避免新旧两套池与迁移。
- 置信度用检索分代理,不新增 reranker;阈值必须由评估集校准。
- 飞轮异步化,入口只落库;审核通过必须向量写入成功才置 approved。
- 审核页本期不做鉴权。
- Langfuse 部署受阻,验收 1/5/6 明确标记暂缓,不伪造通过。
