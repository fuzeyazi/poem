# Ch05 · 分流器正式版(指代消解 · Query 改写/扩写 · 意图识别 · 分流精化 · 槽位处理)· 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Ch04 里**占位的分流器**做成正式版:指代消解 + Query 改写/扩写、八类意图 LLM 识别(四件套 prompt)、六出口硬编码分流、两条判定子流程(格律合规 / 校勘核对)、缺槽位下发诗词卡片的两段式续跑、纠错单落库与前端卡片/表单。

**Architecture:** 沿用 Ch04 的 `StateGraph` + `AsyncSqliteSaver`,只新增节点与边。`resolve` 升级为 LLM 消解/改写(已完整则透传);新增条件边 `after_resolve` 支撑「缺槽位→下发卡片→点选后第二段续跑」;`classify` 升级为八类 + `{intent, confidence}` 四件套 prompt,解析失败降级 `other`;`route` 改为六出口硬编码;新增 `ruling` 子流程三节点(`slot_check` → `expand_query` → `retrieve_policy`)后交主力 Agent 只做「能不能/对不对」判定;新增知识类型 `policy`(纯文档语料,检索侧现查现用)与 `corrections` 表。

**Tech Stack:** Python 3.11 · FastAPI · LangChain 1.6.10 · LangGraph 1.2.16 + `AsyncSqliteSaver` · MySQL 8.4 · Milvus Lite + BGE-M3(复用 Ch03)· 原生 HTML/CSS/JS 前端。**无新增依赖**。

**权威 spec:** [2026-10-19-ai-tutor-ch05-router-formal-design.md](file:///e:/javatexts/poetry-spring2/docs/superpowers/specs/2026-10-19-ai-tutor-ch05-router-formal-design.md)

---

## 计划期已核实的事实(执行时直接用,不必重查)

| 项 | 结论 | 来源 |
|---|---|---|
| 测试基线 | **199 passed**(本次实测,命令见下方环境备忘) | 实测 |
| `chunk_section(meta_prefix, section, body, chunk_size, overlap)` | **通用**切分器,可直接复用于 markdown 规则文档按子节切块 | 已读 `chunking.py` |
| `KnowledgeStorage.list_pending(limit)` | 只按 `status='pending'` 过滤,**无 source_type 过滤** → 必须加参数,否则 `build_kb` 会把 1.1 万条 pending 诗词一起嵌 | 已读 `knowledge.py` |
| `vector_store.search(vector, topk, source_type)` | **单次只吃一个 source_type** → 多查询检索需多次调用后按 chunk id 去重合并 | 已读 `vector_store.py` |
| `KnowledgeChunk.source_type` | `String(16)` → `"policy"`(6 字符)**无需改表** | 已读 `knowledge.py` |
| `AsyncSqliteSaver` | Ch04 已落地;本章不动 checkpointer | 已读 `workflow/graph.py` |
| `agent_react._seed_messages` | 每**轮**首个迭代(`iterations==0`)重新播种 → 判定子流程的「诗作数据 + 规则条款」可在此按 `subflow_kind` 分支注入 | 已读 `workflow/agent_react.py` |
| `_PER_TURN_RESET` | 现位于 `workflow/nodes.py`。**`resolve.py` 也要用它**,若从 nodes 导入会与 `nodes→resolve` 形成循环导入 → 必须**上移到 `workflow/state.py`** | 已读 `workflow/nodes.py` |
| `messages` 通道 | `operator.add` 累积、**不归零** → 跨轮保留;本章新增字段一律进 `PER_TURN_RESET` 归零(Ch04 踩过跨轮泄漏) | 已读 `workflow/state.py` |
| MySQL 3306 | ⚠️ **未监听**(2026-10-19 重启导致)。**T2(语料入库)与 T13(验收)前必须先拉起 MySQL** | 实测 |
| Milvus Lite | 进程独占文件锁 → **建 policy 索引({--only policy})时必须停掉 API 服务** | 已读 `vector_store.py` |
| 诗词库进度 | 约 50%(embedded 11542 / pending 11607)→ 只用 `--only policy` 过滤嵌,不牵连那 1.1 万条 | dev-notes/ch05.md 阶段 1 |

**环境备忘:** 工作目录 `e:\javatexts\poetry-spring2`,服务目录 `potry-ai-agent/`;解释器 `.\.venv\Scripts\python.exe`;**PowerShell 5 不支持 `&&`,用 `;`**;测试必须**在 `potry-ai-agent/` 下用 `python -m pytest`**(`python -m` 才会把 cwd 加入 `sys.path`);git **只 add 明确列出的文件,严禁 `git add -A`**,提交信息单行。

---

## 相对 spec 的两处实现口径(执行时照此,勿来回改)

1. **不新增 `query` 字段,复用 Ch04 的 `resolved_input` 承载「消解/改写后的检索用问题」**,只新增 `query_changed` 标记。
   理由:spec §6 把 `query` 列为新字段,但 `resolved_input` 已是同一语义的既有通道(`retrieve_node` / `agent_react` 都在消费它);再开一个 `query` 会造成双写与漂移。`changed` 标记按 spec 保留。
2. **纠错单入口「总是挂」**(已请示用户并获批):判定子流程(格律合规 / 校勘核对)跑完即在回答下方给出「提交纠错单」入口 + 固定类目下拉,点不点由用户决定。spec §8.6 原为条件语气(「若判定结果为数据存疑/与权威冲突才附带」),实现改为**总是提供入口** —— 因为让模型输出可解析的判定信号既不可靠又不确定,而「用户自行决定是否提交」才是需求第 6 条的本意。

---

## File Structure

**新建:**

| 文件 | 职责 |
|---|---|
| `potry-ai-agent/policy_docs/meter_rules.md` | 格律·词牌规则语料(source_type=`policy`,source_id=1) |
| `potry-ai-agent/policy_docs/collation_rules.md` | 校勘准则语料(source_type=`policy`,source_id=2) |
| `potry-ai-agent/workflow/resolve.py` | 指代消解 + Query 改写(LLM + `history`;已完整则透传) |
| `potry-ai-agent/workflow/expand.py` | Query 扩写(强制 JSON `{"queries":[…]}`)+ 多查询检索去重合并 |
| `potry-ai-agent/workflow/ruling.py` | 判定子流程共用逻辑:槽位检查(取对象)/ 候选卡片 / policy 条款检索 |
| `potry-ai-agent/eval_ch05.py` | 评估集跑批(意图 / 消解改写 / 扩写 / 多轮串),纯 Prompt 类任务替代 TDD |
| `potry-ai-agent/tests/test_workflow_resolve.py` | T6 测试 |
| `potry-ai-agent/tests/test_workflow_expand.py` | T7 测试 |
| `potry-ai-agent/tests/test_workflow_ruling.py` | T8 测试 |

**修改:**

| 文件 | 改动 |
|---|---|
| `potry-ai-agent/chunking.py` | 新增 `split_markdown_sections` + `chunk_policy_doc`(复用 `chunk_section`) |
| `potry-ai-agent/knowledge.py` | `list_pending(source_type=…)` 与 `count_by_status(source_type=…)` 过滤 |
| `potry-ai-agent/build_kb.py` | 新增 `collect_policy_chunks` + `run(only=…, policy_dir=…)` + CLI `--only` |
| `potry-ai-agent/workflow/state.py` | §6 新增字段 + `PER_TURN_RESET`(自 nodes.py 上移)+ `HISTORY_TURNS` |
| `potry-ai-agent/workflow/intent.py` | 八类 + `other` 标签、六出口硬编码映射、`parse_intent_response` |
| `potry-ai-agent/prompts.py` | 意图四件套 / 消解改写 / 扩写 / 对象抽取 prompt + 判定指令 + 槽位话术 |
| `potry-ai-agent/app_storage.py` | 新增 `Correction` 模型 + `CORRECTION_CATEGORIES` + `AppStorage.add_correction` |
| `potry-ai-agent/workflow/nodes.py` | `resolve_node` 改正式版 + `slot_check`/`expand_query`/`retrieve_policy` 三节点 + `after_resolve`/`after_slot_check` + `after_route` 六出口 + `log_node` 补 `conf`/`history` |
| `potry-ai-agent/workflow/agent_react.py` | `_seed_messages` 增判定子流程分支(诗作权威数据 + 规则条款 + 只判能不能/对不对) |
| `potry-ai-agent/workflow/graph.py` | 接新节点与新边 |
| `potry-ai-agent/main.py` | 续跑入参 `selectedPoemId`、`pick_poem`/`open_correction_form` 帧、`POST /agent/correction`、trace 帧补 `confidence`/`queryChanged`/`subflowKind`/`policyCount` |
| `potry-ai-agent/static/chat.html` | 可点选诗词卡片 + 纠错单表单(类目下拉)+ 轨迹行更新 |
| `potry-ai-agent/tests/test_workflow_intent.py` | 按八类/六出口/`parse_intent_response` 更新 |
| `potry-ai-agent/tests/test_workflow_nodes.py` | `resolve_node` 改异步 + `classify` 降级 `other` + 新节点/新边用例 |
| `potry-ai-agent/tests/test_workflow_graph.py` | 覆盖 `ruling`/`other` 出口与续跑条件边 |
| `potry-ai-agent/tests/test_workflow_endpoint.py` | `pick_poem`/`open_correction_form` 帧、`done.status`、`/agent/correction` 落库 |
| `potry-ai-agent/tests/test_knowledge.py` | 补 `source_type` 过滤用例 |
| `potry-ai-agent/tests/test_chunking.py` | 补 markdown 子节切分用例 |
| `potry-ai-agent/tests/test_build_kb.py` | 补 `collect_policy_chunks` 与 `run(only=…)` 用例;`test_run_writes_chunks_and_reports_stats` 改传 `only="poem"` |

**不动:** `chat_service.py`、`memory.py`、`storage.py`、`vector_store.py`、`embeddings.py`、`mining.py`、`workflow/confidence.py`、`workflow/deps.py`、`naive_agent.py`、`tools/*`(业务工具一个不删)、Ch01–Ch04 中除上表外的测试。

**⚠️ 偏离 Ch04(已在 spec §11 留痕,需同步改既有测试):** 分类解析失败/模型异常降级由 `chitchat` 改为 **`other`**。

---

## 排期分组(用户要求:一份 spec 一章,但计划里把语料/评估集与代码分开)

- **组一 · 语料(可独立先行)**:T1(切分/建库支持 + 单测)、T2(真跑入库 + 人工核对)
- **组二 · 代码**:T3–T11
- **组三 · 评估集(依赖组二 prompt 定稿)**:T12
- **收尾**:T13(验收 4 条真跑 + code review + dev-notes + 交付)

---

# 组一 · 语料

## Task 1: 规则语料文档 + 切分/建库支持

**Files:**
- Create: `potry-ai-agent/policy_docs/meter_rules.md`
- Create: `potry-ai-agent/policy_docs/collation_rules.md`
- Modify: `potry-ai-agent/chunking.py`
- Modify: `potry-ai-agent/knowledge.py`
- Modify: `potry-ai-agent/build_kb.py`
- Test: `potry-ai-agent/tests/test_chunking.py`(追加)
- Test: `potry-ai-agent/tests/test_knowledge.py`(追加)
- Test: `potry-ai-agent/tests/test_build_kb.py`(追加 + 改一处)

- [ ] **Step 1: 写语料文档(纯数据)**

`potry-ai-agent/policy_docs/meter_rules.md`(逐字写入):

```markdown
# 格律·词牌规则

本文用于判定诗作在格律与体裁上「合不合规」。条款按子节组织,检索时按子节取值。

## 近体诗的四种体式

- 五言绝句:四句,每句五字,共二十字。
- 七言绝句:四句,每句七字,共二十八字。
- 五言律诗:八句,每句五字,共四十字。
- 七言律诗:八句,每句七字,共五十六字。

判定「是不是七律」需同时满足:八句、每句七字、且中间两联对仗。

## 平仄基本规则

- 一句之内平仄相间,不可连用三个平声或三个仄声字(三平调、三仄尾通常视为出律)。
- 联与联之间讲究「粘对」:下联出句第二字的平仄与上联对句第二字相同为「粘」,相反为「失粘」。
- 孤平是近体诗常见忌讳:除韵脚外仅一个平声字,多出现在「仄仄平平仄仄平」句式。

## 押韵规则

- 近体诗偶句押韵,首句可押可不押;一韵到底,中途换韵即为出韵。
- 通常押平声韵;押仄声韵多见于古体诗或词。
- 同一韵部内字方可通押,跨韵部通押需有「邻韵通押」的传统依据。

## 对仗规则

- 律诗的颔联(第三、四句)与颈联(第五、六句)必须对仗,绝句不强制对仗。
- 对仗要求词性、结构相称:名词对名词、动词对动词,数目、颜色、方位类词各自成对。
- 仅颔联对仗而颈联不对,或反之,属于「偷春格」「蜂腰格」等变体,需注明方不算误判。

## 古体诗与近体诗的区别

- 古体诗不限定句数与字数,可换韵,平仄不拘;近体诗句数、字数、平仄、押韵、对仗五项都有定式。
- 判定「合不合律」时先确认体裁:若为古体诗,则不看平仄粘对,只看押韵是否成立。

## 常见词牌的句式

- 词牌各有定句、定字、定韵。如《忆江南》单调二十七字,五句,三平韵。
- 同一词牌若有「又一體」(别体),按所依体式判定,不同体式之间不可混用句式。
- 词的分片(上片、下片)与句读需与词谱一致,句读移位通常视为不合律。
```

`potry-ai-agent/policy_docs/collation_rules.md`(逐字写入):

```markdown
# 校勘准则

本文用于判定诗作在作者、原文、朝代等「对不对」。条款按子节组织,检索时按子节取值。

## 校勘的基本原则

- 存真:尽量保留底本原貌,不因文意不通而径改。
- 择善:异文并存时,择其义长、有版本依据者。
- 对校:以同一书的别本互校;本校:以本书前后互证;他校:以他书征引者校;理校:据文理、音韵、史实推断。
- 理校风险最高,凡属理校结论必须标注「存疑」,不得当作定论。

## 作者归属判定

- 以最早、最可靠的总集或别集收录为第一依据;晚出选本的单条记载不足以推翻早出总集。
- 同一诗作见于两人别集时,需看历代题署、唱和背景、风格用韵是否吻合。
- 仅凭「风格像某人」而改署作者,属于推测,应标为「存疑」而非「有误」。

## 原文异文判定

- 异文分「形近而讹」(字形相近致误)、「音近而讹」(音同音近致误)、「义近而讹」(因上下文联想致误)三类。
- 判定讹字需给出:底本作某、别本作某、何者为长及依据;无版本依据的单字校改标为「存疑」。
- 押韵位置的字若与韵部不合,优先疑为讹字,但需结合韵书复核。

## 朝代与年代判定

- 诗人所属朝代以其主要活动年代为准;由盛唐入中唐者,按传统题署归属,不以前后跨代为据硬改。
- 诗作系年需有本事、唱和、行迹等旁证;无旁证不得据诗中意象径定年代。

## 常见讹误类型

- 张冠李戴:诗作被误署为另一作者,多见于选本辗转抄录。
- 篇题讹误:诗题与正文不符,或组诗题序错位。
- 断句讹误:因标点或句读移位导致句意走样。
- 译注讹误:译文与原文意不合,或注释人物、典故指向错误。
```

- [ ] **Step 2: 写失败测试(markdown 子节切分)**

追加到 `potry-ai-agent/tests/test_chunking.py` 末尾(并在文件顶部 import 处补 `chunk_policy_doc, split_markdown_sections`):

```python
def test_split_markdown_sections_by_h2_headings():
    md = "# 大标题\n\n前言文字\n\n## 甲节\n甲正文。\n\n## 乙节\n乙正文。\n"
    assert split_markdown_sections(md) == [("甲节", "甲正文。"), ("乙节", "乙正文。")]


def test_split_markdown_sections_falls_back_to_whole_doc():
    assert split_markdown_sections("没有二级标题的正文。") == [("正文", "没有二级标题的正文。")]


def test_split_markdown_sections_empty_doc():
    assert split_markdown_sections("") == []


def test_split_markdown_sections_truncates_long_heading_to_column_width():
    md = "## " + "长" * 40 + "\n正文。"
    (name, body) = split_markdown_sections(md)[0]
    assert len(name) == 32 and body == "正文。"


def test_chunk_policy_doc_uses_rule_meta_prefix_and_sections():
    doc = {
        "title": "格律·词牌规则",
        "markdown": "## 押韵规则\n近体诗偶句押韵。\n## 对仗规则\n律诗颔联颈联对仗。\n",
    }
    chunks = chunk_policy_doc(doc, chunk_size=400, overlap=60)
    assert {c["section"] for c in chunks} == {"押韵规则", "对仗规则"}
    assert all(c["chunk_text"].startswith("格律·词牌规则|||规则\n") for c in chunks)
    assert chunks[0]["raw_text"] == "近体诗偶句押韵。"


def test_chunk_policy_doc_returns_empty_for_blank_markdown():
    assert chunk_policy_doc({"title": "x", "markdown": "   "}, 400, 60) == []
```

- [ ] **Step 3: 写失败测试(source_type 过滤与 policy 建库)**

追加到 `potry-ai-agent/tests/test_knowledge.py` 末尾:

```python
def test_list_pending_filters_by_source_type():
    st = make_storage()
    st.upsert_chunks([_chunk(), _chunk(source_type="policy", source_id=1, section="押韵规则")])
    assert len(st.list_pending()) == 2
    assert [c["source_type"] for c in st.list_pending(source_type="policy")] == ["policy"]


def test_count_by_status_filters_by_source_type():
    st = make_storage()
    st.upsert_chunks([_chunk(), _chunk(source_type="policy", source_id=1, section="押韵规则")])
    st.mark_embedded([c["id"] for c in st.list_pending(source_type="policy")])
    assert st.count_by_status() == {"pending": 1, "embedded": 1}
    assert st.count_by_status(source_type="policy") == {"embedded": 1}
```

追加到 `potry-ai-agent/tests/test_build_kb.py` 末尾:

```python
def test_collect_policy_chunks_assigns_stable_source_ids(tmp_path):
    (tmp_path / "meter_rules.md").write_text("## 押韵规则\n近体诗偶句押韵。\n", encoding="utf-8")
    (tmp_path / "collation_rules.md").write_text("## 存真\n不因文意不通径改。\n", encoding="utf-8")
    rows1 = build_kb.collect_policy_chunks(str(tmp_path), 400, 60)
    rows2 = build_kb.collect_policy_chunks(str(tmp_path), 400, 60)
    assert [r["source_id"] for r in rows1] == [1, 2]          # 稳定映射,重跑不变
    assert [r["source_id"] for r in rows2] == [1, 2]
    assert all(r["source_type"] == "policy" for r in rows1)
    assert rows1[0]["title"] == "格律·词牌规则" and rows1[1]["title"] == "校勘准则"


def test_collect_policy_chunks_skips_missing_file(tmp_path):
    (tmp_path / "meter_rules.md").write_text("## 押韵规则\n近体诗偶句押韵。\n", encoding="utf-8")
    rows = build_kb.collect_policy_chunks(str(tmp_path), 400, 60)   # collation 缺失
    assert {r["source_id"] for r in rows} == {1}


def test_embed_pending_filters_by_source_type(env):
    storage, store = env
    storage.upsert_chunks([_chunk(), _chunk(source_type="policy", source_id=1, section="押韵规则")])
    stats = build_kb.embed_pending(storage, store, batch_size=1, source_type="policy")
    assert stats == {"embedded": 1, "failed": 0, "remaining": 0}
    assert storage.count_by_status() == {"pending": 1, "embedded": 1}   # 诗词块未被牵连
```

- [ ] **Step 4: 改既有用例 `test_run_writes_chunks_and_reports_stats`**

`run()` 默认仍走 poem+poet(**保持 Ch03 语义**),policy 只在显式 `only="policy"` 时纳入;但为了让该用例与其他来源隔离,把两处调用改为显式传 `only="poem"`:

```python
    stats = bk.run(only="poem")
    ...
    stats2 = bk.run(skip_chunk=True, only="poem")  # 只补向量化,不重切
```

- [ ] **Step 5: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chunking.py tests/test_knowledge.py tests/test_build_kb.py -q
```

Expected: FAIL(`chunk_policy_doc` / `split_markdown_sections` 未定义;`list_pending` 不收 `source_type`;`collect_policy_chunks` 不存在)。

- [ ] **Step 6: 实现 `chunking.py`**

在 `chunking.py` 顶部常量区追加:

```python
_HEADING_PREFIX = "## "
_MAX_SECTION_NAME = 32  # knowledge_chunks.section 是 String(32),超出会写不进去
```

在 `chunk_poet` 之后追加:

```python
def split_markdown_sections(markdown: str) -> list[tuple[str, str]]:
    """按 markdown '## ' 二级标题切子节,返回 [(标题, 正文)]。

    首个 '## ' 之前的内容(文档头 / 一级标题)不参与切块,直接忽略;
    整篇没有 '## ' 时视作单个子节,标题记作「正文」;空文档返回 []。
    标题按 section 列宽截断(32 字)。
    """
    sections: list[tuple[str, list[str]]] = []
    current: list[str] | None = None
    for line in markdown.splitlines():
        if line.startswith(_HEADING_PREFIX):
            current = []
            sections.append((line[len(_HEADING_PREFIX):].strip() or "正文", current))
        elif current is not None:
            current.append(line)
    if not sections:
        body = (markdown or "").strip()
        return [("正文", body)] if body else []
    return [(name[:_MAX_SECTION_NAME], "\n".join(body).strip()) for name, body in sections]


def chunk_policy_doc(doc: dict, chunk_size: int, overlap: int) -> list[dict]:
    """把一篇规则文档切成块。doc 需含 title / markdown。

    按 '## ' 二级标题切子节后,逐子节复用通用 `chunk_section`(与诗词/诗人文档同一套
    切块、重叠、裁句逻辑),故块结构与 Ch03 语料完全一致。
    """
    prefix = meta_prefix(doc.get("title"), "", "", "规则")
    chunks: list[dict] = []
    for section, body in split_markdown_sections(doc.get("markdown") or ""):
        chunks.extend(chunk_section(prefix, section, body, chunk_size, overlap))
    return chunks
```

- [ ] **Step 7: 实现 `knowledge.py` 过滤**

把 `list_pending` 改为:

```python
    def list_pending(self, limit: int | None = None, source_type: str | None = None) -> list[dict]:
        stmt = select(KnowledgeChunk).where(KnowledgeChunk.status == "pending").order_by(KnowledgeChunk.id)
        if source_type:
            stmt = stmt.where(KnowledgeChunk.source_type == source_type)
        if limit is not None:
            stmt = stmt.limit(limit)
        with self._factory() as session:
            return [_to_dict(r) for r in session.execute(stmt).scalars()]
```

把 `count_by_status` 改为:

```python
    def count_by_status(self, source_type: str | None = None) -> dict:
        # SQL 聚合计数,避免把全表拉进 Python;只返回出现过的状态(不补 0)
        stmt = select(KnowledgeChunk.status, func.count()).group_by(KnowledgeChunk.status)
        if source_type:
            stmt = stmt.where(KnowledgeChunk.source_type == source_type)
        with self._factory() as session:
            return {status: cnt for status, cnt in session.execute(stmt).all()}
```

- [ ] **Step 8: 实现 `build_kb.py`**

(a) 顶部 import 追加 `import os`、`from chunking import chunk_policy_doc`(与既有 `from chunking import chunk_poem, chunk_poet` 合并成一行);

(b) 常量区追加:

```python
# 规则语料:文件名 → (source_id, 展示标题)。source_id 是**显式固定**的稳定映射,
# 不用「排序后取下标」——新增文档若排在前面会让既有 id 漂移,导致唯一键错位。
_POLICY_DOCS = (
    ("meter_rules.md", 1, "格律·词牌规则"),
    ("collation_rules.md", 2, "校勘准则"),
)
_DEFAULT_POLICY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policy_docs")
```

(c) 在 `collect_poet_chunks` 之后追加:

```python
def collect_policy_chunks(policy_dir: str, chunk_size: int, overlap: int) -> list[dict]:
    """读规则文档 → 切块。文档不可读则跳过并告警(不阻断其余文档)。"""
    out: list[dict] = []
    for filename, source_id, title in _POLICY_DOCS:
        path = os.path.join(policy_dir, filename)
        try:
            with open(path, encoding="utf-8") as handle:
                markdown = handle.read()
        except OSError as exc:  # noqa: BLE001 - 缺文档只告警,不算失败
            print(f"[kb] 规则文档不可读,跳过 {filename}: {str(exc)[:200]}")
            continue
        for c in chunk_policy_doc({"title": title, "markdown": markdown}, chunk_size, overlap):
            out.append(
                {"source_type": "policy", "source_id": source_id,
                 "title": title, "writer": None, "dynasty": None, **c}
            )
    return out
```

(d) `embed_pending` 增加 `source_type` 过滤:

```python
def embed_pending(
    storage: KnowledgeStorage, store: VectorStore, batch_size: int = _EMBED_BATCH,
    source_type: str | None = None,
) -> dict:
    """把 status='pending' 的块分批嵌入并写入 Milvus,成功则转 embedded。

    `source_type` 非空时只处理该类(如只补 `policy`),避免把 1.1 万条 pending 诗词
    一并嵌入。整批嵌入/写入失败时**不标记**,块保持 pending —— 这就是"挂了能重跑"。
    配置类错误(ValueError,如维度/长度校验不通过)不吞:直接上抛。
    """
    embedded = failed = batches = 0
    total = storage.count_by_status(source_type=source_type).get("pending", 0)
    print(f"[kb] 待向量化 {total} 块(source_type={source_type or '全部'}),批大小 {batch_size}")
    while True:
        pending = storage.list_pending(limit=batch_size, source_type=source_type)
        ...
```

(其余循环体一字不改;末尾 `return {... "remaining": storage.count_by_status(source_type=source_type).get("pending", 0)}`。)

(e) `run` 增加 `only` / `policy_dir`:

```python
def run(
    limit: int | None = None, skip_chunk: bool = False,
    only: str | None = None, policy_dir: str | None = None,
) -> dict:
    """`only` ∈ {None, "poem", "poet", "policy"}:None = poem + poet(Ch03 语义,不动);
    显式给 "policy" 才纳入规则语料,并只嵌该来源的 pending。"""
    settings = load_settings()
    engine = get_engine(settings.mysql_url)
    KnowledgeBase.metadata.create_all(engine)
    storage = KnowledgeStorage(sessionmaker(bind=engine))
    store = MilvusLiteVectorStore(settings.milvus_db_path, settings.milvus_collection)

    written = 0
    if not skip_chunk:
        rows: list[dict] = []
        if only in (None, "poem", "poet"):
            session = new_session(settings.mysql_url)
            try:
                if only in (None, "poem"):
                    rows += collect_poem_chunks(session, settings.chunk_size, settings.chunk_overlap, limit)
                if only in (None, "poet"):
                    rows += collect_poet_chunks(session, settings.chunk_size, settings.chunk_overlap)
            finally:
                session.close()
        if only == "policy":
            rows += collect_policy_chunks(policy_dir or _DEFAULT_POLICY_DIR, settings.chunk_size, settings.chunk_overlap)
        written = storage.upsert_chunks(rows)
    stats = embed_pending(storage, store, source_type=only)
    return {"chunks_written": written, **stats, "status_counts": storage.count_by_status()}
```

(f) `main()` 增加 `--only` 与 `--policy-dir`:

```python
    parser.add_argument("--only", choices=("poem", "poet", "policy"), default=None,
                        help="只处理某类来源(如 --only policy 只切/只嵌规则语料)")
    parser.add_argument("--policy-dir", default=None, help="规则文档目录(默认 potry-ai-agent/policy_docs)")
```

并把 `run(limit=..., skip_chunk=...)` 改为 `run(limit=args.limit, skip_chunk=args.skip_chunk, only=args.only, policy_dir=args.policy_dir)`。

> 注意:`embed_pending(storage, store, source_type=only)` 里 `only=None` 时行为与 Ch03 完全一致(嵌全部 pending);只有显式 `--only policy` 才把嵌入范围收窄到 policy。

- [ ] **Step 9: 跑测试确认通过**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chunking.py tests/test_knowledge.py tests/test_build_kb.py -q
```

Expected: 全绿。

- [ ] **Step 10: 全量回归**

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Expected: `199 passed` + 新增用例数(以全绿为准)。

- [ ] **Step 11: 追记 dev-notes 阶段 3(第 1 个任务)**

追加到 `dev-notes/ch05.md` 一段:关键指令 / 产出物(本任务提交 hash)/ 拒绝或纠偏 / 翻车与返工。

- [ ] **Step 12: 提交**

```powershell
git add potry-ai-agent/policy_docs potry-ai-agent/chunking.py potry-ai-agent/knowledge.py potry-ai-agent/build_kb.py potry-ai-agent/tests/test_chunking.py potry-ai-agent/tests/test_knowledge.py potry-ai-agent/tests/test_build_kb.py dev-notes/ch05.md
git commit -m "feat(ch05): 规则语料文档与 policy 切分/建库支持(--only 过滤,不牵连 pending 诗词)"
```

---

## Task 2: 语料真跑入库 + 人工核对(前置:拉起 MySQL、停 API 服务)

**Files:**
- 无代码改动(纯数据/运行任务)

- [ ] **Step 1: 拉起 MySQL 并确认监听**

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" -uroot -ppublication-placeholder-mysql_password -N -e "SELECT COUNT(*) FROM knowledge_chunks;"
```

Expected: 返回行数(能连上)。若报连接失败 → 先用 `Get-Service -Name *mysql*` / 服务管理器把 MySQL 拉起来再重试。

- [ ] **Step 2: 确认 API 服务已停(Milvus Lite 独占文件锁)**

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
```

Expected: **无输出**(8000 无监听)。若有,先停掉 uvicorn 进程。

- [ ] **Step 3: 只切/只嵌 policy**

```powershell
.\.venv\Scripts\python.exe build_kb.py --only policy
```

Expected: 打印 `[kb] 待向量化 N 块(source_type=policy)` 且结果里 `failed=0`、`remaining=0`;`chunks_written` 为规则文档切出的块数(数十条量级,远小于 1.1 万)。

- [ ] **Step 4: 复核库内状态(只动了 policy)**

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" -uroot -ppublication-placeholder-mysql_password -N -e "SELECT source_type, status, COUNT(*) FROM knowledge_chunks GROUP BY source_type, status ORDER BY source_type, status;" poem
```

Expected: 出现 `policy  embedded  N`;诗词的 `pending` 计数**与 Step 1 前的 dev-notes 记录一致**(未被牵连)。

- [ ] **Step 5: 人工核对语料质量(纯数据任务)**

逐字通读 `policy_docs/meter_rules.md` 与 `policy_docs/collation_rules.md`:核对体式字数、平仄/押韵/对仗表述、校勘四法定义是否准确;把「每条条款是否自洽、是否可用作判定依据」的结论写进 dev-notes。

- [ ] **Step 6: 追记 dev-notes 阶段 3(第 2 个任务)并提交**

```powershell
git add dev-notes/ch05.md
git commit -m "docs(ch05): policy 语料入库真跑与人工核对结果"
```

---

# 组二 · 代码

## Task 3: 意图体系(八类六出口)+ 状态字段 + 归零清单上移

**Files:**
- Modify: `potry-ai-agent/workflow/intent.py`
- Modify: `potry-ai-agent/workflow/state.py`
- Modify: `potry-ai-agent/workflow/nodes.py`(只改 `classify_node` / `route_node` / `resolve_node` 的引用)
- Test: `potry-ai-agent/tests/test_workflow_intent.py`(重写)
- Test: `potry-ai-agent/tests/test_workflow_nodes.py`(改 classify / route / resolve 相关用例)
- Test: `potry-ai-agent/tests/test_workflow_graph.py`(改 1 处已失效标签)

- [ ] **Step 1: 重写 `tests/test_workflow_intent.py`**

```python
"""八类意图 → 六出口硬编码映射的完整性与解析降级(含新置信度字段)。"""
from workflow import intent


def test_mapping_covers_all_eight_intents():
    assert len(intent.INTENT_LABELS) == 8
    assert set(intent.INTENT_TO_ROUTE) == set(intent.INTENT_LABELS)


def test_route_values_are_legal():
    assert set(intent.INTENT_TO_ROUTE.values()) <= set(intent.ROUTES)
    assert set(intent.ROUTES) == {
        intent.ROUTE_KNOWLEDGE, intent.ROUTE_BUSINESS, intent.ROUTE_RULING,
        intent.ROUTE_COMPLAINT, intent.ROUTE_CHITCHAT, intent.ROUTE_OTHER,
    }


def test_mapping_matches_spec():
    assert intent.INTENT_TO_ROUTE["poem_explain"] == intent.ROUTE_KNOWLEDGE
    assert intent.INTENT_TO_ROUTE["find_poem"] == intent.ROUTE_BUSINESS
    assert intent.INTENT_TO_ROUTE["find_poet"] == intent.ROUTE_BUSINESS
    assert intent.INTENT_TO_ROUTE["poem_meter"] == intent.ROUTE_RULING
    assert intent.INTENT_TO_ROUTE["poem_verify"] == intent.ROUTE_RULING
    assert intent.INTENT_TO_ROUTE["complaint"] == intent.ROUTE_COMPLAINT
    assert intent.INTENT_TO_ROUTE["chitchat"] == intent.ROUTE_CHITCHAT
    assert intent.INTENT_TO_ROUTE["other"] == intent.ROUTE_OTHER


def test_merged_labels_are_gone():
    # 归并后这两个标签不再单列(工具与能力保留,只是标签消失)
    assert "reference_lookup" not in intent.INTENT_LABELS
    assert "find_dynasty" not in intent.INTENT_LABELS


def test_parse_intent_response_accepts_plain_json():
    label, conf = intent.parse_intent_response('{"intent": "find_poet", "confidence": 0.9}')
    assert (label, conf) == ("find_poet", 0.9)


def test_parse_intent_response_tolerates_fenced_json():
    assert intent.parse_intent_response(
        '```json\n{"intent": "poem_explain", "confidence": 0.8}\n```'
    )[0] == "poem_explain"


def test_parse_intent_response_defaults_confidence_when_missing():
    assert intent.parse_intent_response('{"intent": "poem_meter"}') == ("poem_meter", 0.0)


def test_parse_intent_response_clamps_out_of_range_confidence():
    assert intent.parse_intent_response('{"intent": "chitchat", "confidence": 7}')[1] == 1.0
    assert intent.parse_intent_response('{"intent": "chitchat", "confidence": -3}')[1] == 0.0
    assert intent.parse_intent_response('{"intent": "chitchat", "confidence": "高"}')[1] == 0.0


def test_parse_intent_response_degrades_to_other():
    assert intent.parse_intent_response("今天天气不错") == (intent.DEFAULT_INTENT, 0.0)
    assert intent.parse_intent_response('{"intent": "no_such_label"}') == (intent.DEFAULT_INTENT, 0.0)
    assert intent.parse_intent_response('{"nope": 1}') == (intent.DEFAULT_INTENT, 0.0)
    assert intent.DEFAULT_INTENT == intent.INTENT_OTHER == "other"
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_intent.py -q
```

Expected: FAIL(`ROUTE_RULING` / `parse_intent_response` 不存在)。

- [ ] **Step 3: 重写 `workflow/intent.py`**

```python
"""八类意图定义 + **硬编码**分流映射(八类 → 六出口)。

分流规则不交给模型决策:意图识别节点只负责产出标签 + 置信度,出口由本模块常量表决定(spec §3)。

相对 Ch04 的归并(用户拍板):`reference_lookup`(典故/出处)并入 `poem_explain`;
`find_dynasty`(查朝代)并入 `find_poem`。两个工具仍保留,Agent 仍可自主调用。
"""
import json

# 六个出口
ROUTE_KNOWLEDGE = "knowledge"
ROUTE_BUSINESS = "business"
ROUTE_RULING = "ruling"          # 判定子流程(格律/体裁合规 + 诗作校勘核对)
ROUTE_COMPLAINT = "complaint"
ROUTE_CHITCHAT = "chitchat"
ROUTE_OTHER = "other"
ROUTES = (ROUTE_KNOWLEDGE, ROUTE_BUSINESS, ROUTE_RULING, ROUTE_COMPLAINT, ROUTE_CHITCHAT, ROUTE_OTHER)

# 八类意图标签(七类业务 + other 兜底)
INTENT_POEM_EXPLAIN = "poem_explain"
INTENT_FIND_POEM = "find_poem"
INTENT_FIND_POET = "find_poet"
INTENT_POEM_METER = "poem_meter"
INTENT_POEM_VERIFY = "poem_verify"
INTENT_COMPLAINT = "complaint"
INTENT_CHITCHAT = "chitchat"
INTENT_OTHER = "other"

INTENT_LABELS = (
    INTENT_POEM_EXPLAIN, INTENT_FIND_POEM, INTENT_FIND_POET,
    INTENT_POEM_METER, INTENT_POEM_VERIFY, INTENT_COMPLAINT, INTENT_CHITCHAT, INTENT_OTHER,
)

# 八类 → 六出口(硬编码,不得改为模型决策)
INTENT_TO_ROUTE = {
    INTENT_POEM_EXPLAIN: ROUTE_KNOWLEDGE,
    INTENT_FIND_POEM: ROUTE_BUSINESS,
    INTENT_FIND_POET: ROUTE_BUSINESS,
    INTENT_POEM_METER: ROUTE_RULING,
    INTENT_POEM_VERIFY: ROUTE_RULING,
    INTENT_COMPLAINT: ROUTE_COMPLAINT,
    INTENT_CHITCHAT: ROUTE_CHITCHAT,
    INTENT_OTHER: ROUTE_OTHER,
}

# 拿不准就归 other(spec §3.2:别硬塞进业务意图);解析失败/模型异常同样落这里
DEFAULT_INTENT = INTENT_OTHER


def parse_intent_response(text: str) -> tuple[str, float]:
    """从模型输出取出 `(intent, confidence)`。

    模型可能包 ```json 围栏或加解释文字,故按首 `{` / 末 `}` 截取再解析。
    解析失败、标签非法、置信度缺失/非数值 → 归 `other`,置信度 0.0(spec §3.2/§10:
    不抛异常、不阻断);置信度钳到 [0, 1]。
    """
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
        label = str(data.get("intent", "")).strip()
    except (ValueError, json.JSONDecodeError, AttributeError):
        return DEFAULT_INTENT, 0.0
    if label not in INTENT_LABELS:
        return DEFAULT_INTENT, 0.0
    raw = data.get("confidence", 0.0)
    try:
        confidence = min(1.0, max(0.0, float(raw)))
    except (TypeError, ValueError):
        confidence = 0.0
    return label, confidence
```

- [ ] **Step 4: 重写 `workflow/state.py`**

```python
"""Ch04/Ch05 编排状态:贯穿图全流程的 WorkflowState(TypedDict)。

`messages` 用 `operator.add` 做累积(LangGraph 官方 reducer 写法)以形成跨轮对话历史;
`tool_trace` 为普通通道(每轮由 `resolve_node` 归零,防跨轮泄漏);其余字段为单值覆盖语义。
`total=False` 使所有键可选,便于分支出口只写自己那几个键。

**注意**:本文件不承载 `pending_subflow` / `candidates` / `subflow_kind` —— 这三个是
「两段式续跑」的跨轮标记,由 `resolve_node` 与 `route_node` 显式处置,刻意不进 `PER_TURN_RESET`。
"""
import operator
from typing import Annotated, TypedDict

# 本会话最近 N 轮注入指代消解(单一来源);history 只存 user 原问 + 最终回答
HISTORY_TURNS = 3

# 每轮开始时必须归零的"本轮字段":State 经 checkpointer 跨轮持久化,而 LangGraph
# 只更新"节点返回了的键",所以不显式覆盖就会把上一轮的值泄漏到本轮
# (Ch04 实测:投诉轮之后的普通问题仍被 SSE 带出 handoff/feedback 按钮)。
# `messages` 是 add reducer 通道,刻意不归零 → 保留跨轮对话历史;`history` 同理累积。
PER_TURN_RESET = {
    "intent": "",
    "confidence": 0.0,
    "route": "",
    "retrieved": [],
    "evidence_score": None,
    "gate_status": "skip",
    "answer": "",
    "actions": [],
    "tool_trace": [],
    "iterations": 0,
    "tokens_used": 0,
    "fallback_reason": "",
    # ---------- Ch05 ----------
    "query_changed": False,
    "slot_target": None,
    "expanded_queries": [],
    "policy_hits": [],
    "correction_categories": [],
}


class WorkflowState(TypedDict, total=False):
    session_id: str              # 会话标识,同时作为 checkpointer 的 thread_id
    user_input: str              # 用户原始输入(续跑段为空串)
    selected_poem_id: int | None # 续跑段:用户点选的诗词卡片 id(缺槽位回填)
    resolved_input: str          # 消解/改写后的检索用问题(即 spec 里的 query)
    history: list[dict]          # 本会话最近 HISTORY_TURNS 轮的 {role, content}
    intent: str                  # 八类意图标签
    confidence: float            # 模型自评置信度(本章只记录,不据此分流)
    route: str                   # 六个出口之一
    retrieved: list[dict]        # 知识类检索证据(hit + 回查到的原文片段)
    evidence_score: float | None # 证据强度(合并后 top1 相似度;本轮未检索时 None)
    gate_status: str             # pass / insufficient;未走检索的出口保持缺省(日志记 skip)
    messages: Annotated[list, operator.add]     # ReAct 子循环消息序列(累积)
    tool_trace: list             # 工具调用轨迹(供 SSE 与落库);普通通道,每轮归零
    answer: str                  # 最终回答
    actions: list[str]           # 可选操作标识(投诉类为 ["handoff", "feedback"])
    iterations: int              # ReAct 迭代数
    tokens_used: int             # token 累计
    fallback_reason: str         # 兜底/强制收敛原因
    started_at: float            # 本轮起始 monotonic 时间戳(日志耗时用)
    # ---------- Ch05 ----------
    query_changed: bool         # 消解/改写是否真的改动过原文
    subflow_kind: str            # meter / verify(哪条判定子流程)
    slot_target: dict | None     # 已确定的诗作对象(权威数据);空 = 缺槽位
    candidates: list[dict]       # 缺槽位时下发的候选诗词卡片
    pending_subflow: bool        # 是否处于"等用户回填"状态(续跑入口判据)
    expanded_queries: list[str]  # 扩写出的多条检索查询(仅 ruling 用)
    policy_hits: list[dict]      # 检索到的 policy 规则条款(供 Agent 作判定依据)
    correction_categories: list[str]  # 纠错单固定类目(下发前端做下拉)
```

- [ ] **Step 5: 改 `workflow/nodes.py` 的三处引用**

(a) 删除文件内的 `_PER_TURN_RESET` 定义块(注释 + 字典),改为 import:

```python
from workflow.state import PER_TURN_RESET
```

(b) `resolve_node` 返回改用新名字:

```python
def resolve_node(state: dict) -> dict:
    """指代消解(Ch04 版:直接透传;正式版在 Task 9 换为 LLM 消解/改写)+ 本轮字段归零。"""
    return {"resolved_input": state["user_input"], **PER_TURN_RESET}
```

(c) `classify_node` 改为八类 + 置信度 + 降级 `other`:

```python
async def classify_node(state: dict) -> dict:
    """意图识别:四件套 prompt 输出 {intent, confidence};解析失败/模型失败 → 降级 other 并告警。"""
    deps = get_deps()
    try:
        message = await deps.llm.ainvoke(INTENT_PROMPT.invoke({"question": state["resolved_input"]}))
        label, confidence = parse_intent_response(message.content or "")
    except Exception as exc:  # noqa: BLE001 - 分类失败不阻断流程
        print(f"[wf] classify fail, degrade to {DEFAULT_INTENT}: {str(exc)[:200]}")
        label, confidence = DEFAULT_INTENT, 0.0
    print(f"[wf] classify intent={label} conf={confidence:.2f}")
    return {"intent": label, "confidence": confidence}
```

(d) import 区把 `parse_intent` 换成 `parse_intent_response`,并补 `ROUTE_RULING` / `ROUTE_OTHER` / `INTENT_POEM_METER` / `INTENT_POEM_VERIFY`:

```python
from workflow.intent import (
    DEFAULT_INTENT,
    INTENT_POEM_METER,
    INTENT_TO_ROUTE,
    ROUTE_BUSINESS,
    ROUTE_CHITCHAT,
    ROUTE_COMPLAINT,
    ROUTE_KNOWLEDGE,
    ROUTE_OTHER,
    ROUTE_RULING,
    parse_intent_response,
)
```

(e) `route_node` 改为六出口 + 设定 `subflow_kind`:

```python
def route_node(state: dict) -> dict:
    """意图分流:硬编码查表得出口;投诉/闲聊直接落预设话术(不调模型、不调工具)。

    判定子流程在此确定 `subflow_kind`(meter / verify)—— 续跑段不经过本节点,
    故该字段依赖 state 持久化保留;新轮一律重新赋值(非判定类为空串)。
    """
    label = state.get("intent", DEFAULT_INTENT)
    route = INTENT_TO_ROUTE.get(label, ROUTE_OTHER)
    out: dict = {"route": route, "subflow_kind": ""}
    if route == ROUTE_RULING:
        out["subflow_kind"] = "meter" if label == INTENT_POEM_METER else "verify"
    elif route == ROUTE_COMPLAINT:
        out["answer"] = COMPLAINT_REPLY
        out["actions"] = ["handoff", "feedback"]
    elif route == ROUTE_CHITCHAT:
        out["answer"] = CHITCHAT_REPLY
    return out
```

(f) `after_route` 扩到六出口(**本步只加 `ruling`/`other` 分支,条件边接线在 Task 9**):

```python
def after_route(state: dict) -> str:
    """分流条件边:知识类→检索;判定类→槽位检查;业务类/其他→Agent;投诉/闲聊→直接日志收尾。"""
    route = state.get("route", ROUTE_OTHER)
    if route == ROUTE_KNOWLEDGE:
        return "retrieve"
    if route == ROUTE_RULING:
        return "slot_check"
    if route in (ROUTE_BUSINESS, ROUTE_OTHER):
        return "agent"
    return "log"
```

- [ ] **Step 6: 改 `tests/test_workflow_nodes.py` 受影响用例**

- `test_resolve_node_passes_through_and_resets_turn_fields` 增加新字段断言:

```python
    assert out["confidence"] == 0.0
    assert out["query_changed"] is False
    assert out["policy_hits"] == []
    assert out["correction_categories"] == []
```

- 三个 classify 用例改为新契约:

```python
@pytest.mark.asyncio
async def test_classify_node_parses_json_with_confidence():
    _deps(ScriptedLLM(reply='{"intent": "find_poem", "confidence": 0.7}'))
    assert await classify_node({"resolved_input": "找那首讲月亮的"}) == {"intent": "find_poem", "confidence": 0.7}


@pytest.mark.asyncio
async def test_classify_node_degrades_to_other_on_bad_json():
    _deps(ScriptedLLM(reply="我觉得这是查诗人吧"))
    assert await classify_node({"resolved_input": "x"}) == {"intent": intent.DEFAULT_INTENT, "confidence": 0.0}


@pytest.mark.asyncio
async def test_classify_node_degrades_to_other_on_model_failure():
    _deps(ScriptedLLM(boom=True))
    assert await classify_node({"resolved_input": "x"}) == {"intent": intent.DEFAULT_INTENT, "confidence": 0.0}
```

- route 用例改为覆盖六出口:

```python
def test_route_node_knowledge_and_business_do_not_answer():
    _deps()
    assert route_node({"intent": "poem_explain"}) == {"route": intent.ROUTE_KNOWLEDGE, "subflow_kind": ""}
    assert route_node({"intent": "find_poet"}) == {"route": intent.ROUTE_BUSINESS, "subflow_kind": ""}


def test_route_node_ruling_marks_subflow_kind():
    assert route_node({"intent": "poem_meter"}) == {"route": intent.ROUTE_RULING, "subflow_kind": "meter"}
    assert route_node({"intent": "poem_verify"}) == {"route": intent.ROUTE_RULING, "subflow_kind": "verify"}


def test_route_node_complaint_carries_two_independent_actions():
    out = route_node({"intent": "complaint"})
    assert out["route"] == intent.ROUTE_COMPLAINT
    assert out["answer"] == COMPLAINT_REPLY
    assert out["actions"] == ["handoff", "feedback"]   # 两个独立操作标识


def test_route_node_chitchat_uses_preset_reply():
    out = route_node({"intent": "chitchat"})
    assert out == {"route": intent.ROUTE_CHITCHAT, "subflow_kind": "", "answer": CHITCHAT_REPLY}


def test_route_node_unknown_intent_falls_to_other():
    # 兜底类改为 other(原降级 chitchat):拿不准不硬塞业务意图
    assert route_node({"intent": "no_such"})["route"] == intent.ROUTE_OTHER


def test_after_route_branches_six_outlets():
    assert after_route({"route": intent.ROUTE_KNOWLEDGE}) == "retrieve"
    assert after_route({"route": intent.ROUTE_RULING}) == "slot_check"
    assert after_route({"route": intent.ROUTE_BUSINESS}) == "agent"
    assert after_route({"route": intent.ROUTE_OTHER}) == "agent"
    assert after_route({"route": intent.ROUTE_COMPLAINT}) == "log"
    assert after_route({"route": intent.ROUTE_CHITCHAT}) == "log"
```

- [ ] **Step 7: 改 `tests/test_workflow_graph.py` 的失效标签**

`reference_lookup` 已并入 `poem_explain`,而 `parse_intent_response` 对未知标签会归 `other` → 该用例的意图标签必须换掉,否则会走 `other` 出口而进不了知识类检索:

```python
    _wire(ScriptedLLM([AIMessage(content='{"intent": "poem_explain"}')]), registry,
          knowledge=knowledge, chat=FakeChatStorage())
```

(仅此一行,属 `test_knowledge_gate_blocks_agent_when_evidence_insufficient`。)

- [ ] **Step 8: 跑测试确认通过**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_intent.py tests/test_workflow_nodes.py tests/test_workflow_graph.py -q
```

Expected: 全绿。

- [ ] **Step 9: 全量回归**

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Expected: 全绿(`test_workflow_endpoint.py` 的 `test_workflow_sse_sequence_with_action` 仍应通过 —— 投诉类契约未变)。

- [ ] **Step 10: 追记 dev-notes 阶段 3(第 3 个任务)并提交**

```powershell
git add potry-ai-agent/workflow/intent.py potry-ai-agent/workflow/state.py potry-ai-agent/workflow/nodes.py potry-ai-agent/tests/test_workflow_intent.py potry-ai-agent/tests/test_workflow_nodes.py potry-ai-agent/tests/test_workflow_graph.py dev-notes/ch05.md
git commit -m "feat(ch05): 八类意图/六出口硬编码映射 + 状态新增字段与归零清单(nodes→state 上移)"
```

---

## Task 4: Prompt 四件套 / 消解改写 / 扩写 / 对象抽取 / 判定指令 / 槽位话术

**Files:**
- Modify: `potry-ai-agent/prompts.py`

- [ ] **Step 1: 重写 `prompts.py` 的 Ch04 段并追加 Ch05 段**

把现有 `# ---------- Ch04:意图识别与预设话术 ----------` 起至文件末尾整段替换为:

```python
# ---------- 意图识别与预设话术 ----------

# spec §3.2 四件套:枚举成选择题 / 强制 JSON(intent + confidence)/ 边界 few-shot / other 兜底
INTENT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是意图分类器。请从下列八个选项里选一个最贴切的,只输出一行 JSON,不要任何解释与多余文字:
{{"intent": "<标签>", "confidence": <0 到 1 之间的小数>}}

八个选项:
- poem_explain: 诗词释义/赏析/典故出处(如"这首诗什么意思""举头望明月出自哪首诗")
- find_poem: 查诗词/按朝代找诗(如"那首讲月亮的叫啥""唐代有哪些名篇")
- find_poet: 查诗人(如"李白是什么朝代的""介绍一下杜甫")
- poem_meter: 格律/体裁合规判定(如"这句合不合律""这首是不是七律")
- poem_verify: 诗作校勘核对(作者/原文/朝代是否与权威数据一致,如"作者是不是搞错了""原文有没有讹字")
- complaint: 纠错或表达不满(如"答得不对,我不满意")
- chitchat: 其它闲聊(如"今天天气不错")
- other: 与诗词无关、或说不清的问题(如"帮我写个 Java 排序")

易混边界样例:
"这句合不合律" → poem_meter(不是 poem_explain)
"这首诗什么意思" → poem_explain
"作者是不是搞错了" → poem_verify(不是 complaint)
"答得不对,我不满意" → complaint
"李白是什么朝代的" → find_poet
"帮我找一首写月亮的" → find_poem

拿不准就归 other,不要硬塞进业务意图。""",
        ),
        ("human", "{question}"),
    ]
)

# spec §3.1:指代消解 + Query 改写合成一个 LLM 环节(结合本会话历史)
RESOLVE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是对话理解助手。结合下面的「最近对话记录」,把用户最新的问题补全成一句
**不依赖上下文也能看懂**的完整问题,并把口语模糊的问法归一成标准问法。

规则:
- 问题本身已完整、指代已明确(如"《静夜思》表达了什么感情"),**原样返回,不要改写**;
- 只补全指代与归一化问法,**不要作答、不要添加未经用户提及的事实**(如不要凭空补诗题);
- 只输出一行 JSON:{{"query": "<补全后的问题>", "changed": <true|false>}},
  changed 表示相对用户原话是否真的改动过。

最近对话记录:
{history}""",
        ),
        ("human", "{question}"),
    ]
)

# spec §1.2:仅判定子流程使用;强制 JSON,字段只有 queries 一个数组
EXPAND_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是检索查询扩写助手。把用户问题泛化成 2 到 5 条**侧重点不同**的检索查询,
用于检索格律/校勘的规则条款。

- 只输出一行 JSON:{{"queries": ["查询一", "查询二"]}},字段只有 queries 一个数组;
- 各条查询之间不要语义重复(例如一条问体式句数、一条问押韵、一条问平仄)。""",
        ),
        ("human", "{question}"),
    ]
)

# spec §8.1:判定子流程的槽位抽取(抽不到给 null,禁止编造)
SLOT_EXTRACT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """从用户问题里抽取**诗作对象**:诗题,或用户引用的诗句片段。

- 只输出一行 JSON:{{"title": "<诗题或诗句片段>"}};
- 抽不到就输出 {{"title": null}};**不要编造诗题**。""",
        ),
        ("human", "{question}"),
    ]
)

# spec §8.5:判定子流程交给主力 Agent 的硬约束(只判"能不能/对不对")
RULING_JUDGE_INSTRUCTION = (
    "【任务】依据上面的诗作权威数据与规则条款,只回答用户问的"
    "「能不能 / 对不对」这一个判定问题:合不合律、是不是某个体式、"
    "作者/原文/朝代是否与权威数据一致。"
    "不要泛泛赏析,不要延伸到无关话题;依据不足就如实说不确定,不得编造。"
)

# spec §4/§8:投诉与闲聊走**预设固定话术**,不调模型、不调工具
COMPLAINT_REPLY = (
    "抱歉,让你有不好的体验了。这轮问题我记下来了,"
    "你可以选择转人工,或提交反馈告诉我具体哪里不对。"
)
CHITCHAT_REPLY = "我是青莲,只陪你聊诗词文史。想读哪首诗,或问哪句词的出处,随时招呼我。"

# spec §7:知识类证据不足时的兜底话术
FALLBACK_REPLY = "这块我暂时没查到确切的资料,不敢乱讲。要不换个问法,或告诉我更具体的线索?"

# spec §5:缺槽位(没说哪首诗)时的固定确认提示 —— 用固定常量避免前端显示「(空回复)」
SLOT_PROMPT_REPLY = "先确认一下,你问的是哪首诗、哪句诗?下面几首里点一个,我接着细看。"
# 连候选都捞不到时:不能下发卡片,如实请用户补充线索
SLOT_NO_CANDIDATE_REPLY = "我没定位到你说的那首诗。麻烦告诉我诗题,或把原句贴给我。"
```

- [ ] **Step 2: 跑测试确认通过(纯文本改动,不该破坏既有用例)**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_prompts.py tests/test_workflow_nodes.py -q
```

Expected: 全绿(`test_prompts.py` 只断言系统提示词与 `CHAT_PROMPT`,不受影响)。

- [ ] **Step 3: 追记 dev-notes 阶段 3(第 4 个任务)并提交**

```powershell
git add potry-ai-agent/prompts.py dev-notes/ch05.md
git commit -m "feat(ch05): 意图四件套/消解改写/扩写/对象抽取 prompt 与判定指令、槽位话术"
```

---

## Task 5: `corrections` 表 + 固定类目 + 落库接口

**Files:**
- Modify: `potry-ai-agent/app_storage.py`
- Test: `potry-ai-agent/tests/test_feedback.py`(追加)

- [ ] **Step 1: 写失败测试**

追加到 `potry-ai-agent/tests/test_feedback.py` 末尾(并把顶部 import 改为 `from app_storage import AppBase, AppStorage, CORRECTION_CATEGORIES, Correction, Feedback`):

```python
def test_correction_columns_match_spec():
    assert {c.name for c in Correction.__table__.columns} == {
        "id", "userid", "poem_id", "category", "detail", "session_id", "creatime"
    }


def test_correction_categories_are_fixed_list():
    assert CORRECTION_CATEGORIES == (
        "格律错误", "作者张冠李戴", "原文有误", "译文有误", "赏析不认同",
    )


def test_add_correction_appends_row():
    engine = create_engine("sqlite:///:memory:")
    AppBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    storage = AppStorage(factory)
    cid = storage.add_correction(
        category="作者张冠李戴", detail="这首诗的作者应是王某", poem_id=7, session_id="s1"
    )
    assert cid is not None
    with factory() as session:
        row = session.get(Correction, cid)
    assert row.category == "作者张冠李戴"
    assert row.poem_id == 7 and row.session_id == "s1"
    assert row.userid is None and row.creatime is not None


def test_add_correction_rejects_unknown_category():
    engine = create_engine("sqlite:///:memory:")
    AppBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    storage = AppStorage(factory)
    with pytest.raises(ValueError, match="category"):
        storage.add_correction(category="乱填类目", detail="x")
```

> 该文件顶部需补 `import pytest`(若尚无)。

- [ ] **Step 2: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_feedback.py -q
```

Expected: FAIL(`Correction` / `CORRECTION_CATEGORIES` 不存在)。

- [ ] **Step 3: 实现 `app_storage.py`**

在 `Feedback` 类之后追加:

```python
# 纠错/复核单的固定类目(单一来源:后端校验 + 下发前端做下拉,前端不再自维护一份)
CORRECTION_CATEGORIES = (
    "格律错误",
    "作者张冠李戴",
    "原文有误",
    "译文有误",
    "赏析不认同",
)


class Correction(AppBase):
    """纠错/复核单(需求原文的"退款单"在诗词域的等价物,spec §9)。

    与 `feedback` 同 Base,由 `main.init_db` 的 `create_all` 一并建表;与 feedback 并存互不影响。
    """

    __tablename__ = "corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userid: Mapped[int | None] = mapped_column(Integer)
    poem_id: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str | None] = mapped_column(Text)
    session_id: Mapped[str | None] = mapped_column(String(64))
    creatime: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.now)
```

并把 import 行改为:

```python
from sqlalchemy import DateTime, Integer, String, Text
```

在 `AppStorage` 的 `add_feedback` 之后追加:

```python
    def add_correction(
        self, category: str, detail: str | None = None,
        poem_id: int | None = None, session_id: str | None = None, userid: int | None = None,
    ) -> int:
        """写一条纠错单,返回新行 id。类目非法直接抛 ValueError(边界校验,不静默存脏数据)。"""
        if category not in CORRECTION_CATEGORIES:
            raise ValueError(f"category 必须是固定类目之一,收到: {category}")
        with self._factory() as session:
            row = Correction(
                userid=userid, poem_id=poem_id, category=category,
                detail=detail, session_id=session_id,
            )
            session.add(row)
            session.commit()
            return row.id
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_feedback.py -q
```

Expected: 全绿(既有 3 个 feedback 用例 + 新增 4 个)。

- [ ] **Step 5: 追记 dev-notes 阶段 3(第 5 个任务)并提交**

```powershell
git add potry-ai-agent/app_storage.py potry-ai-agent/tests/test_feedback.py dev-notes/ch05.md
git commit -m "feat(ch05): corrections 纠错单表与固定类目、落库接口(类目校验)"
```

---

## Task 6: `workflow/resolve.py`(指代消解 + Query 改写)

**Files:**
- Create: `potry-ai-agent/workflow/resolve.py`
- Test: `potry-ai-agent/tests/test_workflow_resolve.py`

- [ ] **Step 1: 写失败测试**

`potry-ai-agent/tests/test_workflow_resolve.py`:

```python
"""指代消解 + Query 改写:透传 / 改写 / 失败降级 / 历史为空走捷径。"""
import pytest
from langchain_core.messages import AIMessage

from workflow.resolve import format_history, parse_resolve_result, resolve_input


class ScriptedLLM:
    def __init__(self, reply="", boom=False):
        self.reply = reply
        self.boom = boom
        self.calls = 0

    async def ainvoke(self, messages):
        self.calls += 1
        if self.boom:
            raise ConnectionError("upstream down")
        return AIMessage(content=self.reply)


def test_parse_resolve_result_accepts_plain_json():
    assert parse_resolve_result('{"query": "这句合不合律", "changed": true}') == ("这句合不合律", True)


def test_parse_resolve_result_tolerates_fenced_json():
    assert parse_resolve_result('```json\n{"query": "x", "changed": false}\n```') == ("x", False)


def test_parse_resolve_result_degrades_on_garbage():
    assert parse_resolve_result("我觉得不用改写") == ("", False)
    assert parse_resolve_result('{"query": ""}') == ("", False)


def test_format_history_renders_roles():
    text = format_history([{"role": "user", "content": "《静夜思》是谁写的"}, {"role": "assistant", "content": "李白"}])
    assert "用户:" in text and "青莲:" in text and "静夜思" in text


def test_format_history_empty():
    assert format_history([]) == "(无)"


@pytest.mark.asyncio
async def test_resolve_passes_through_when_no_history():
    llm = ScriptedLLM(reply='{"query": "不该被用到", "changed": true}')
    assert await resolve_input(llm, "《静夜思》表达了什么感情", []) == ("《静夜思》表达了什么感情", False)
    assert llm.calls == 0          # 无历史时不调模型(已完整问题原样透传)


@pytest.mark.asyncio
async def test_resolve_rewrites_with_history():
    llm = ScriptedLLM(reply='{"query": "《静夜思》这首诗合不合律", "changed": true}')
    history = [{"role": "user", "content": "《静夜思》是谁写的"}, {"role": "assistant", "content": "李白"}]
    assert await resolve_input(llm, "它合不合律", history) == ("《静夜思》这首诗合不合律", True)


@pytest.mark.asyncio
async def test_resolve_keeps_original_when_model_says_unchanged():
    llm = ScriptedLLM(reply='{"query": "《春晓》写的是什么", "changed": false}')
    assert await resolve_input(llm, "《春晓》写的是什么", [{"role": "user", "content": "x"}]) == ("《春晓》写的是什么", False)


@pytest.mark.asyncio
async def test_resolve_passes_through_when_model_fails():
    llm = ScriptedLLM(boom=True)
    assert await resolve_input(llm, "它合律吗", [{"role": "user", "content": "x"}]) == ("它合律吗", False)


@pytest.mark.asyncio
async def test_resolve_passes_through_when_json_unparsable():
    llm = ScriptedLLM(reply="这句得补一下上下文")
    assert await resolve_input(llm, "它合律吗", [{"role": "user", "content": "x"}]) == ("它合律吗", False)
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_resolve.py -q
```

Expected: FAIL,`ModuleNotFoundError: No module named 'workflow.resolve'`。

- [ ] **Step 3: 实现 `workflow/resolve.py`**

```python
"""指代消解 + Query 改写(合成一个 LLM 环节,spec §1.1)。

设计要点:
- **已完整、指代明确的问题原样透传**:历史为空时直接返回原问、不调模型(也省一次调用);
- 有历史才请模型消解;模型说 `changed=false` 时按原问返回,避免无谓改写;
- 任何失败(模型异常 / JSON 解析失败 / 空 query)一律透传原文 + 告警,不阻断(spec §10)。
"""
import json

from prompts import RESOLVE_PROMPT

_ROLE_NAMES = {"user": "用户", "assistant": "青莲"}


def format_history(history: list[dict]) -> str:
    """把本会话最近若干轮渲染成「用户:/青莲:」的纯文本,供 prompt 注入。"""
    lines = [
        f"{_ROLE_NAMES.get(row.get('role'), row.get('role') or '-')}:{row.get('content') or ''}"
        for row in (history or [])
    ]
    return "\n".join(lines) if lines else "(无)"


def parse_resolve_result(text: str) -> tuple[str, bool]:
    """解析模型输出 `{"query": ..., "changed": ...}`。

    失败、query 为空 → `("", False)`,由调用方按"透传原文"处理。
    """
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError, AttributeError):
        return "", False
    query = str(data.get("query") or "").strip()
    if not query:
        return "", False
    return query, bool(data.get("changed", False))


async def resolve_input(llm, question: str, history: list[dict] | None) -> tuple[str, bool]:
    """返回 `(消解/改写后的问题, 是否真的改动过)`;失败一律回落到原问。"""
    question = (question or "").strip()
    if not history:
        return question, False       # 无上文可依 → 原样透传
    try:
        message = await llm.ainvoke(
            RESOLVE_PROMPT.invoke({"history": format_history(history), "question": question})
        )
        resolved, changed = parse_resolve_result(message.content or "")
    except Exception as exc:  # noqa: BLE001 - 消解失败不阻断,透传原文
        print(f"[wf] resolve fail, pass through: {str(exc)[:200]}")
        return question, False
    if not resolved:
        return question, False
    return resolved, changed
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_resolve.py -q
```

Expected: `9 passed`。

- [ ] **Step 5: 追记 dev-notes 阶段 3(第 6 个任务)并提交**

```powershell
git add potry-ai-agent/workflow/resolve.py potry-ai-agent/tests/test_workflow_resolve.py dev-notes/ch05.md
git commit -m "feat(ch05): 指代消解与 Query 改写(无历史即透传,失败回落原文)"
```

---

## Task 7: `workflow/expand.py`(Query 扩写 + 多查询检索去重合并)

**Files:**
- Create: `potry-ai-agent/workflow/expand.py`
- Test: `potry-ai-agent/tests/test_workflow_expand.py`

- [ ] **Step 1: 写失败测试**

`potry-ai-agent/tests/test_workflow_expand.py`:

```python
"""Query 扩写(强制 JSON)+ 多查询检索按 chunk id 去重合并。"""
import pytest
from langchain_core.messages import AIMessage

from workflow import expand


class ScriptedLLM:
    def __init__(self, reply="", boom=False):
        self.reply = reply
        self.boom = boom

    async def ainvoke(self, messages):
        if self.boom:
            raise ConnectionError("upstream down")
        return AIMessage(content=self.reply)


def test_parse_queries_accepts_plain_json():
    assert expand.parse_queries('{"queries": ["甲", "乙"]}') == ["甲", "乙"]


def test_parse_queries_dedupes_and_drops_blank():
    assert expand.parse_queries('{"queries": ["甲", "甲", "", "  ", "乙"]}') == ["甲", "乙"]


def test_parse_queries_degrades_on_garbage():
    assert expand.parse_queries("我觉得可以拆三条") == []
    assert expand.parse_queries('{"queries": "不是数组"}') == []
    assert expand.parse_queries('{"nope": []}') == []


@pytest.mark.asyncio
async def test_expand_queries_reads_json():
    llm = ScriptedLLM(reply='{"queries": ["七律的句数字数", "律诗对仗要求"]}')
    assert await expand.expand_queries(llm, "这首是不是七律") == ["七律的句数字数", "律诗对仗要求"]


@pytest.mark.asyncio
async def test_expand_queries_degrades_to_single_original_query():
    llm = ScriptedLLM(reply="这三条我认为……")
    assert await expand.expand_queries(llm, "这首是不是七律") == ["这首是不是七律"]


@pytest.mark.asyncio
async def test_expand_queries_degrades_when_model_fails():
    llm = ScriptedLLM(boom=True)
    assert await expand.expand_queries(llm, "这句合律吗") == ["这句合律吗"]


@pytest.mark.asyncio
async def test_expand_queries_caps_at_five():
    llm = ScriptedLLM(reply='{"queries": ["1", "2", "3", "4", "5", "6", "7"]}')
    assert await expand.expand_queries(llm, "q") == ["1", "2", "3", "4", "5"]


class FakeEmbedder:
    def embed(self, texts):
        return [[float(len(t))] * 2 for t in texts]


class FakeStore:
    """同一 chunk id 在两次查询里给出不同分数,验证"按 id 去重取最高分后降序"。"""

    def __init__(self):
        self.calls = []

    def search(self, vector, topk, source_type):
        self.calls.append(source_type)
        score = vector[0]        # 用向量首元素当分数
        return [
            {"id": 100, "score": score, "source_type": source_type, "title": "t"},
            {"id": 200, "score": score - 0.1, "source_type": source_type, "title": "t2"},
        ]


def test_search_multi_dedupes_by_chunk_id_and_sorts(monkeypatch):
    monkeypatch.setattr(expand, "embed", FakeEmbedder().embed)
    store = FakeStore()
    monkeypatch.setattr(expand, "search", store.search)
    hits = expand.search_multi(["aa", "aaaa"], "policy", 5)
    assert store.calls == ["policy", "policy"]        # 每条查询各查一次
    assert [h["id"] for h in hits] == [100, 200]      # 按 id 去重
    assert hits[0]["score"] == 4.0                    # 同一 id 取最高分
    assert hits[0]["score"] >= hits[1]["score"]       # 降序


def test_search_multi_returns_empty_for_no_queries(monkeypatch):
    monkeypatch.setattr(expand, "embed", FakeEmbedder().embed)
    assert expand.search_multi([], "policy", 5) == []


def test_search_multi_survives_embedding_failure(monkeypatch):
    def boom(texts):
        raise RuntimeError("模型挂了")

    monkeypatch.setattr(expand, "embed", boom)
    assert expand.search_multi(["q"], "policy", 5) == []


def test_search_multi_survives_single_query_search_failure(monkeypatch):
    monkeypatch.setattr(expand, "embed", FakeEmbedder().embed)

    class BoomStore:
        def search(self, vector, topk, source_type):
            raise RuntimeError("milvus 挂了")

    monkeypatch.setattr(expand, "search", BoomStore().search)
    assert expand.search_multi(["q"], "policy", 5) == []
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_expand.py -q
```

Expected: FAIL,`ModuleNotFoundError: No module named 'workflow.expand'`。

- [ ] **Step 3: 实现 `workflow/expand.py`**

```python
"""Query 扩写 + 多查询检索去重合并(spec §1.2)。

只服务**判定子流程**:把一句问题泛化成多条侧重点不同的检索查询,各查一次 `policy` 源,
按 chunk id 去重后按相似度降序合并。扩写放在**检索侧现查现用**,知识库只留一份。
知识类(FAQ 式)不扩写 —— 由调用方决定是否走本模块。
"""
import json

from embeddings import embed
from prompts import EXPAND_PROMPT
from vector_store import search

_MAX_QUERIES = 5


def parse_queries(text: str) -> list[str]:
    """解析模型输出 `{"queries": [...]}`;失败 → `[]`,由调用方降级为单条原 query。"""
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
        raw = data.get("queries")
    except (ValueError, json.JSONDecodeError, AttributeError):
        return []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        text_item = str(item or "").strip()
        if text_item and text_item not in out:
            out.append(text_item)
    return out


async def expand_queries(llm, question: str) -> list[str]:
    """扩写成 2–5 条查询;任何失败降级为**单条原 query**(不阻断,spec §10)。"""
    question = (question or "").strip()
    try:
        message = await llm.ainvoke(EXPAND_PROMPT.invoke({"question": question}))
        queries = parse_queries(message.content or "")
    except Exception as exc:  # noqa: BLE001 - 扩写失败不阻断
        print(f"[wf] expand fail, degrade to single query: {str(exc)[:200]}")
        queries = []
    if not queries:
        return [question]
    return queries[:_MAX_QUERIES]


def search_multi(queries: list[str], source_type: str, topk: int) -> list[dict]:
    """对每条查询各查一次该来源,按 chunk id 去重(取最高分)后降序合并。

    `vector_store.search` 单次只吃一个 source_type,故必须多次调用;任何失败都退化为
    少查几条/空结果,不抛异常(spec §10)。
    """
    queries = [q for q in (queries or []) if q and q.strip()]
    if not queries:
        return []
    try:
        vectors = embed(queries)
    except Exception as exc:  # noqa: BLE001 - 嵌入失败整段降级为空
        print(f"[wf] search_multi embed fail: {str(exc)[:200]}")
        return []
    merged: dict[int, dict] = {}
    for vector in vectors:
        try:
            hits = search(vector, topk, source_type)
        except Exception as exc:  # noqa: BLE001 - 单条查询失败不拖垮其余
            print(f"[wf] search_multi fail source_type={source_type}: {str(exc)[:200]}")
            continue
        for hit in hits:
            prev = merged.get(hit["id"])
            if prev is None or hit.get("score", 0.0) > prev.get("score", 0.0):
                merged[hit["id"]] = hit
    return sorted(merged.values(), key=lambda h: h.get("score", 0.0), reverse=True)
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_expand.py -q
```

Expected: `12 passed`。

- [ ] **Step 5: 追记 dev-notes 阶段 3(第 7 个任务)并提交**

```powershell
git add potry-ai-agent/workflow/expand.py potry-ai-agent/tests/test_workflow_expand.py dev-notes/ch05.md
git commit -m "feat(ch05): Query 扩写与多查询检索去重合并(失败降级单条)"
```

---

## Task 8: `workflow/ruling.py`(槽位检查 / 候选卡片 / policy 条款检索)

**Files:**
- Create: `potry-ai-agent/workflow/ruling.py`
- Test: `potry-ai-agent/tests/test_workflow_ruling.py`

- [ ] **Step 1: 写失败测试**

`potry-ai-agent/tests/test_workflow_ruling.py`:

```python
"""判定子流程共用逻辑:槽位检查(取对象/下发候选)/ policy 条款检索。"""
import pytest
from langchain_core.messages import AIMessage

from app_storage import CORRECTION_CATEGORIES
from config import Settings
from prompts import SLOT_NO_CANDIDATE_REPLY, SLOT_PROMPT_REPLY
from workflow import ruling


class ScriptedLLM:
    def __init__(self, reply="", boom=False):
        self.reply = reply
        self.boom = boom

    async def ainvoke(self, messages):
        if self.boom:
            raise ConnectionError("upstream down")
        return AIMessage(content=self.reply)


class FakeKnowledgeStorage:
    def __init__(self, chunks=None):
        self.chunks = chunks or {}

    def get_chunk(self, chunk_id):
        return self.chunks.get(chunk_id)


class FakeDeps:
    def __init__(self, llm=None, chunks=None, milvus_topk=5):
        self.llm = llm or ScriptedLLM()
        self.knowledge_storage = FakeKnowledgeStorage(chunks)
        self.settings = Settings(
            llm_base_url="http://fake", llm_api_key="CONFIGURE_LOCALLY", llm_model="fake",
            history_max_tokens=2000, llm_temperature=0.7,
            mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
            milvus_topk=milvus_topk,
        )


def test_parse_slot_title_accepts_plain_json():
    assert ruling.parse_slot_title('{"title": "静夜思"}') == "静夜思"


def test_parse_slot_title_returns_none_for_null_or_garbage():
    assert ruling.parse_slot_title('{"title": null}') is None
    assert ruling.parse_slot_title("应该是静夜思吧") is None
    assert ruling.parse_slot_title('{"title": "  "}') is None


def test_build_candidates_dedupes_by_poem_id(monkeypatch):
    chunks = {
        1: {"source_id": 11, "title": "静夜思", "writer": "李白", "dynasty": "唐"},
        2: {"source_id": 11, "title": "静夜思", "writer": "李白", "dynasty": "唐"},
        3: {"source_id": 22, "title": "春晓", "writer": "孟浩然", "dynasty": "唐"},
    }
    monkeypatch.setattr(
        ruling.expand, "search_multi",
        lambda queries, source_type, topk: [
            {"id": 1, "score": 0.82, "source_type": source_type},
            {"id": 2, "score": 0.91, "source_type": source_type},   # 同一首诗的高分块
            {"id": 3, "score": 0.70, "source_type": source_type},
        ],
    )
    cands = ruling.build_candidates("静夜思", FakeDeps(chunks=chunks))
    assert [c["poemId"] for c in cands] == [11, 22]         # 按 poems 去重
    assert cands[0]["score"] == 0.91                        # 取该诗最高分
    assert cands[0]["title"] == "静夜思" and cands[0]["writer"] == "李白"


def test_build_candidates_skips_hits_without_chunk(monkeypatch):
    monkeypatch.setattr(
        ruling.expand, "search_multi",
        lambda queries, source_type, topk: [{"id": 999, "score": 0.9, "source_type": source_type}],
    )
    assert ruling.build_candidates("x", FakeDeps(chunks={})) == []


@pytest.mark.asyncio
async def test_resolve_slot_uses_selected_poem_id(monkeypatch):
    monkeypatch.setattr(ruling, "fetch_poem", lambda poem_id: {"poemId": poem_id, "title": "静夜思"})
    out = await ruling.resolve_slot({"selected_poem_id": 7, "resolved_input": "它合律吗"}, FakeDeps())
    assert out == {"slot_target": {"poemId": 7, "title": "静夜思"}, "pending_subflow": False}


@pytest.mark.asyncio
async def test_resolve_slot_finds_target_by_extracted_title(monkeypatch):
    monkeypatch.setattr(ruling, "fetch_poem", lambda poem_id: {"poemId": poem_id, "title": "静夜思"})
    monkeypatch.setattr(
        ruling.expand, "search_multi",
        lambda queries, source_type, topk: [{"id": 1, "score": 0.9, "source_type": source_type}],
    )
    deps = FakeDeps(llm=ScriptedLLM(reply='{"title": "静夜思"}'), chunks={1: {"source_id": 11}})
    out = await ruling.resolve_slot({"resolved_input": "静夜思合不合律"}, deps)
    assert out["slot_target"] == {"poemId": 11, "title": "静夜思"}
    assert out["pending_subflow"] is False


@pytest.mark.asyncio
async def test_resolve_slot_offers_cards_when_no_target(monkeypatch):
    monkeypatch.setattr(
        ruling.expand, "search_multi",
        lambda queries, source_type, topk: [{"id": 1, "score": 0.9, "source_type": source_type}],
    )
    deps = FakeDeps(llm=ScriptedLLM(reply='{"title": null}'),
                    chunks={1: {"source_id": 11, "title": "静夜思", "writer": "李白", "dynasty": "唐"}})
    out = await ruling.resolve_slot({"resolved_input": "这句合不合律"}, deps)
    assert out["pending_subflow"] is True
    assert out["slot_target"] is None
    assert out["answer"] == SLOT_PROMPT_REPLY
    assert out["candidates"][0]["poemId"] == 11


@pytest.mark.asyncio
async def test_resolve_slot_asks_for_clue_when_no_candidates(monkeypatch):
    monkeypatch.setattr(
        ruling.expand, "search_multi", lambda queries, source_type, topk: []
    )
    deps = FakeDeps(llm=ScriptedLLM(reply='{"title": null}'))
    out = await ruling.resolve_slot({"resolved_input": "这句合不合律"}, deps)
    assert out["pending_subflow"] is False          # 无卡片可下发 → 不进等待态
    assert out["answer"] == SLOT_NO_CANDIDATE_REPLY


def test_after_slot_check_branches(monkeypatch):
    assert ruling.after_slot_check({"slot_target": {"poemId": 1}}) == "expand_query"
    assert ruling.after_slot_check({"slot_target": None}) == "log"


def test_collect_policy_returns_clauses_and_categories(monkeypatch):
    monkeypatch.setattr(
        ruling.expand, "search_multi",
        lambda queries, source_type, topk: [{"id": 5, "score": 0.8, "source_type": source_type, "raw_text": "偶句押韵"}],
    )
    out = ruling.collect_policy({"expanded_queries": ["押韵", "平仄"]}, FakeDeps())
    assert out["policy_hits"][0]["raw_text"] == "偶句押韵"
    assert out["correction_categories"] == list(CORRECTION_CATEGORIES)


def test_collect_policy_falls_back_to_resolved_input(monkeypatch):
    seen = {}

    def fake_search(queries, source_type, topk):
        seen["queries"] = queries
        return []

    monkeypatch.setattr(ruling.expand, "search_multi", fake_search)
    out = ruling.collect_policy({"resolved_input": "七律"}, FakeDeps())
    assert seen["queries"] == ["七律"]
    assert out["policy_hits"] == []
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_ruling.py -q
```

Expected: FAIL,`ModuleNotFoundError: No module named 'workflow.ruling'`。

- [ ] **Step 3: 实现 `workflow/ruling.py`**

```python
"""判定子流程共用逻辑(两条子流程只差 `subflow_kind` 与检索哪类 policy,spec §8)。

职责:
1. 槽位检查:优先用用户点选的 `selected_poem_id`;否则用 LLM 从 query 抽对象;
   抽不到 → 用 query 做一次 poem 源向量检索取候选卡片下发,收尾等回填(两段式第一段);
2. 取对象数据:命中对象后回查 `potry` 表拿权威数据(标题/作者/朝代/体裁/原文/译文);
3. 规则条款检索:对扩写后的多条查询各查一次 `policy` 源,去重合并。
"""
from app_storage import CORRECTION_CATEGORIES
from prompts import SLOT_EXTRACT_PROMPT, SLOT_NO_CANDIDATE_REPLY, SLOT_PROMPT_REPLY
from workflow import expand

_MAX_CANDIDATES = 5
_MAX_CONTENT = 300  # 回灌截断,防上下文爆炸(与 tools/poetry_tools 同一口径)


def fetch_poem(poem_id: int) -> dict | None:
    """取诗作权威数据(potry 表)。**单一入口**,测试可 monkeypatch 本函数。"""
    from sqlalchemy import select

    from config import load_settings
    from db import Potry, new_session

    try:
        with new_session(load_settings().mysql_url) as session:
            row = session.execute(select(Potry).where(Potry.id == poem_id)).scalars().first()
    except Exception as exc:  # noqa: BLE001 - 回查失败按"取不到"处理
        print(f"[wf] fetch_poem fail id={poem_id}: {str(exc)[:200]}")
        return None
    if row is None:
        return None
    content = (row.content or "")[:_MAX_CONTENT]
    translation = (row.translation or "")[:_MAX_CONTENT]
    return {
        "poemId": row.id,
        "title": row.title or "",
        "writer": row.writer or "",
        "dynasty": row.dynasty or "",
        "type": row.type or "",
        "content": content,
        "translation": translation,
    }


def parse_slot_title(text: str) -> str | None:
    """解析 `{"title": "..."}`;null / 空白 / 解析失败 → None(不硬猜,spec §10)。"""
    import json

    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError, AttributeError):
        return None
    title = str(data.get("title") or "").strip()
    return title or None


async def extract_slot_title(llm, question: str) -> str | None:
    """用 LLM 从问题里抽诗作对象;失败一律当"没抽到"。"""
    try:
        message = await llm.ainvoke(SLOT_EXTRACT_PROMPT.invoke({"question": question}))
        return parse_slot_title(message.content or "")
    except Exception as exc:  # noqa: BLE001 - 抽取失败按缺槽位处理
        print(f"[wf] extract slot fail: {str(exc)[:200]}")
        return None


def build_candidates(question: str, deps, limit: int = _MAX_CANDIDATES) -> list[dict]:
    """用 query 做一次 poem 源检索,按**诗作**去重(取该诗最高分块)后取 top-k 作候选卡片。

    hit 的 `id` 是 chunk id;卡片的 `poemId` 取 `chunk.source_id`(= potry.id)。
    """
    hits = expand.search_multi([question], "poem", deps.settings.milvus_topk)
    seen: dict[int, dict] = {}
    for hit in hits:
        chunk = None
        try:
            if deps.knowledge_storage is not None:
                chunk = deps.knowledge_storage.get_chunk(hit["id"])
        except Exception as exc:  # noqa: BLE001 - 回查失败跳过该命中
            print(f"[wf] candidate chunk fail id={hit.get('id')}: {str(exc)[:200]}")
        if not chunk:
            continue
        poem_id = chunk.get("source_id")
        if poem_id is None:
            continue
        candidate = {
            "poemId": int(poem_id),
            "title": hit.get("title") or chunk.get("title") or "",
            "writer": hit.get("writer") or chunk.get("writer") or "",
            "dynasty": hit.get("dynasty") or chunk.get("dynasty") or "",
            "score": round(float(hit.get("score", 0.0)), 4),
        }
        prev = seen.get(poem_id)
        if prev is None or candidate["score"] > prev["score"]:
            seen[poem_id] = candidate
    ordered = sorted(seen.values(), key=lambda c: c["score"], reverse=True)
    return ordered[:limit]


async def resolve_slot(state: dict, deps) -> dict:
    """槽位检查节点:拿到对象 → 继续子流程;拿不到 → 下发候选卡片等回填。"""
    selected = state.get("selected_poem_id")
    if selected:
        target = fetch_poem(int(selected))
        if target:
            return {"slot_target": target, "pending_subflow": False}
    question = state.get("resolved_input", "")
    title = await extract_slot_title(deps.llm, question)
    if title:
        found = build_candidates(title, deps)
        if found:
            target = fetch_poem(found[0]["poemId"])
            if target:
                return {"slot_target": target, "pending_subflow": False}
    candidates = build_candidates(question, deps)
    if not candidates:
        # 连候选都没有:不下发卡片(否则前端无从点选),如实请用户补充线索
        return {"slot_target": None, "pending_subflow": False, "answer": SLOT_NO_CANDIDATE_REPLY}
    return {
        "candidates": candidates, "pending_subflow": True, "slot_target": None,
        "answer": SLOT_PROMPT_REPLY,
    }


def after_slot_check(state: dict) -> str:
    """槽位检查后条件边:拿到对象 → 扩写+检索条款;否则日志收尾(答案已就位)。"""
    return "expand_query" if state.get("slot_target") else "log"


def collect_policy(state: dict, deps) -> dict:
    """对扩写后的多条查询各查一次 `policy` 源,去重合并后作为"规则条款依据"。

    同时把纠错单固定类目写进 state —— 判定子流程**总是**给出纠错单入口(已请示用户获批)。
    """
    queries = state.get("expanded_queries") or [state.get("resolved_input", "")]
    hits = expand.search_multi(queries, "policy", deps.settings.milvus_topk)
    return {"policy_hits": hits, "correction_categories": list(CORRECTION_CATEGORIES)}
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_ruling.py -q
```

Expected: `12 passed`。

- [ ] **Step 5: 追记 dev-notes 阶段 3(第 8 个任务)并提交**

```powershell
git add potry-ai-agent/workflow/ruling.py potry-ai-agent/tests/test_workflow_ruling.py dev-notes/ch05.md
git commit -m "feat(ch05): 判定子流程槽位检查/候选卡片/policy 条款检索"
```

---

## Task 9: 节点接线(条件边 + 判定子流程 + Agent 判定种子)+ 图装配

**Files:**
- Modify: `potry-ai-agent/workflow/nodes.py`
- Modify: `potry-ai-agent/workflow/agent_react.py`
- Modify: `potry-ai-agent/workflow/graph.py`
- Test: `potry-ai-agent/tests/test_workflow_nodes.py`(追加)
- Test: `potry-ai-agent/tests/test_workflow_graph.py`(追加 + 改节点集断言)

- [ ] **Step 1: 追加节点测试**

追加到 `potry-ai-agent/tests/test_workflow_nodes.py` 末尾(并在顶部 import 补 `after_resolve, after_slot_check, expand_query_node, retrieve_policy_node, slot_check_node`),并做两处既有用例改造:

**(1)** `test_resolve_node_passes_through_and_resets_turn_fields` 改为异步(Task 9 起 `resolve_node` 是协程):

```python
@pytest.mark.asyncio
async def test_resolve_node_passes_through_and_resets_turn_fields():
    _deps(ScriptedLLM())
    out = await resolve_node({"user_input": "那首讲月亮的叫啥"})
    assert out["resolved_input"] == "那首讲月亮的叫啥"
    assert out["actions"] == []
    assert out["iterations"] == 0
    assert out["tokens_used"] == 0
    assert out["gate_status"] == "skip"
    assert out["tool_trace"] == []
    assert out["retrieved"] == []
    assert out["evidence_score"] is None
    assert out["answer"] == ""
    assert out["fallback_reason"] == ""
    assert out["confidence"] == 0.0
    assert out["query_changed"] is False
    assert out["policy_hits"] == []
    assert out["correction_categories"] == []
    assert out["pending_subflow"] is False and out["candidates"] == []
```

**(2)** `test_log_node_prints_structured_line_and_persists` 的期望行把 `conf` 补上:

```python
    assert line.startswith("[wf] intent=find_poet conf=- route=business gate=skip score=- iters=2 tokens=321 elapsed=")
```

(该用例其余断言不变;`test_log_node_prints_score_when_retrieval_happened` / `test_log_node_survives_storage_failure` 不受影响。)

新增用例:

```python
@pytest.mark.asyncio
async def test_resolve_node_rewrites_with_history(monkeypatch):
    import workflow.nodes as nodes_module

    async def fake_resolve(llm, question, history):
        return ("《静夜思》这首诗合不合律", True)

    monkeypatch.setattr(nodes_module, "resolve_input", fake_resolve)
    _deps(ScriptedLLM())
    out = await resolve_node({"user_input": "它合不合律", "history": [{"role": "user", "content": "《静夜思》是谁写的"}]})
    assert out["resolved_input"] == "《静夜思》这首诗合不合律"
    assert out["query_changed"] is True
    assert out["pending_subflow"] is False and out["candidates"] == []


@pytest.mark.asyncio
async def test_resolve_node_resumes_without_calling_model(monkeypatch):
    import workflow.nodes as nodes_module
    calls = {"n": 0}

    async def fake_resolve(llm, question, history):
        calls["n"] += 1
        return ("不该被调用", True)

    monkeypatch.setattr(nodes_module, "resolve_input", fake_resolve)
    _deps(ScriptedLLM())
    state = {"user_input": "", "selected_poem_id": 7, "pending_subflow": True,
             "resolved_input": "这句合不合律", "subflow_kind": "meter"}
    out = await resolve_node(state)
    assert calls["n"] == 0                       # 续跑不重新消解
    assert out["pending_subflow"] is True
    assert out["resolved_input"] == "这句合不合律"  # 沿用上一轮结果(本节点不覆盖)


def test_after_resolve_branches():
    assert after_resolve({"pending_subflow": True}) == "slot_check"
    assert after_resolve({"pending_subflow": False}) == "classify"


@pytest.mark.asyncio
async def test_slot_check_node_delegates_to_ruling(monkeypatch):
    import workflow.nodes as nodes_module

    async def fake_resolve_slot(state, deps):
        return {"slot_target": {"poemId": 1}, "pending_subflow": False}

    monkeypatch.setattr(nodes_module.ruling, "resolve_slot", fake_resolve_slot)
    _deps()
    assert await slot_check_node({"resolved_input": "x"}) == {"slot_target": {"poemId": 1}, "pending_subflow": False}


def test_after_slot_check_branches():
    assert after_slot_check({"slot_target": {"poemId": 1}}) == "expand_query"
    assert after_slot_check({"slot_target": None}) == "log"


@pytest.mark.asyncio
async def test_expand_query_node_fills_queries(monkeypatch):
    import workflow.nodes as nodes_module

    async def fake_expand(llm, question):
        return ["七律的句数字数", "律诗对仗要求"]

    monkeypatch.setattr(nodes_module.expand, "expand_queries", fake_expand)
    _deps()
    assert await expand_query_node({"resolved_input": "这首是不是七律"}) == {
        "expanded_queries": ["七律的句数字数", "律诗对仗要求"]
    }


def test_retrieve_policy_node_records_clauses_and_categories(monkeypatch):
    _deps()
    import workflow.nodes as nodes_module
    monkeypatch.setattr(
        nodes_module.expand, "search_multi",
        lambda queries, source_type, topk: [{"id": 3, "score": 0.7, "source_type": source_type, "raw_text": "偶句押韵"}],
    )
    out = retrieve_policy_node({"expanded_queries": ["押韵"], "subflow_kind": "meter", "slot_target": {"title": "静夜思"}})
    assert out["policy_hits"][0]["raw_text"] == "偶句押韵"
    assert out["correction_categories"] == list(CORRECTION_CATEGORIES)


def test_log_node_prints_confidence_and_updates_history(capsys):
    chat = FakeChatStorage()
    _deps(chat=chat)
    out = log_node({
        "user_input": "《静夜思》是谁写的", "answer": "是李白",
        "intent": "find_poet", "confidence": 0.9, "route": "business",
        "history": [{"role": "user", "content": "上一轮"}, {"role": "assistant", "content": "上答"}],
    })
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert line.startswith("[wf] intent=find_poet conf=0.90 route=business")
    assert out["history"][-2:] == [
        {"role": "user", "content": "《静夜思》是谁写的"},
        {"role": "assistant", "content": "是李白"},
    ]


def test_log_node_replaces_last_answer_on_resume():
    _deps()
    out = log_node({
        "user_input": "", "answer": "判定结果",
        "history": [{"role": "user", "content": "这句合不合律"},
                    {"role": "assistant", "content": "先确认一下,你问的是哪首诗?"}],
    })
    assert out["history"][-1] == {"role": "assistant", "content": "判定结果"}
    assert len(out["history"]) == 2          # 续跑不新增 user 轮
```

`CORRECTION_CATEGORIES` 需在该测试文件顶部 import:`from app_storage import CORRECTION_CATEGORIES`。

- [ ] **Step 2: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_nodes.py -q
```

Expected: FAIL(`after_resolve` / `slot_check_node` / `expand_query_node` / `retrieve_policy_node` 未定义;`log_node` 行格式未变)。

- [ ] **Step 3: 改 `workflow/nodes.py`**

(a) import 区追加(`CORRECTION_CATEGORIES` 由 `ruling.collect_policy` 内部使用,`nodes.py` 无需 import;测试文件自己 import):

```python
from workflow import expand, ruling
from workflow.resolve import resolve_input
from workflow.state import HISTORY_TURNS, PER_TURN_RESET
```

(b) `resolve_node` 改为正式版(异步、消解改写、续跑跳过):

```python
async def resolve_node(state: dict) -> dict:
    """指代消解 + Query 改写(正式版):结合本会话历史;已完整则原样透传。

    同时**归零本轮字段**并处置两段式续跑的跨轮标记:
    - 有 `selected_poem_id` 且上一轮处于等待回填 → 续跑(沿用上一轮消解结果,不调模型);
    - 否则按新轮处理,清掉等待态与候选。
    """
    deps = get_deps()
    selected = state.get("selected_poem_id")
    resume = bool(selected) and bool(state.get("pending_subflow"))
    out: dict = {**PER_TURN_RESET, "selected_poem_id": selected, "candidates": [], "pending_subflow": resume}
    if resume:
        print("[wf] resolve resume=续跑(沿用上一轮消解结果)")
        return out
    resolved, changed = await resolve_input(deps.llm, (state.get("user_input") or "").strip(), state.get("history") or [])
    out["resolved_input"] = resolved
    out["query_changed"] = changed
    print(f"[wf] resolve changed={str(changed).lower()} query={resolved}")
    return out
```

(c) 追加三个判定子流程节点与两条条件边(放在 `route_node` 之后、`retrieve_node` 之前):

```python
async def slot_check_node(state: dict) -> dict:
    """判定子流程第一步:拿到诗作对象 → 继续;拿不到 → 下发诗词卡片等用户点选。"""
    return await ruling.resolve_slot(state, get_deps())


def after_slot_check(state: dict) -> str:
    """槽位检查后条件边。"""
    return ruling.after_slot_check(state)


async def expand_query_node(state: dict) -> dict:
    """判定子流程第二步:把问题扩写成多条检索查询(失败降级单条原 query)。"""
    queries = await expand.expand_queries(get_deps().llm, state.get("resolved_input", ""))
    return {"expanded_queries": queries}


def retrieve_policy_node(state: dict) -> dict:
    """判定子流程第三步:多查询检索 `policy` 条款并合并;同时挂上纠错单类目。"""
    out = ruling.collect_policy(state, get_deps())
    target = (state.get("slot_target") or {}).get("title") or "-"
    print(
        f"[wf] subflow kind={state.get('subflow_kind', '-')} target={target} "
        f"policy={len(out['policy_hits'])}"
    )
    return out
```

(d) 追加 `after_resolve` 条件边(放在 `after_route` 之前):

```python
def after_resolve(state: dict) -> str:
    """消解后条件边:处于等待回填的续跑 → 直接进判定子流程(跳过分类);否则正常分类。"""
    return "slot_check" if state.get("pending_subflow") else "classify"
```

(e) `log_node` 补 `conf` 与 `history`:

```python
def log_node(state: dict) -> dict:
    """日志记录:一行结构化日志(验收观测点)+ 落 messages 表 + 累积本会话 history。"""
    elapsed = int((time.monotonic() - state.get("started_at", time.monotonic())) * 1000)
    score = state.get("evidence_score")
    score_text = f"{score:.4f}" if isinstance(score, (int, float)) else "-"
    confidence = state.get("confidence")
    conf_text = f"{confidence:.2f}" if isinstance(confidence, (int, float)) else "-"
    print(
        f"[wf] intent={state.get('intent', '-')} conf={conf_text} route={state.get('route', '-')} "
        f"gate={state.get('gate_status', 'skip')} score={score_text} "
        f"iters={state.get('iterations', 0)} tokens={state.get('tokens_used', 0)} elapsed={elapsed}"
    )
    _persist_turn(state)
    return {"history": _next_history(state)}


def _next_history(state: dict) -> list[dict]:
    """累积 history(仅 user 原问 + 最终回答),裁到最近 HISTORY_TURNS 轮。

    续跑轮(用户没发新消息)把上一条 assistant 回答**替换**为本次判定结果,不新增 user 轮。
    """
    rows = list(state.get("history") or [])
    question = (state.get("user_input") or "").strip()
    answer = state.get("answer", "")
    if not question and rows and rows[-1].get("role") == "assistant":
        rows[-1] = {"role": "assistant", "content": answer}
    else:
        if question:
            rows.append({"role": "user", "content": question})
        rows.append({"role": "assistant", "content": answer})
    return rows[-(2 * HISTORY_TURNS):]
```

> 提示:(a) 里 `PER_TURN_RESET` 供 `resolve_node` 使用、`HISTORY_TURNS` 供 `_next_history` 使用,两个 import 都有实际消费点,不要删。

- [ ] **Step 4: 改 `workflow/agent_react.py`(判定子流程的种子消息)**

把 `_seed_messages` 改为:

```python
def _seed_messages(state: dict) -> list:
    """首轮消息:判定子流程注入「诗作权威数据 + 规则条款」;知识类注入检索片段(spec §7/§8.5)。"""
    if state.get("subflow_kind"):
        return [HumanMessage(content=_ruling_seed(state))]
    question = state.get("resolved_input", "")
    retrieved = state.get("retrieved") or []
    if not retrieved:
        return [HumanMessage(content=question)]
    evidence = "\n\n".join(
        f"[{h.get('source_type', '')}|{h.get('title') or ''}] {h.get('text') or ''}".strip()
        for h in retrieved
    )
    return [HumanMessage(content=f"参考资料:\n{evidence}\n\n用户问题:{question}")]


def _ruling_seed(state: dict) -> str:
    """判定子流程的 prompt:诗作权威数据 + 规则条款 + 「只判能不能/对不对」的硬约束。"""
    target = state.get("slot_target") or {}
    lines = [
        "【待判定的诗作(权威数据)】",
        f"标题:{target.get('title') or '-'}",
        f"作者:{target.get('writer') or '-'}",
        f"朝代:{target.get('dynasty') or '-'}",
        f"体裁:{target.get('type') or '-'}",
        f"原文:{(target.get('content') or '').strip()}",
        f"译文:{(target.get('translation') or '').strip()}",
        "",
        "【适用规则条款】",
    ]
    hits = state.get("policy_hits") or []
    for hit in hits:
        text = (hit.get("raw_text") or hit.get("chunk_text") or "").strip()
        if text:
            lines.append(f"- {text}")
    if not hits:
        lines.append("(未检索到相关规则条款:依据不足时请如实说明不确定)")
    lines += ["", RULING_JUDGE_INSTRUCTION, "", f"用户问题:{state.get('resolved_input', '')}"]
    return "\n".join(lines)
```

并把 import 改为:

```python
from prompts import RULING_JUDGE_INSTRUCTION
```

- [ ] **Step 5: 改 `workflow/graph.py`**

替换 import 区与 `build_graph`:

```python
from workflow.nodes import (
    after_gate,
    after_resolve,
    after_route,
    after_slot_check,
    classify_node,
    expand_query_node,
    gate_node,
    log_node,
    resolve_node,
    retrieve_node,
    retrieve_policy_node,
    route_node,
    slot_check_node,
)
```

```python
def build_graph(checkpointer):
    """按固定顺序装配并编译(spec §4)。"""
    builder = StateGraph(WorkflowState)
    builder.add_node("resolve", resolve_node)
    builder.add_node("classify", classify_node)
    builder.add_node("route", route_node)
    builder.add_node("slot_check", slot_check_node)
    builder.add_node("expand_query", expand_query_node)
    builder.add_node("retrieve_policy", retrieve_policy_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("gate", gate_node)
    builder.add_node("agent", agent_node)
    builder.add_node("tool_node", tool_node)
    builder.add_node("log", log_node)

    builder.add_edge(START, "resolve")
    builder.add_conditional_edges(
        "resolve", after_resolve, {"slot_check": "slot_check", "classify": "classify"}
    )
    builder.add_edge("classify", "route")
    builder.add_conditional_edges(
        "route", after_route,
        {"retrieve": "retrieve", "agent": "agent", "slot_check": "slot_check", "log": "log"},
    )
    builder.add_edge("retrieve", "gate")
    builder.add_conditional_edges("gate", after_gate, {"agent": "agent", "log": "log"})
    builder.add_conditional_edges(
        "slot_check", after_slot_check, {"expand_query": "expand_query", "log": "log"}
    )
    builder.add_edge("expand_query", "retrieve_policy")
    builder.add_edge("retrieve_policy", "agent")
    builder.add_conditional_edges(
        "agent", should_continue, {"tool_node": "tool_node", "log": "log"}
    )
    builder.add_edge("tool_node", "agent")   # ReAct 子循环:工具执行后回到 Agent
    builder.add_edge("log", END)
    return builder.compile(checkpointer=checkpointer)
```

- [ ] **Step 6: 追加图测试**

在 `tests/test_workflow_graph.py` 里:

(a) `test_graph_builds_and_has_all_nodes` 的节点集断言改为:

```python
    assert {"resolve", "classify", "route", "retrieve", "gate", "agent", "tool_node", "log",
            "slot_check", "expand_query", "retrieve_policy"} <= nodes
```

(b) 追加三个用例(文件顶部需补 `from prompts import SLOT_PROMPT_REPLY`):

```python
@pytest.mark.asyncio
async def test_other_outlet_goes_to_agent_for_clarification():
    registry, _ = make_registry()
    llm = ScriptedLLM([AIMessage(content='{"intent": "other", "confidence": 0.3}'), AIMessage(content="想聊什么?我陪你读诗。")])
    _wire(llm, registry, chat=FakeChatStorage())
    final = await _run(build_graph(InMemorySaver()), "帮我写个 Java 排序")
    assert final["route"] == intent.ROUTE_OTHER
    assert final["iterations"] == 1
    assert final["answer"] == "想聊什么?我陪你读诗。"


@pytest.mark.asyncio
async def test_ruling_outlet_asks_cards_when_slot_missing(monkeypatch):
    """缺槽位:不发 token、判定子流程收尾在下发卡片处。"""
    registry, _ = make_registry()
    _wire(ScriptedLLM([AIMessage(content='{"intent": "poem_meter", "confidence": 0.8}'),
                       AIMessage(content='{"title": null}')]),
          registry, knowledge=FakeKnowledgeStorage(chunks={1: {"source_id": 11, "title": "静夜思",
                                                               "writer": "李白", "dynasty": "唐"}}),
          chat=FakeChatStorage())

    import workflow.ruling as ruling
    monkeypatch.setattr(ruling.expand, "search_multi",
                        lambda queries, source_type, topk: [{"id": 1, "score": 0.9, "source_type": source_type}])
    final = await _run(build_graph(InMemorySaver()), "这句合不合律", session_id="slot1")
    assert final["route"] == intent.ROUTE_RULING
    assert final["subflow_kind"] == "meter"
    assert final["pending_subflow"] is True
    assert final["answer"] == SLOT_PROMPT_REPLY
    assert final["candidates"][0]["poemId"] == 11
    assert final.get("iterations", 0) == 0        # 未进 Agent


@pytest.mark.asyncio
async def test_ruling_resume_after_card_pick_judges(monkeypatch):
    """两段式续跑:第一段缺槽位下发卡片;第二段带 selectedPoemId → 跳过分类/消解,直接判定。"""
    registry, _ = make_registry()
    _wire(ScriptedLLM([
        AIMessage(content='{"intent": "poem_meter", "confidence": 0.8}'),            # 第一段:分类
        AIMessage(content='{"queries": ["七律句数字数", "律诗对仗"]}'),                  # 第二段:扩写
        AIMessage(content="这首是七律,八句七字,中间两联对仗。"),                        # 第二段:Agent 判定
    ]), registry, chat=FakeChatStorage())

    import workflow.nodes as nodes_module
    import workflow.ruling as ruling

    async def fake_resolve_slot(state, deps):
        # 无 selectedPoemId → 缺槽位等回填;有 selectedPoemId → 取到对象继续
        if state.get("selected_poem_id"):
            return {"slot_target": {"poemId": 11, "title": "静夜思", "content": "床前明月光"},
                    "pending_subflow": False}
        return {"candidates": [{"poemId": 11, "title": "静夜思"}], "pending_subflow": True,
                "slot_target": None, "answer": SLOT_PROMPT_REPLY}

    monkeypatch.setattr(nodes_module.ruling, "resolve_slot", fake_resolve_slot)
    monkeypatch.setattr(ruling.expand, "search_multi",
                        lambda queries, source_type, topk: [{"id": 5, "score": 0.8,
                                                             "source_type": source_type,
                                                             "raw_text": "七言律诗八句每句七字。"}])
    graph = build_graph(InMemorySaver())
    # 第一段:缺槽位,建立等待态(只用了 1 次 LLM 调用:分类)
    turn1 = await _run(graph, "这句合不合律", session_id="resume1")
    assert turn1["pending_subflow"] is True and turn1["subflow_kind"] == "meter"
    # 第二段:点选卡片续跑(message 空 + selectedPoemId;续跑不重新消解,故不额外调模型)
    final = await _run(graph, "", session_id="resume1", selected_poem_id=11)
    assert final["slot_target"]["poemId"] == 11
    assert final["policy_hits"][0]["raw_text"] == "七言律诗八句每句七字。"
    assert final["correction_categories"]                  # 判定完成 → 总是挂纠错单入口
    injected = [m for m in final["messages"]
                if isinstance(m, HumanMessage) and "床前明月光" in m.content]
    assert injected, "判定子流程必须把诗作权威数据注入 Agent prompt"
```

> `_run` 的 `**extra` 已支持任意初始键,故 `selected_poem_id=11` 直接透传即可。

- [ ] **Step 7: 跑测试确认通过**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_nodes.py tests/test_workflow_graph.py tests/test_workflow_agent_react.py -q
```

Expected: 全绿。

- [ ] **Step 8: 全量回归**

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Expected: 全绿。

- [ ] **Step 9: 追记 dev-notes 阶段 3(第 9 个任务)并提交**

```powershell
git add potry-ai-agent/workflow/nodes.py potry-ai-agent/workflow/agent_react.py potry-ai-agent/workflow/graph.py potry-ai-agent/tests/test_workflow_nodes.py potry-ai-agent/tests/test_workflow_graph.py dev-notes/ch05.md
git commit -m "feat(ch05): 六出口条件边、判定子流程三节点与两段式续跑接线"
```

---

## Task 10: `main.py` 接线(续跑入参 / 三类 action 帧 / 纠错单端点 / trace 扩展)

**Files:**
- Modify: `potry-ai-agent/main.py`
- Test: `potry-ai-agent/tests/test_workflow_endpoint.py`(追加)

- [ ] **Step 1: 追加端点测试**

追加到 `potry-ai-agent/tests/test_workflow_endpoint.py` 末尾:

```python
def _stream(client, payload):
    with client.stream("POST", "/agent/workflow", json=payload) as resp:
        assert resp.status_code == 200
        return "".join(resp.iter_text())


def test_workflow_passes_selected_poem_id_into_state(monkeypatch):
    client, fake = _client(monkeypatch, {"route": "ruling", "answer": "判定", "actions": []})
    _stream(client, {"sessionId": "s20", "message": "", "selectedPoemId": 7})
    assert fake.records[0][0]["selected_poem_id"] == 7
    assert fake.records[0][0]["user_input"] == ""


def test_workflow_emits_pick_poem_frame_and_awaiting_status(monkeypatch):
    final = {
        "route": "ruling", "answer": "先确认一下,你问的是哪首诗?",
        "actions": [], "tool_trace": [], "pending_subflow": True,
        "candidates": [{"poemId": 11, "title": "静夜思", "writer": "李白", "dynasty": "唐", "score": 0.9123}],
    }
    client, _ = _client(monkeypatch, final)
    body = _stream(client, {"sessionId": "s21", "message": "这句合不合律"})
    assert '"action": "pick_poem"' in body
    assert '"poemId": 11' in body
    assert '"status": "awaiting_slot"' in body


def test_workflow_emits_correction_form_frame(monkeypatch):
    final = {
        "route": "ruling", "answer": "这首是七律。", "actions": [], "tool_trace": [],
        "pending_subflow": False, "correction_categories": ["格律错误", "原文有误"],
    }
    client, _ = _client(monkeypatch, final)
    body = _stream(client, {"sessionId": "s22", "message": "这首是不是七律"})
    assert '"action": "open_correction_form"' in body
    assert '"格律错误"' in body
    assert '"status": "ok"' in body


def test_workflow_trace_frame_reports_ch05_fields(monkeypatch):
    final = {
        "route": "ruling", "answer": "判定", "actions": [], "tool_trace": [],
        "intent": "poem_meter", "confidence": 0.83, "query_changed": True,
        "subflow_kind": "meter", "policy_hits": [{"id": 1}, {"id": 2}],
    }
    client, _ = _client(monkeypatch, final)
    body = _stream(client, {"sessionId": "s23", "message": "这句合不合律"})
    assert '"confidence": 0.83' in body
    assert '"queryChanged": true' in body
    assert '"subflowKind": "meter"' in body
    assert '"policyCount": 2' in body


def test_correction_endpoint_writes_row(monkeypatch):
    captured = {}

    def fake_add_correction(category, detail=None, poem_id=None, session_id=None, userid=None):
        captured.update(category=category, detail=detail, poem_id=poem_id, session_id=session_id, userid=userid)
        return 42

    monkeypatch.setattr(main.app_storage, "add_correction", fake_add_correction)
    client = TestClient(main.app)
    resp = client.post(
        "/agent/correction",
        json={"sessionId": "s1", "poemId": 7, "category": "作者张冠李戴", "detail": "作者应为王某"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "correctionId": 42}
    assert captured == {"category": "作者张冠李戴", "detail": "作者应为王某",
                        "poem_id": 7, "session_id": "s1", "userid": None}


def test_correction_endpoint_rejects_unknown_category(monkeypatch):
    client = TestClient(main.app)
    resp = client.post("/agent/correction", json={"category": "乱填类目"})
    assert resp.status_code == 400
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_endpoint.py -q
```

Expected: FAIL(`pick_poem` 帧缺失 / `/agent/correction` 404 / trace 无新字段)。

- [ ] **Step 3: 改 `ChatRequest` 与 invoke 入参**

```python
class ChatRequest(BaseModel):
    userId: str | None = None
    sessionId: str | None = None
    message: str
    selectedPoemId: int | None = None   # Ch05 两段式续跑:用户点选的诗词卡片 id
```

`workflow_chat` 的 `ainvoke` 初始 state 改为:

```python
                {
                    "session_id": session_id,
                    "user_input": req.message,
                    "selected_poem_id": req.selectedPoemId,
                    "started_at": time.monotonic(),
                    "messages": [],
                    "tool_trace": [],
                },
```

- [ ] **Step 4: 改 `_answer_source` / `_trace_payload` 与三帧 action**

`_answer_source`:

```python
def _answer_source(final: dict) -> str:
    """回答来源标识:预设话术(含等回填的固定提示)/兜底/调工具/基于资料/模型知识。"""
    if final.get("pending_subflow") or final.get("route") in ("complaint", "chitchat"):
        return "preset"
    if final.get("fallback_reason") == "insufficient_evidence":
        return "fallback"          # 仅"检索证据不足"才算兜底;agent_error 之类不冒充
    if final.get("tool_trace"):
        return "tool"
    if final.get("gate_status") == "pass" or final.get("policy_hits"):
        return "rag"               # 知识类过闸 / 判定子流程检索到条款:基于资料作答
    return "model"
```

`_trace_payload` 的返回字典追加四项:

```python
        "confidence": final.get("confidence", 0.0),
        "queryChanged": bool(final.get("query_changed")),
        "subflowKind": final.get("subflow_kind", ""),
        "policyCount": len(final.get("policy_hits") or []),
```

`workflow_chat` 的 `gen()` 里、现有 `actions` 帧之后追加:

```python
            actions = final.get("actions") or []
            if actions:
                yield _sse("action", {"actions": actions})
            if final.get("pending_subflow"):
                yield _sse("action", {"action": "pick_poem", "candidates": final.get("candidates") or []})
            if final.get("correction_categories"):
                yield _sse("action", {"action": "open_correction_form",
                                      "categories": final.get("correction_categories")})
        except Exception as exc:  # noqa: BLE001 - 单请求失败不崩服务,补 error 帧
            yield _sse("error", {"message": str(exc)[:200]})
        yield _sse("done", {"sessionId": session_id, "source": _answer_source(final),
                            "status": "awaiting_slot" if final.get("pending_subflow") else "ok"})
```

- [ ] **Step 5: 新增 `/agent/correction`**

在 `agent_feedback` 之后追加:

```python
class CorrectionRequest(BaseModel):
    userId: str | None = None
    sessionId: str | None = None
    poemId: int | None = None
    category: str
    detail: str | None = None


@app.post("/agent/correction")
def agent_correction(req: CorrectionRequest) -> dict:
    """纠错/复核单落点:写 corrections 表(前端「提交纠错单」按钮调用;后端不自动触发)。"""
    userid = int(req.userId) if req.userId and req.userId.isdigit() else None
    try:
        correction_id = app_storage.add_correction(
            category=req.category, detail=req.detail, poem_id=req.poemId,
            session_id=req.sessionId, userid=userid,
        )
    except ValueError as exc:      # 类目非法 → 400(边界校验)
        raise HTTPException(status_code=400, detail={"message": str(exc)[:200]})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"message": str(exc)[:200]})
    return {"ok": True, "correctionId": correction_id}
```

- [ ] **Step 6: 跑测试确认通过**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_endpoint.py -q
```

Expected: 全绿(含既有 10 个用例)。

- [ ] **Step 7: 全量回归**

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Expected: 全绿。

- [ ] **Step 8: 追记 dev-notes 阶段 3(第 10 个任务)并提交**

```powershell
git add potry-ai-agent/main.py potry-ai-agent/tests/test_workflow_endpoint.py dev-notes/ch05.md
git commit -m "feat(ch05): 接线两段式续跑入参、pick_poem/纠错单 action 帧与 /agent/correction"
```

---

## Task 11: 前端诗词卡片 + 纠错单表单(Vibe Coding 例外)

**说明:** 前端属 **Vibe Coding 例外**(用户原话:我描述效果你改,不套 brainstorm/TDD/code review)。做法:直接改 `static/chat.html`,**人工在浏览器验证**;自动化取证仍走后端 SSE 帧断言(Task 10 已覆盖)。

**Files:**
- Modify: `potry-ai-agent/static/chat.html`

- [ ] **Step 1: 补样式(卡片 + 表单)**

在 `.action-btn:disabled { opacity: .4; cursor: default; }` 之后追加:

```css
  .cand-cards { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }
  .cand-card {
    border: 1px solid var(--line);
    background: #fffdf8;
    border-radius: 10px;
    padding: 10px 14px;
    cursor: pointer;
    display: flex;
    align-items: baseline;
    gap: 10px;
    transition: border-color .15s, background .15s;
  }
  .cand-card:hover { border-color: var(--gold); background: rgba(217, 185, 120, .14); }
  .cand-card .title { font-size: 15px; color: var(--ink); }
  .cand-card .meta { font-size: 12px; color: var(--ink-soft); letter-spacing: 1px; }
  .cand-card .score { margin-left: auto; font-size: 11px; color: var(--gold-soft); }
  .correction-form {
    margin-top: 10px;
    padding: 12px 14px;
    border: 1px dashed var(--line);
    border-radius: 10px;
    background: rgba(250, 246, 239, .8);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .correction-form .cap { font-size: 12px; letter-spacing: 2px; color: var(--ink-soft); }
  .correction-form select,
  .correction-form textarea {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #fffdf8;
    color: var(--ink);
    font-family: inherit;
    font-size: 14px;
    padding: 8px 10px;
    outline: none;
  }
  .correction-form textarea { resize: vertical; min-height: 56px; }
  .correction-form select:focus,
  .correction-form textarea:focus { border-color: var(--gold); }
  .correction-form .row-btns { display: flex; gap: 8px; justify-content: flex-end; }
```

- [ ] **Step 2: 把 `send()` 抽成可复用的流读取函数**

原 `send()` 里「fetch + 读 SSE」整段抽成 `streamReply(userText, extra)`(供续跑复用),`send()` 只负责取输入、加 user 行、调用它:

```js
  // 流式请求 + SSE 解析(main 与续跑共用);extra 用于续跑段携带 selectedPoemId
  async function streamReply(userText, extra) {
    const bubble = addRow("assistant", "");
    bubble.classList.add("typing");
    const body = Object.assign({ sessionId: sessionId, message: userText }, extra || {});
    let acc = "";
    const toolCalls = [];
    let finalSource = null;
    try {
      const resp = await fetch("/agent/workflow", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error((err.detail && err.detail.message) || ("请求失败 " + resp.status));
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop();
        for (const chunk of chunks) {
          const lines = chunk.split("\n");
          let event = "message";
          let data = "";
          for (const line of lines) {
            if (line.startsWith("event: ")) event = line.slice(7).trim();
            else if (line.startsWith("data: ")) data += line.slice(6);
          }
          if (!data) continue;
          const payload = JSON.parse(data);
          if (event === "meta") {
            sessionId = payload.sessionId;
          } else if (event === "tool_status") {
            const idx = toolCalls.findIndex((c) => c.tool === payload.tool && c.status === "calling");
            if (payload.status === "calling" || idx === -1) toolCalls.push(payload);
            else toolCalls[idx] = payload;
            refreshSource(bubble, finalSource, toolCalls);
          } else if (event === "token") {
            acc += payload.content;
            bubble.textContent = acc;
          } else if (event === "trace") {
            lastTrace = payload;
          } else if (event === "action") {
            handleActionFrame(bubble, payload);
          } else if (event === "done") {
            finalSource = payload.source || null;
            refreshSource(bubble, finalSource, toolCalls);
          } else if (event === "error") {
            throw new Error(payload.message || "上游出错");
          }
          messagesEl.scrollTop = messagesEl.scrollHeight;
        }
      }
      bubble.textContent = acc || "(空回复)";
      refreshSource(bubble, finalSource, toolCalls);
    } catch (e) {
      bubble.classList.remove("typing");
      bubble.parentElement.parentElement.classList.add("error");
      bubble.textContent = "出错了:" + e.message;
    } finally {
      bubble.classList.remove("typing");
    }
  }

  async function send() {
    const text = inputEl.value.trim();
    if (!text || sending) return;
    sending = true;
    sendBtn.disabled = true;
    inputEl.value = "";
    inputEl.style.height = "auto";
    addRow("user", text);
    lastUserText = text;
    lastTrace = null;
    try {
      await streamReply(text, null);
    } finally {
      sending = false;
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }
```

- [ ] **Step 3: action 帧分发:三类动作**

在 `handleAction` 之前追加(并把原 `renderActions` 的调用点从 `payload.actions` 改为经本函数分发):

```js
  // 兼容三类 action 帧:{"actions":[...]} / {"action":"pick_poem"} / {"action":"open_correction_form"}
  function handleActionFrame(bubble, payload) {
    if (payload.actions) {
      renderActions(bubble.parentElement, payload.actions);
      return;
    }
    if (payload.action === "pick_poem") {
      renderPoemCards(bubble, payload.candidates || []);
      return;
    }
    if (payload.action === "open_correction_form") {
      renderCorrectionForm(bubble, payload.categories || []);
    }
  }

  // 诗词卡片选择器:缺槽位时下发候选,点选后自动回填并把流程接着走完
  function renderPoemCards(bubble, candidates) {
    if (!candidates.length) return;
    const wrap = document.createElement("div");
    wrap.className = "cand-cards";
    const cap = document.createElement("div");
    cap.className = "cap";
    cap.textContent = "点选一首,我接着判定:";
    wrap.appendChild(cap);
    candidates.forEach((c) => {
      const card = document.createElement("div");
      card.className = "cand-card";
      const title = document.createElement("span");
      title.className = "title";
      title.textContent = "《" + (c.title || "未题") + "》";
      const meta = document.createElement("span");
      meta.className = "meta";
      meta.textContent = (c.writer || "-") + " · " + (c.dynasty || "-");
      const score = document.createElement("span");
      score.className = "score";
      score.textContent = c.score != null ? c.score.toFixed(2) : "";
      card.append(title, meta, score);
      card.addEventListener("click", () => pickPoem(c, wrap));
      wrap.appendChild(card);
    });
    bubble.parentElement.appendChild(wrap);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  async function pickPoem(candidate, wrap) {
    if (sending) return;
    sending = true;
    sendBtn.disabled = true;
    wrap.remove();                                   // 选过即收起卡片
    addRow("user", "《" + (candidate.title || "未题") + "》");
    lastTrace = null;
    try {
      await streamReply("", { selectedPoemId: candidate.poemId });
    } finally {
      sending = false;
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  // 纠错/复核单:类目下拉 + 补充说明;提交后落 corrections 表
  function renderCorrectionForm(bubble, categories) {
    if (!categories.length) return;
    const form = document.createElement("div");
    form.className = "correction-form";
    const cap = document.createElement("div");
    cap.className = "cap";
    cap.textContent = "发现数据有误?可提交纠错单";
    const select = document.createElement("select");
    categories.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      select.appendChild(opt);
    });
    const detail = document.createElement("textarea");
    detail.placeholder = "补充说明(可选)";
    const btns = document.createElement("div");
    btns.className = "row-btns";
    const submit = document.createElement("button");
    submit.className = "action-btn";
    submit.textContent = "提交纠错单";
    submit.addEventListener("click", async () => {
      submit.disabled = true;
      try {
        const resp = await fetch("/agent/correction", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sessionId: sessionId,
            poemId: (lastTrace && lastTrace.poemId) || null,
            category: select.value,
            detail: detail.value.trim() || null,
          }),
        });
        if (!resp.ok) throw new Error("提交失败 " + resp.status);
        form.replaceWith(document.createTextNode("已提交,感谢指正。"));
      } catch (e) {
        submit.disabled = false;
        addRow("assistant", "纠错单提交失败:" + e.message);
      }
    });
    btns.appendChild(submit);
    form.append(cap, select, detail, btns);
    bubble.parentElement.appendChild(form);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
```

- [ ] **Step 4: 编排轨迹面板补 Ch05 行**

`traceRows(trace, toolCalls)` 里的行数组改为(新增「消解/改写」「判定子流程」两行的信息,并把原「指代消解」行改成真实值):

```js
    const resolveText = trace.queryChanged ? "已改写 · 结合上轮指代" : "透传 · 未改写";
    const subflowText = trace.subflowKind
      ? (trace.subflowKind === "meter" ? "格律合规" : "校勘核对") + " · 条款 " + (trace.policyCount || 0) + " 条"
      : "未进入";
    return [
      ["指代消解", resolveText],
      ["意图识别", (trace.intent || "-") + (trace.confidence != null ? " · conf " + trace.confidence.toFixed(2) : "")],
      ["意图分流", (ROUTE_LABELS[route] || "-") + " · 硬编码查表"],
      ["判定子流程", subflowText],
      ["知识检索", isKnowledge ? (trace.retrievedCount || 0) + " 条 · top " + scoreText : "跳过 · 不预检索"],
      ["置信度闸", isKnowledge ? (trace.gate === "pass" ? "pass · 证据充足" : "insufficient · 已走兜底") : "跳过"],
      ["主力 Agent", agentText],
      ["日志记录", "落 messages 表 · " + (trace.tokens || 0) + " tokens" +
        (trace.elapsedMs != null ? " · " + trace.elapsedMs + "ms" : "")],
    ];
```

并把 `ROUTE_LABELS` 扩为六出口:

```js
  const ROUTE_LABELS = {
    knowledge: "知识类", business: "业务类", ruling: "判定类",
    complaint: "投诉类", chitchat: "闲聊类", other: "其他类",
  };
```

> `appendTracePanel` 里 `li.className = "step" + (i === 5 ? " focus" : "")` 的聚焦下标需从 `5` 改为 `6`(主力 Agent 现在是第 6 行,下标 6)。

- [ ] **Step 5: 人工验证(浏览器)**

启动服务后打开 `http://127.0.0.1:8000/chat`:

1. 不带诗题只问「这句合不合律」→ 回答为「先确认一下,你问的是哪首诗、哪句诗?」并弹出**诗词卡片**;点一张 → 卡片收起、自动补一行用户消息、判定结果接着流出;
2. 判定结果下方出现**「提交纠错单」表单**,类目下拉含 5 个固定类目;提交后显示「已提交,感谢指正。」且 `corrections` 表行数 +1;
3. 展开来源标识 → 编排轨迹显示 8 行(含「判定子流程 · 格律合规 · 条款 N 条」)。

- [ ] **Step 6: 追记 dev-notes 阶段 3(第 11 个任务)并提交**

```powershell
git add potry-ai-agent/static/chat.html dev-notes/ch05.md
git commit -m "feat(ch05): 聊天页诗词卡片选择器与纠错单表单(类目下拉)+ 轨迹行扩展"
```

---

# 组三 · 评估集

## Task 12: 评估集(纯 Prompt / 数据类 → 标注样例替代 TDD)

**说明:** 按用户工作要求 1,纯 Prompt 类任务把 TDD 换成**标注样例/评估集跑通验证**。本任务产出 `eval_ch05.py`(样例 + 跑批),用真实模型跑三类评估集 + 一组多轮串。

**Files:**
- Create: `potry-ai-agent/eval_ch05.py`

- [ ] **Step 1: 写评估集脚本**

`potry-ai-agent/eval_ch05.py`:

```python
"""Ch05 评估集:意图识别 / 指代消解·改写 / Query 扩写 / 多轮串 的真实模型跑批。

纯 Prompt 类任务按用户工作要求用**标注样例替代 TDD**(见 dev-notes/ch05.md 阶段 4)。
用法(在 potry-ai-agent 下执行,需 .env 可用):
    .\.venv\Scripts\python.exe eval_ch05.py
"""
import asyncio

from chat_service import build_llm
from config import load_settings
from prompts import EXPAND_PROMPT, INTENT_PROMPT, RESOLVE_PROMPT
from workflow.expand import parse_queries
from workflow.intent import parse_intent_response
from workflow.resolve import format_history, parse_resolve_result

# ---------- 意图识别评估集:8 类 × 4 条(含边界与怪问题) ----------
INTENT_SAMPLES = [
    ("《静夜思》表达了什么感情", "poem_explain"),
    ("这首诗是什么意思", "poem_explain"),
    ("帮我赏析一下《春望》", "poem_explain"),
    ("举头望明月出自哪首诗", "poem_explain"),            # 典故/出处并入 poem_explain
    ("那首讲月亮的叫啥", "find_poem"),
    ("帮我找一首写思乡的诗", "find_poem"),
    ("唐代有哪些著名的诗", "find_poem"),                  # 查朝代并入 find_poem
    ("宋朝的词人写了哪些名篇", "find_poem"),
    ("李白是什么朝代的", "find_poet"),
    ("介绍一下杜甫", "find_poet"),
    ("苏轼写过哪些名篇", "find_poet"),
    ("王维是什么风格", "find_poet"),
    ("这句合不合律", "poem_meter"),
    ("这首是不是七律", "poem_meter"),
    ("这首诗押韵出律了吗", "poem_meter"),
    ("平仄对不对", "poem_meter"),
    ("作者是不是搞错了", "poem_verify"),
    ("原文是不是有讹字", "poem_verify"),
    ("这首诗的朝代标得对吗", "poem_verify"),
    ("这首诗真的是李白写的吗", "poem_verify"),
    ("答得不对,我不满意", "complaint"),
    ("你搞错了吧", "complaint"),
    ("这个答案有误", "complaint"),
    ("太离谱了,我不接受", "complaint"),
    ("今天天气不错", "chitchat"),
    ("你叫什么名字", "chitchat"),
    ("讲个笑话吧", "chitchat"),
    ("你吃饭了吗", "chitchat"),
    ("帮我写个 Java 排序", "other"),
    ("明天股市会涨吗", "other"),
    ("随便聊聊吧", "other"),
    ("这个字怎么读来着", "other"),
]

# ---------- 指代消解/改写评估集:(history, 输入, 期望结果里必须出现的关键词, 期望 changed) ----------
RESOLVE_SAMPLES = [
    ([{"role": "user", "content": "《静夜思》是谁写的"}, {"role": "assistant", "content": "李白"}],
     "它合律吗", "静夜思", True),
    ([{"role": "user", "content": "《静夜思》是谁写的"}, {"role": "assistant", "content": "李白"}],
     "那这首诗什么意思", "静夜思", True),
    ([{"role": "user", "content": "帮我找一首写月亮的"}, {"role": "assistant", "content": "《静夜思》"}],
     "它押什么韵", "静夜思", True),
    ([{"role": "user", "content": "这首诗讲什么"}, {"role": "assistant", "content": "讲思乡"}],
     "那它合律吗", "合", True),
    ([{"role": "user", "content": "介绍一下杜甫"}, {"role": "assistant", "content": "杜甫,唐代诗人"}],
     "他写过哪些名篇", "杜甫", True),
    ([{"role": "user", "content": "《春晓》的作者是谁"}, {"role": "assistant", "content": "孟浩然"}],
     "这首诗有讹字吗", "春晓", True),
    ([{"role": "user", "content": "这首是不是七律"}, {"role": "assistant", "content": "是七律"}],
     "那它押什么韵", "七律", True),
    ([{"role": "user", "content": "《静夜思》的作者是谁"}, {"role": "assistant", "content": "李白"}],
     "它的朝代标对了吗", "静夜思", True),
    # 负例:问题本身已完整 → 必须原样透传(changed=False)
    ([{"role": "user", "content": "《静夜思》是谁写的"}, {"role": "assistant", "content": "李白"}],
     "《静夜思》这首诗表达了什么感情", "静夜思", False),
    ([{"role": "user", "content": "介绍一下杜甫"}, {"role": "assistant", "content": "杜甫,唐代诗人"}],
     "杜甫的代表作有哪些", "杜甫", False),
    ([], "《静夜思》这首诗合不合律", "静夜思", False),
    ([], "帮我找一首写梅花的诗", "梅花", False),
    ([{"role": "user", "content": "唐朝有哪些诗人"}, {"role": "assistant", "content": "李白、杜甫"}],
     "李白是什么朝代的", "李白", False),
    ([{"role": "user", "content": "这首诗什么意思"}, {"role": "assistant", "content": "讲思乡"}],
     "《静夜思》的作者是谁", "静夜思", False),
    ([{"role": "user", "content": "《春晓》是谁写的"}, {"role": "assistant", "content": "孟浩然"}],
     "孟浩然还有哪些作品", "孟浩然", False),
]

# ---------- Query 扩写评估集(仅判定子流程场景) ----------
EXPAND_SAMPLES = [
    "这首是不是七律",
    "这句合不合律",
    "这首诗押韵出律了吗",
    "平仄对不对",
    "这首诗的朝代标得对吗",
    "原文是不是有讹字",
    "作者是不是搞错了",
    "这首诗的体裁是什么",
    "这首词的分片对不对",
    "这个断句合不合词谱",
]

# ---------- 多轮串:同一会话连续三轮,逐轮断言意图(验收标准 1 的用例) ----------
MULTI_TURN = [
    ("《静夜思》是谁写的", "find_poet"),
    ("那它合律吗", "poem_meter"),
    ("帮我再找一首写月亮的", "find_poem"),
]


async def _intent_case(llm, text):
    message = await llm.ainvoke(INTENT_PROMPT.invoke({"question": text}))
    return parse_intent_response(message.content or "")


async def run_intent(llm):
    print("\n===== 评估集一:意图识别(32 条) =====")
    hits = 0
    for text, expected in INTENT_SAMPLES:
        label, conf = await _intent_case(llm, text)
        hit = label == expected
        hits += int(hit)
        print(("  OK " if hit else "  NG ") + f"{text} -> {label}({conf:.2f}) 期望 {expected}")
    rate = hits / len(INTENT_SAMPLES)
    print(f"意图准确率 {hits}/{len(INTENT_SAMPLES)} = {rate:.1%}")
    assert rate >= 0.80, f"意图准确率 {rate:.1%} < 80%"
    return rate


async def run_resolve(llm):
    print("\n===== 评估集二:指代消解 / Query 改写(15 条) =====")
    hits = 0
    for history, text, keyword, expect_changed in RESOLVE_SAMPLES:
        message = await llm.ainvoke(
            RESOLVE_PROMPT.invoke({"history": format_history(history), "question": text})
        )
        query, changed = parse_resolve_result(message.content or "")
        if not query:
            query, changed = text, False
        hit = (keyword in query) and (changed == expect_changed)
        hits += int(hit)
        print(("  OK " if hit else "  NG ") + f"{text} -> {query}(changed={changed}) 期望含「{keyword}」changed={expect_changed}")
    rate = hits / len(RESOLVE_SAMPLES)
    print(f"消解/透传正确率 {hits}/{len(RESOLVE_SAMPLES)} = {rate:.1%}")
    assert rate >= 0.80, f"消解正确率 {rate:.1%} < 80%"
    return rate


async def run_expand(llm):
    print("\n===== 评估集三:Query 扩写(10 条) =====")
    parseable = in_range = 0
    for text in EXPAND_SAMPLES:
        message = await llm.ainvoke(EXPAND_PROMPT.invoke({"question": text}))
        queries = parse_queries(message.content or "")
        parseable += int(bool(queries))
        ok_range = 2 <= len(queries) <= 5
        in_range += int(ok_range)
        print(("  OK " if ok_range else "  NG ") + f"{text} -> {len(queries)} 条:{queries}")
    parse_rate = parseable / len(EXPAND_SAMPLES)
    range_rate = in_range / len(EXPAND_SAMPLES)
    print(f"JSON 可解析率 {parseable}/{len(EXPAND_SAMPLES)} = {parse_rate:.1%};2–5 条占比 {range_rate:.1%}")
    assert parse_rate >= 0.90 and range_rate >= 0.80, "扩写评估集未达阈值"
    return parse_rate


async def run_multi_turn(llm):
    print("\n===== 评估集四:多轮串(问诗人 → 判格律 → 查诗词) =====")
    history = []
    hits = 0
    for text, expected in MULTI_TURN:
        label, conf = await _intent_case(llm, text)
        hit = label == expected
        hits += int(hit)
        message = await llm.ainvoke(RESOLVE_PROMPT.invoke({"history": format_history(history), "question": text}))
        resolved, changed = parse_resolve_result(message.content or "")
        if not resolved:
            resolved, changed = text, False
        print(("  OK " if hit else "  NG ") + f"{text} -> intent={label}({conf:.2f}) 期望 {expected};resolve={resolved}(changed={changed})")
        history += [{"role": "user", "content": text}, {"role": "assistant", "content": "(上轮回答)"}]
    rate = hits / len(MULTI_TURN)
    print(f"多轮意图准确率 {hits}/{len(MULTI_TURN)} = {rate:.1%}")
    assert rate == 1.0, "多轮串必须逐轮判对(验收标准 1)"
    return rate


async def main():
    settings = load_settings()
    llm = build_llm(settings)
    await run_intent(llm)
    await run_resolve(llm)
    await run_expand(llm)
    await run_multi_turn(llm)
    print("\n[eval] 全部评估集通过")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 跑评估集(真实模型)**

```powershell
.\.venv\Scripts\python.exe eval_ch05.py
```

把完整输出(逐条 + 各准确率)原样贴进 `dev-notes/ch05.md` 阶段 4。

- [ ] **Step 3: 处理偏差(若有)**

- 个别判错且属**标注口径问题**(如"这个字怎么读来着"本可算 chitchat)→ **改标注**并在 dev-notes 记"翻车与返工",不动 prompt;
- **同类系统性错判**(如 4 条 `poem_verify` 全判 `complaint`)→ 回 `prompts.py` 补一句边界区分规则后重跑,并留痕;
- 若「已完整问题应原样透传」的负例被错误改写 → 强化 `RESOLVE_PROMPT` 的"原样返回"条款后重跑。

- [ ] **Step 4: 提交**

```powershell
git add potry-ai-agent/eval_ch05.py potry-ai-agent/prompts.py dev-notes/ch05.md
git commit -m "test(ch05): 意图/消解/扩写/多轮评估集与真实模型跑批结果"
```

> 若 Step 3 未改 `prompts.py`,提交时去掉该项(`git add potry-ai-agent/eval_ch05.py dev-notes/ch05.md`)。

---

## Task 13: 验收 4 条真跑 + 整体 code review + dev-notes 完结 + 交付

**Files:**
- Modify: `dev-notes/ch05.md`

- [ ] **Step 1: 启动服务(前置:MySQL 已拉起)**

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

保持该终端不关,另开 PowerShell 窗口做后续验收。启动日志应现 `[wf] 图已编译(checkpointer=sqlite:...)`。

- [ ] **Step 2: 验收①——多轮意图与指代(问诗人 → 判格律 → 查诗词)**

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/agent/workflow -H "Content-Type: application/json" -d '{\"sessionId\":\"acc1\",\"message\":\"《静夜思》是谁写的\"}'
curl.exe -N -X POST http://127.0.0.1:8000/agent/workflow -H "Content-Type: application/json" -d '{\"sessionId\":\"acc1\",\"message\":\"那它合律吗\"}'
curl.exe -N -X POST http://127.0.0.1:8000/agent/workflow -H "Content-Type: application/json" -d '{\"sessionId\":\"acc1\",\"message\":\"帮我再找一首写月亮的\"}'
```

Expected:服务日志三轮分别出现
`[wf] intent=find_poet ...` / `[wf] intent=poem_meter ... subflow kind=meter ...` / `[wf] intent=find_poem ...`;
且第二轮出现 `[wf] resolve changed=true query=...静夜思...`(指代补全)。

- [ ] **Step 3: 验收②——JSON 稳定 + `other` 兜底**

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/agent/workflow -H "Content-Type: application/json" -d '{\"sessionId\":\"acc2\",\"message\":\"帮我写个 Java 排序\"}'
```

Expected:`[wf] classify intent=other conf=...` 且 `[wf] intent=other route=other ... iters>=1`(交 Agent 做需求澄清)。

- [ ] **Step 4: 验收③——先消解、再子流程可观测**

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/agent/workflow -H "Content-Type: application/json" -d '{\"sessionId\":\"acc3\",\"message\":\"《静夜思》是谁写的\"}'
curl.exe -N -X POST http://127.0.0.1:8000/agent/workflow -H "Content-Type: application/json" -d '{\"sessionId\":\"acc3\",\"message\":\"这句合不合律\"}'
```

Expected:第二轮日志依次出现
①`[wf] resolve changed=... query=...`;
②`[wf] subflow kind=meter target=... policy=N`(N ≥ 1);
③`[wf] intent=poem_meter conf=... route=ruling ...`。
(若该轮恰好命中对象则直达判定;若未命中则出现 `pending_subflow` 卡片帧,按验收④继续。)

- [ ] **Step 5: 验收④——浏览器诗词卡片回填后判定走完(含两段式后端取证)**

**后端取证(确定性,浏览器不可靠时的替代):**

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/agent/workflow -H "Content-Type: application/json" -d '{\"sessionId\":\"acc4\",\"message\":\"这句合不合律\"}'
```

Expected(第一段):响应含 `event: action` 且 `data` 里有 `"action": "pick_poem"` 与候选数组;`done` 里 `"status": "awaiting_slot"`。

把候选里第一项的 `poemId` 填入下一条(示例 `11` 需换成实际值):

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/agent/workflow -H "Content-Type: application/json" -d '{\"sessionId\":\"acc4\",\"message\":\"\",\"selectedPoemId\":11}'
```

Expected(第二段):响应含 `event: token`(判定结果)+ `event: action`(`"action": "open_correction_form"`)+ `done.status="ok"`;服务日志出现 `[wf] resolve resume=续跑(...)` 与 `[wf] subflow kind=... policy=N`。

**浏览器人工确认:** 打开 `http://127.0.0.1:8000/chat`,重复上述两步 → 出现**诗词卡片**、点选后**自动回填并接着走完**、判定下方出现**纠错单表单**(类目下拉 5 项)。

- [ ] **Step 6: 纠错单落库取证**

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" -uroot -ppublication-placeholder-mysql_password -N -e "SELECT COUNT(*) FROM corrections;" poem
```

在聊天页提交一次纠错单后再查 → **+1**;`SELECT category, detail FROM corrections ORDER BY id DESC LIMIT 1;` 能看到类目与补充说明。

- [ ] **Step 7: 整体 code review(两阶段评审)**

按 Superpowers 两阶段评审对 Ch05 全部新代码做 **spec 合规评审 + 质量评审**;把结论(问题项与修复、是否 Yes)写入 `dev-notes/ch05.md` 阶段 5。
**重点自查项:**
- `PER_TURN_RESET` 是否漏了新字段(跨轮泄漏回归:`tests/test_workflow_graph.py::test_second_turn_does_not_leak_previous_turn_state` 必须绿);
- `pending_subflow` / `subflow_kind` 在续跑段的读写是否与"新轮清、续跑留"一致;
- `agent_react._seed_messages` 的判定分支是否只在 `subflow_kind` 非空时生效(不得影响知识类/业务类);
- `search_multi` 的去重键是 **chunk id**(不是 poemId)—— 候选卡片另按 poemId 去重;
- `main.py` 三类 action 帧与 `done.status` 是否与前端 `handleActionFrame` 一一对应。

- [ ] **Step 8: 追记 dev-notes 阶段 5/6 并按 spec §11 复核留痕**

`dev-notes/ch05.md` 补齐:
- **阶段 2(计划评审通过)**:计划路径、自审结论;
- **阶段 3(逐任务实现)**:各任务提交 hash、评审结论、返工记录(前面每任务已逐段追记,此处汇总核对);
- **阶段 4(评估集)**:四组评估集完整输出与准确率;
- **阶段 5(验收)**:四条验收的原始命令与观测输出(日志行、`corrections` 计数前后值);
- **阶段 6(交付)**:演示命令、测试总数、文档路径。

同时把两处**实现口径**(不新增 `query` 字段 / 纠错单入口总是挂)写入 `docs/superpowers/specs/2026-10-19-ai-tutor-ch05-router-formal-design.md` §11 决策留痕表(追加两行,不改原有行)。

- [ ] **Step 9: 最终全量回归 + 提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Expected:全绿,总数 = 199 + 本章新增用例数。

```powershell
git add dev-notes/ch05.md docs/superpowers/specs/2026-10-19-ai-tutor-ch05-router-formal-design.md
git commit -m "docs(ch05): 验收结果、评估集与两处实现口径留痕"
```

- [ ] **Step 10: 交付说明**

向用户汇报:
1. **功能演示命令**:`.\.venv\Scripts\python.exe -m uvicorn main:app --port 8000` → 打开 `http://127.0.0.1:8000/chat`;
2. **测试结果**:`pytest tests -q` 全绿(与基线 199 的对照);
3. **dev-notes 路径**:`dev-notes/ch05.md`;
4. **已知边界**:建库仍停在 ~50%(未嵌入的诗词检索不到,预期);意图识别**只记录 confidence、不据此分流**(阈值与两级升级留后续,spec §11 已留痕);policy 语料为**小体量规则文档**,判定依据的完备性以「宁可说不确定」为准则。

---

## Self-Review

**1. Spec coverage**

| spec 章节 / 需求 | 落到哪个 Task |
|---|---|
| §1.1 指代消解 + Query 改写(已完整则透传) | T4(prompt)、T6(resolve.py)、T9(resolve_node) |
| §1.2 Query 扩写(强制 JSON `{"queries":[…]}`、多查询去重合并、只在判定侧) | T4、T7、T9(expand_query_node) |
| §1.3 意图识别 LLM 路线 + 四件套 | T3(intent.py)、T4(INTENT_PROMPT)、T9(classify_node) |
| §1.4 分流精化:两条判定子流程(取对象 → 扩写 → 强制检索 policy → Agent 只判能不能/对不对) | T1/T2(policy 语料)、T8(ruling.py)、T9(三节点 + Agent 种子) |
| §1.5 槽位处理(缺对象不猜、下发卡片、原因类目不追问、澄清留 Agent) | T5(corrections)、T8(候选卡片)、T9(两段式)、T11(卡片/表单) |
| §1.6 前端配套(Vibe 例外) | T11 |
| §3.1 八类 + `other`、归并两个旧标签、工具全留 | T3 |
| §3.2 四件套 prompt + 解析失败落 `other` + 置信度只用不判 | T3、T4、T9 |
| §3.3 六出口 | T3、T9 |
| §4 图骨架(新三节点 + `after_resolve` + 两出口) | T9 |
| §5 两段式续跑(固定提示 + `pick_poem` 帧 + `awaiting_slot` + `selectedPoemId` 续跑) | T9、T10、T11 |
| §6 状态新增字段 + 全量进 `PER_TURN_RESET` | T3 |
| §7 模块划分 | T1、T3–T11 |
| §8 判定子流程 6 步 | T8、T9 |
| §9 落库 + 结构化日志(conf / resolve / subflow 三行) | T5(corrections)、T9(日志)、T10(端点) |
| §10 错误处理与降级(逐条) | T6、T7、T8、T9、T10 |
| §11 决策与偏差留痕(含两处实现口径) | T13 |
| §12 测试与验收策略(可单测 + 标注样例 + 端到端) | T1–T13;评估集 T12;验收 T13 |
| 需求"无新增组件,延用现有聊天上游" | 全章无新依赖(T1 只加语料与过滤) |
| 需求"本章不做微调小模型/跨会话记忆" | spec §11 已留痕;计划未引入 |

**2. Placeholder scan:** 无 TBD/TODO;每个改代码的步骤都给出完整可粘贴代码;每条命令给出期望输出。

**3. Type / 名称一致性核对**

- 状态字段名:`confidence` / `query_changed` / `subflow_kind` / `slot_target` / `candidates` / `pending_subflow` / `expanded_queries` / `policy_hits` / `correction_categories` / `selected_poem_id` / `history` 在 T3 定义,T6–T10 一致使用;`resolved_input` 沿用 Ch04 语义(见「两处实现口径」)。
- 上游签名:`parse_intent_response(text) -> (label, confidence)`(T3 定,T9 用);`resolve_input(llm, question, history) -> (query, changed)`(T6 定,T9 用);`expand_queries(llm, question) -> list[str]` 与 `search_multi(queries, source_type, topk) -> list[dict]`(T7 定,T8/T9 用);`ruling.resolve_slot(state, deps)` / `ruling.collect_policy(state, deps)` / `ruling.fetch_poem(poem_id)` / `ruling.after_slot_check(state)`(T8 定,T9 用)。
- 条件边返回名与 `add_node` 注册名一致:`classify` / `slot_check` / `expand_query` / `retrieve_policy` / `retrieve` / `agent` / `tool_node` / `log`(T9)。
- `knowledge.list_pending(limit, source_type)` 与 `count_by_status(source_type)`(T1 定,T2/T1 用)。
- `AppStorage.add_correction(category, detail, poem_id, session_id, userid)`(T5 定,T10 端点用;测试按同名关键字参数调用)。
- `_PER_TURN_RESET` 已更名 `PER_TURN_RESET` 并从 `workflow/nodes.py` 上移到 `workflow/state.py`(T3),`nodes.py` 只 import。
- `selectedPoemId`(HTTP JSON,前端/端点)↔ `selected_poem_id`(state 键):T10 明确映射。

**4. 已知的执行顺序依赖**

- 组三(评估集 T12)依赖 T4 的 prompt 定稿与 T6/T7 的解析函数 → 排在组二之后;
- 验收 T13 依赖 MySQL 已起(policy 检索与纠错单落库都走 MySQL)· 语料已入库(T2)。
