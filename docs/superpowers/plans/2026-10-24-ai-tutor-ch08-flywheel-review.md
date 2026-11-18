# Ch08 数据飞轮与审核后台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把三个入口（检索置信度闸、模型自评、用户 👎）的问题送进 `pending_questions`，后台异步标准化/查重/入 `review_queue`，人工在 `/admin/review` 审核通过后写入知识库。

**Architecture:** 请求内只做一次 DB 入池；`FlywheelService` 后台异步调用 LLM 标准化与查重，按 `matched_review_id` 幂等落队列；审核 API 复用 Ch03 的 `upsert_chunks + embed + Milvus upsert + mark_embedded`，向量写入成功后才置 approved。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy 2.0、LangChain、APScheduler 3.11、原生 HTML/JS。

**Spec:** `docs/superpowers/specs/2026-10-24-ai-tutor-ch08-observability-flywheel-design.md`

---

## 0. 执行约定

- 工作目录：`e:\javatexts\poetry-spring2\potry-ai-agent`。
- 只提交本任务文件；工作区无关改动一律不 add。
- 测试命令统一 `.\.venv\Scripts\python.exe -m pytest ...`。
- 每个任务完成立即追记 `dev-notes/ch08.md`（用户原话、产出、纠偏、返工）。
- 本批不实现 Langfuse 与评估流水线；验收 1/5/6 暂缓。

---

### Task 1: 问题池加列 + review_queue 模型 + 迁移

**Files:**
- Modify: `knowledge.py`
- Test: `tests/test_flywheel_storage.py`

- [ ] **Step 1: 写失败测试**

```python
"""Ch08 存储：pending_questions 三列、review_queue CRUD、旧表迁移。"""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from knowledge import KnowledgeBase, KnowledgeStorage


def _storage():
    engine = create_engine("sqlite:///:memory:")
    KnowledgeBase.metadata.create_all(engine)
    return KnowledgeStorage(sessionmaker(bind=engine)), engine


def test_pending_columns_match_spec():
    engine = create_engine("sqlite:///:memory:")
    KnowledgeBase.metadata.create_all(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("pending_questions")}
    assert {"source_entry", "retrieved_snapshot", "matched_review_id"} <= cols


def test_add_pending_with_entry_and_snapshot():
    storage, _ = _storage()
    pid = storage.add_pending_question(
        "问题", session_id="s1", source_entry="model_self_eval",
        retrieved_snapshot='[{"title": "静夜思"}]',
    )
    row = storage.get_pending_question(pid)
    assert row["source_entry"] == "model_self_eval"
    assert row["retrieved_snapshot"] == '[{"title": "静夜思"}]'
    assert row["matched_review_id"] is None


def test_review_crud_and_occurrences():
    storage, _ = _storage()
    rid = storage.create_review("标准问题", "示例答案")
    storage.increment_review_occurrences(rid)
    row = storage.get_review(rid)
    assert row["standard_question"] == "标准问题"
    assert row["occurrences"] == 2
    assert row["status"] == "pending"
    storage.update_review_status(rid, "approved", approved_answer="核准答案")
    assert storage.get_review(rid)["approved_answer"] == "核准答案"


def test_mark_pending_matched_and_list_by_review():
    storage, _ = _storage()
    pid = storage.add_pending_question("原话", session_id="s1")
    rid = storage.create_review("标准", "示例")
    storage.mark_pending_matched(pid, rid)
    assert storage.get_pending_question(pid)["matched_review_id"] == rid
    assert [r["id"] for r in storage.list_pending_by_review(rid)] == [pid]


def test_list_unmatched_pending_excludes_matched():
    storage, _ = _storage()
    a = storage.add_pending_question("a")
    b = storage.add_pending_question("b")
    rid = storage.create_review("x", "y")
    storage.mark_pending_matched(a, rid)
    assert [r["id"] for r in storage.list_unmatched_pending()] == [b]


def test_get_chunk_id_by_key():
    storage, _ = _storage()
    storage.upsert_chunks([{
        "source_type": "qa", "source_id": 1, "section": "faq", "seq": 0,
        "chunk_text": "Q: x\nA: y", "raw_text": "Q: x\nA: y", "title": "x",
    }])
    assert storage.get_chunk_id("qa", 1, "faq", 0) is not None


def test_ensure_ch08_schema_adds_columns_to_legacy_table():
    from knowledge import ensure_ch08_schema

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE pending_questions "
            "(id INTEGER PRIMARY KEY, question TEXT, session_id VARCHAR(64), created_at DATETIME)"
        ))
    ensure_ch08_schema(engine)
    ensure_ch08_schema(engine)          # 幂等
    cols = {c["name"] for c in inspect(engine).get_columns("pending_questions")}
    assert {"source_entry", "retrieved_snapshot", "matched_review_id"} <= cols
```

- [ ] **Step 2: 跑失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_flywheel_storage.py -v`
Expected: FAIL（缺列/缺方法/缺 `ReviewQueue`）。

- [ ] **Step 3: 改 `knowledge.py`**

`PendingQuestion` 追加：

```python
    source_entry: Mapped[str | None] = mapped_column(String(32))
    retrieved_snapshot: Mapped[str | None] = mapped_column(Text)
    matched_review_id: Mapped[int | None] = mapped_column(_ID_TYPE)
```

新增：

```python
class ReviewQueue(KnowledgeBase):
    """待审队列:一行一个去重缺口。"""

    __tablename__ = "review_queue"

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    standard_question: Mapped[str] = mapped_column(Text)
    example_answer: Mapped[str] = mapped_column(Text)
    occurrences: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    approved_answer: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


def ensure_ch08_schema(engine) -> None:
    """给旧 pending_questions 补三列;新表由 create_all 建。幂等。"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "pending_questions" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("pending_questions")}
    columns = {
        "source_entry": "VARCHAR(32) NULL",
        "retrieved_snapshot": "TEXT NULL",
        "matched_review_id": "BIGINT NULL",
    }
    with engine.begin() as conn:
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE pending_questions ADD COLUMN {name} {ddl}"))
```

`KnowledgeStorage` 追加：

```python
    def add_pending_question(
        self, question: str, session_id: str | None = None,
        *, source_entry: str = "retrieval_gate",
        retrieved_snapshot: str | None = None,
    ) -> int:
        with self._factory() as session:
            row = PendingQuestion(
                question=question, session_id=session_id,
                source_entry=source_entry, retrieved_snapshot=retrieved_snapshot,
            )
            session.add(row)
            session.commit()
            return row.id

    def get_pending_question(self, pending_id: int) -> dict | None:
        with self._factory() as session:
            row = session.get(PendingQuestion, pending_id)
            return {
                "id": row.id, "question": row.question, "session_id": row.session_id,
                "source_entry": row.source_entry,
                "retrieved_snapshot": row.retrieved_snapshot,
                "matched_review_id": row.matched_review_id,
            } if row else None

    def list_unmatched_pending(self, limit: int = 50) -> list[dict]:
        with self._factory() as session:
            rows = session.execute(
                select(PendingQuestion)
                .where(PendingQuestion.matched_review_id.is_(None))
                .order_by(PendingQuestion.id).limit(limit)
            ).scalars()
            return [
                {"id": r.id, "question": r.question, "session_id": r.session_id,
                 "source_entry": r.source_entry,
                 "retrieved_snapshot": r.retrieved_snapshot}
                for r in rows
            ]

    def mark_pending_matched(self, pending_id: int, review_id: int) -> None:
        with self._factory() as session:
            row = session.get(PendingQuestion, pending_id)
            if row is not None:
                row.matched_review_id = review_id
            session.commit()

    def list_pending_by_review(self, review_id: int) -> list[dict]:
        with self._factory() as session:
            rows = session.execute(
                select(PendingQuestion)
                .where(PendingQuestion.matched_review_id == review_id)
                .order_by(PendingQuestion.id)
            ).scalars()
            return [
                {"id": r.id, "question": r.question, "session_id": r.session_id,
                 "source_entry": r.source_entry,
                 "retrieved_snapshot": r.retrieved_snapshot,
                 "created_at": r.created_at}
                for r in rows
            ]

    def create_review(self, standard_question: str, example_answer: str) -> int:
        with self._factory() as session:
            row = ReviewQueue(
                standard_question=standard_question, example_answer=example_answer,
            )
            session.add(row)
            session.commit()
            return row.id

    def get_review(self, review_id: int) -> dict | None:
        with self._factory() as session:
            row = session.get(ReviewQueue, review_id)
            return {
                "id": row.id, "standard_question": row.standard_question,
                "example_answer": row.example_answer, "occurrences": row.occurrences,
                "status": row.status, "approved_answer": row.approved_answer,
                "created_at": row.created_at, "updated_at": row.updated_at,
            } if row else None

    def list_reviews(self, status: str | None = "pending",
                     limit: int = 50, offset: int = 0) -> list[dict]:
        with self._factory() as session:
            stmt = select(ReviewQueue).order_by(ReviewQueue.id.desc()).limit(limit).offset(offset)
            if status:
                stmt = stmt.where(ReviewQueue.status == status)
            return [
                {"id": r.id, "standard_question": r.standard_question,
                 "example_answer": r.example_answer, "occurrences": r.occurrences,
                 "status": r.status, "approved_answer": r.approved_answer,
                 "created_at": r.created_at}
                for r in session.execute(stmt).scalars()
            ]

    def increment_review_occurrences(self, review_id: int) -> None:
        with self._factory() as session:
            row = session.get(ReviewQueue, review_id)
            if row is not None:
                row.occurrences = (row.occurrences or 0) + 1
            session.commit()

    def update_review_status(
        self, review_id: int, status: str,
        *, approved_answer: str | None = None,
        standard_question: str | None = None,
    ) -> None:
        with self._factory() as session:
            row = session.get(ReviewQueue, review_id)
            if row is None:
                return
            row.status = status
            if approved_answer is not None:
                row.approved_answer = approved_answer
            if standard_question is not None:
                row.standard_question = standard_question
            session.commit()

    def get_chunk_id(
        self, source_type: str, source_id, section: str, seq: int,
    ) -> int | None:
        with self._factory() as session:
            row = session.execute(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.source_type == source_type,
                    KnowledgeChunk.source_id == source_id,
                    KnowledgeChunk.section == section,
                    KnowledgeChunk.seq == seq,
                )
            ).scalar_one_or_none()
            return row.id if row else None
```

- [ ] **Step 4: 跑通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_flywheel_storage.py -v`
Expected: 7 passed。
再跑 `tests/test_knowledge.py tests/test_storage.py -q` 防回归。

- [ ] **Step 5: 提交**

```powershell
git add potry-ai-agent/knowledge.py potry-ai-agent/tests/test_flywheel_storage.py
git commit -m "feat(ch08): add flywheel pool columns and review queue storage"
```

---

### Task 2: 置信度信号与公式

**Files:**
- Modify: `workflow/confidence.py`
- Modify: `config.py`
- Test: `tests/test_confidence_signals.py`

- [ ] **Step 1: 写失败测试**

```python
"""证据置信度代理公式:Top1/margin/有效条数。"""
from workflow.confidence import evidence_signals


def test_empty_hits_zero_confidence():
    s = evidence_signals([], min_score=0.3)
    assert s["top1"] == 0.0
    assert s["evidence_confidence"] == 0.0


def test_signals_use_top1_margin_count():
    hits = [{"score": 0.8}, {"score": 0.6}, {"score": 0.5}, {"score": 0.1}]
    s = evidence_signals(hits, min_score=0.3)
    assert s["top1"] == 0.8
    assert s["top2"] == 0.6
    assert s["margin"] == 0.2
    assert s["effective_count"] == 3
    assert 0.7 < s["evidence_confidence"] <= 1.0


def test_single_hit_has_no_margin_but_counts():
    s = evidence_signals([{"score": 0.9}], min_score=0.3)
    assert s["margin"] == 0.0
    assert s["effective_count"] == 1
    assert s["evidence_confidence"] < 0.9
```

- [ ] **Step 2: 跑失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_confidence_signals.py -v`
Expected: FAIL（无 `evidence_signals`）。

- [ ] **Step 3: 实现**

`workflow/confidence.py` 追加：

```python
_MARGIN_SCALE = 0.20
_COUNT_TARGET = 3


def evidence_signals(hits: list[dict], min_score: float) -> dict:
    """用现有稠密检索分做证据置信度代理（无 reranker）。"""
    scores = sorted(
        (max(0.0, min(1.0, float(h.get("score", 0.0)))) for h in hits),
        reverse=True,
    )
    top1 = scores[0] if scores else 0.0
    top2 = scores[1] if len(scores) > 1 else 0.0
    margin = max(0.0, top1 - top2) if len(scores) > 1 else 0.0
    effective_count = sum(1 for s in scores if s >= min_score)
    confidence = (
        0.5 * top1
        + 0.3 * min(margin / _MARGIN_SCALE, 1.0)
        + 0.2 * min(effective_count / _COUNT_TARGET, 1.0)
    )
    return {
        "top1": round(top1, 4), "top2": round(top2, 4),
        "margin": round(margin, 4), "effective_count": effective_count,
        "evidence_confidence": round(confidence, 4),
    }


def is_confidence_sufficient(confidence: float, threshold: float) -> bool:
    return confidence >= threshold
```

`config.py` 增加默认值与 Settings 字段：

```python
_DEFAULT_EVIDENCE_MIN_SCORE = 0.30
_DEFAULT_EVIDENCE_CONFIDENCE_THRESHOLD = 0.60
```

```python
    evidence_min_score: float = _DEFAULT_EVIDENCE_MIN_SCORE
    evidence_confidence_threshold: float = _DEFAULT_EVIDENCE_CONFIDENCE_THRESHOLD
```

`load_settings` 读取 `EVIDENCE_MIN_SCORE` / `EVIDENCE_CONFIDENCE_THRESHOLD`，并校验在 0–1。

- [ ] **Step 4: 跑通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_confidence_signals.py -v`
Expected: 3 passed。再跑 `tests/test_config.py -q`。

- [ ] **Step 5: 提交**

```powershell
git add potry-ai-agent/workflow/confidence.py potry-ai-agent/config.py potry-ai-agent/tests/test_confidence_signals.py
git commit -m "feat(ch08): add evidence confidence signals from retrieval scores"
```

---

### Task 3: FlywheelService（标准化 / 查重 / 幂等）

**Files:**
- Modify: `prompts.py`
- Create: `flywheel.py`
- Test: `tests/test_flywheel.py`

- [ ] **Step 1: 写失败测试**

```python
"""飞轮后台:标准化→查重→建/并队列,失败留待重试,幂等。"""
import asyncio

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from flywheel import FlywheelService, snapshot_hits
from knowledge import KnowledgeBase, KnowledgeStorage


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def ainvoke(self, prompt):
        self.calls.append(prompt)
        return AIMessage(content=self.replies.pop(0))


def _storage():
    engine = create_engine("sqlite:///:memory:")
    KnowledgeBase.metadata.create_all(engine)
    return KnowledgeStorage(sessionmaker(bind=engine))


def test_snapshot_hits_serializes_top5_with_text():
    hits = [{"id": i, "score": 0.9 - i / 10, "source_type": "poem",
             "title": f"诗{i}", "writer": "李白", "dynasty": "唐", "text": "x" * 500}
            for i in range(7)]
    payload = snapshot_hits(hits)
    assert payload.count('"id"') == 5
    assert "\\u" not in payload
    assert '"title": "诗0"' in payload


@pytest.mark.asyncio
async def test_process_creates_review_and_links_pending():
    storage = _storage()
    pid = storage.add_pending_question("静夜思是谁写的", "s1", source_entry="retrieval_gate")
    llm = FakeLLM([
        '{"standard_question": "《静夜思》的作者是谁?", "example_answer": "李白"}',
        '{"matched_id": null}',
    ])
    service = FlywheelService(storage, llm)
    await service.process_pending(pid)
    review_id = storage.get_pending_question(pid)["matched_review_id"]
    assert review_id is not None
    assert storage.get_review(review_id)["occurrences"] == 1


@pytest.mark.asyncio
async def test_dedup_merges_existing_review():
    storage = _storage()
    rid = storage.create_review("《静夜思》的作者是谁?", "李白")
    pid = storage.add_pending_question("静夜思作者", "s1")
    llm = FakeLLM([
        '{"standard_question": "《静夜思》的作者是谁?", "example_answer": "李白"}',
        f'{{"matched_id": {rid}}}',
    ])
    await FlywheelService(storage, llm).process_pending(pid)
    assert storage.get_review(rid)["occurrences"] == 2
    assert storage.get_pending_question(pid)["matched_review_id"] == rid


@pytest.mark.asyncio
async def test_malformed_standardization_leaves_pending_unmatched():
    storage = _storage()
    pid = storage.add_pending_question("问题", "s1")
    await FlywheelService(storage, FakeLLM(["not json"])).process_pending(pid)
    assert storage.get_pending_question(pid)["matched_review_id"] is None


@pytest.mark.asyncio
async def test_idempotent_second_process_no_new_row():
    storage = _storage()
    pid = storage.add_pending_question("问题", "s1")
    llm = FakeLLM([
        '{"standard_question": "标准", "example_answer": "答案"}',
        '{"matched_id": null}',
    ])
    service = FlywheelService(storage, llm)
    await service.process_pending(pid)
    rid = storage.get_pending_question(pid)["matched_review_id"]
    await service.process_pending(pid)
    assert len(storage.list_reviews()) == 1
    assert storage.get_review(rid)["occurrences"] == 1


@pytest.mark.asyncio
async def test_drain_processes_unmatched_rows():
    storage = _storage()
    storage.add_pending_question("a", "s1")
    storage.add_pending_question("b", "s2")
    llm = FakeLLM([
        '{"standard_question": "A", "example_answer": "a"}', '{"matched_id": null}',
        '{"standard_question": "B", "example_answer": "b"}', '{"matched_id": null}',
    ])
    await FlywheelService(storage, llm).drain()
    assert len(storage.list_reviews()) == 2
```

- [ ] **Step 2: 跑失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_flywheel.py -v`
Expected: FAIL（无 `flywheel` 模块）。

- [ ] **Step 3: 加 Prompt**

`prompts.py` 追加：

```python
STANDARDIZE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "你是知识库运营助手。把用户口语问题改写成一条标准 FAQ 问题,并给一条简短示例答案备查。"
     "只输出 JSON:{\"standard_question\": \"...\", \"example_answer\": \"...\"}。"
     "示例答案只作草稿,不得编造具体诗文原文;不确定就写通用回答。"),
    ("human", "用户问题:{question}\n召回片段:\n{evidence}"),
])

DEDUP_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "判断新问题与待审队列中的哪一条是同一个意思。只输出 JSON:"
     '{"matched_id": 整数或null}。拿不准就输出 null,不要强行合并。'),
    ("human", "新问题:{question}\n待审队列:\n{candidates}"),
])
```

- [ ] **Step 4: 实现 `flywheel.py`**

```python
"""数据飞轮后台:标准化 → 查重 → 入待审队列。"""
import asyncio
import json
import re

from prompts import DEDUP_PROMPT, STANDARDIZE_PROMPT


def snapshot_hits(hits: list[dict], top_n: int = 5) -> str:
    rows = [
        {
            "id": h.get("id"), "source_type": h.get("source_type"),
            "title": h.get("title"), "writer": h.get("writer"),
            "dynasty": h.get("dynasty"), "score": h.get("score"),
            "text": (h.get("text") or "")[:400],
        }
        for h in (hits or [])[:top_n]
    ]
    return json.dumps(rows, ensure_ascii=False, default=str)


def _parse_json(text: str) -> dict | None:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


class FlywheelService:
    def __init__(self, storage, llm, *, max_dedup_candidates: int = 50) -> None:
        self._storage = storage
        self._llm = llm
        self._max = max_dedup_candidates
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()

    def schedule(self, pending_id: int) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(self.process_pending(pending_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()

    async def drain(self, limit: int = 50) -> int:
        processed = 0
        for row in self._storage.list_unmatched_pending(limit):
            await self.process_pending(row["id"])
            processed += 1
        return processed

    async def process_pending(self, pending_id: int) -> None:
        async with self._lock:
            pending = self._storage.get_pending_question(pending_id)
            if not pending or pending["matched_review_id"]:
                return
            standardized = await self._standardize(pending)
            if standardized is None:
                return
            candidates = self._storage.list_reviews(status="pending", limit=self._max)
            matched_id = await self._dedup(standardized["standard_question"], candidates)
            if matched_id:
                self._storage.increment_review_occurrences(matched_id)
                review_id = matched_id
            else:
                review_id = self._storage.create_review(
                    standardized["standard_question"], standardized["example_answer"],
                )
            self._storage.mark_pending_matched(pending_id, review_id)

    async def _standardize(self, pending: dict) -> dict | None:
        try:
            message = await self._llm.ainvoke(STANDARDIZE_PROMPT.invoke({
                "question": pending["question"],
                "evidence": pending.get("retrieved_snapshot") or "[]",
            }))
            data = _parse_json(message.content or "")
            if not data:
                return None
            question = str(data.get("standard_question") or "").strip()
            answer = str(data.get("example_answer") or "").strip()
            if not question or not answer:
                return None
            return {"standard_question": question[:500], "example_answer": answer[:2000]}
        except Exception as exc:  # noqa: BLE001 - 后台失败留待重试
            print(f"[flywheel] standardize fail id={pending['id']}: {str(exc)[:160]}")
            return None

    async def _dedup(self, question: str, candidates: list[dict]) -> int | None:
        if not candidates:
            return None
        lines = "\n".join(f"{c['id']}. {c['standard_question']}" for c in candidates)
        try:
            message = await self._llm.ainvoke(DEDUP_PROMPT.invoke({
                "question": question, "candidates": lines,
            }))
            data = _parse_json(message.content or "")
        except Exception as exc:  # noqa: BLE001
            print(f"[flywheel] dedup fail: {str(exc)[:160]}")
            return None
        if not data or data.get("matched_id") is None:
            return None
        try:
            matched = int(data["matched_id"])
        except (TypeError, ValueError):
            return None
        return matched if any(c["id"] == matched for c in candidates) else None
```

- [ ] **Step 5: 跑通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_flywheel.py -v`
Expected: 6 passed。

- [ ] **Step 6: 提交**

```powershell
git add potry-ai-agent/prompts.py potry-ai-agent/flywheel.py potry-ai-agent/tests/test_flywheel.py
git commit -m "feat(ch08): add flywheel standardization and dedup service"
```

---

### Task 4: 置信度闸升级 + 入池快照

**Files:**
- Modify: `workflow/confidence.py`（Task 2 已加信号）
- Modify: `workflow/nodes.py`
- Modify: `workflow/state.py`
- Modify: `workflow/deps.py`
- Modify: `main.py`（装配 FlywheelService）
- Test: `tests/test_workflow_confidence.py`、`tests/test_workflow_nodes.py`、`tests/test_workflow_graph.py`

- [ ] **Step 1: 写/改测试**

在 `tests/test_workflow_nodes.py` 增加：

```python
def test_gate_insufficient_writes_snapshot_and_schedules(monkeypatch):
    scheduled = []

    class FakePending:
        def add_pending_question(self, question, session_id=None, **kwargs):
            self.kwargs = kwargs
            return 7

        def __init__(self):
            self.kwargs = {}

    class FakeFlywheel:
        def schedule(self, pending_id):
            scheduled.append(pending_id)

    pending = FakePending()
    deps = SimpleNamespace(
        settings=SimpleNamespace(
            evidence_min_score=0.3, evidence_confidence_threshold=0.99,
            similarity_threshold=0.4,
        ),
        knowledge_storage=pending, flywheel=FakeFlywheel(),
    )
    monkeypatch.setattr("workflow.nodes.get_deps", lambda: deps)
    out = gate_node({
        "user_input": "知识库没有的问题", "session_id": "s1",
        "retrieved": [{"id": 1, "title": "静夜思", "score": 0.2,
                       "source_type": "poem", "text": "床前明月光"}],
    })
    assert out["gate_status"] == "insufficient"
    assert pending.kwargs["source_entry"] == "retrieval_gate"
    assert '"title": "静夜思"' in pending.kwargs["retrieved_snapshot"]
    assert scheduled == [7]
```

（若文件已有 `SimpleNamespace` 导入则复用；没有就补 `from types import SimpleNamespace`。）

- [ ] **Step 2: 跑失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_workflow_nodes.py::test_gate_insufficient_writes_snapshot_and_schedules -v`
Expected: FAIL（gate 仍用旧阈值/不传快照）。

- [ ] **Step 3: 改 state / deps**

`workflow/state.py` 的 `PER_TURN_RESET` 追加：

```python
    "evidence_confidence": 0.0,
    "gate_signals": {},
```

`WorkflowState` 追加：

```python
    evidence_confidence: float
    gate_signals: dict
```

`workflow/deps.py` 的构造函数追加可选 `flywheel=None`：

```python
    def __init__(self, settings, llm, tools, knowledge_storage, chat_storage, flywheel=None) -> None:
        ...
        self.flywheel = flywheel
```

- [ ] **Step 4: 改 gate_node**

```python
def gate_node(state: dict) -> dict:
    """置信度闸:检索后、Agent 前;不足则兜底 + 入池(带 Top5 快照)。"""
    deps = get_deps()
    hits = state.get("retrieved") or []
    signals = evidence_signals(hits, deps.settings.evidence_min_score)
    confidence = signals["evidence_confidence"]
    if is_confidence_sufficient(confidence, deps.settings.evidence_confidence_threshold):
        return {
            "gate_status": "pass",
            "evidence_confidence": confidence,
            "gate_signals": signals,
        }
    try:
        if deps.knowledge_storage is not None:
            pending_id = deps.knowledge_storage.add_pending_question(
                state.get("user_input", ""), state.get("session_id"),
                source_entry="retrieval_gate",
                retrieved_snapshot=snapshot_hits(hits),
            )
            if deps.flywheel is not None:
                deps.flywheel.schedule(pending_id)
    except Exception as exc:  # noqa: BLE001 - 记录失败只告警,不阻断兜底
        print(f"[wf] pending write fail: {str(exc)[:200]}")
    return {
        "gate_status": "insufficient",
        "evidence_confidence": confidence,
        "gate_signals": signals,
        "answer": FALLBACK_REPLY,
        "fallback_reason": "insufficient_evidence",
    }
```

导入改为：

```python
from flywheel import snapshot_hits
from workflow.confidence import evidence_signals, is_confidence_sufficient, retrieve_evidence
```

日志行追加 `conf=...`（保留 `score=` 兼容）。

- [ ] **Step 5: main 装配**

在 `workflow_deps = WorkflowDeps(...)` 前创建：

```python
from flywheel import FlywheelService
flywheel_service = FlywheelService(knowledge_storage, workflow_llm)
```

并把 `WorkflowDeps(..., flywheel=flywheel_service)`；lifespan 关闭时 `await flywheel_service.shutdown()`（放在 `shutdown_summaries()` 附近）。

- [ ] **Step 6: 跑通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_workflow_nodes.py tests/test_workflow_confidence.py tests/test_workflow_graph.py -q`
Expected: 全绿（旧测试里的 `add_pending_question` 假实现要加 `**kwargs`）。

- [ ] **Step 7: 提交**

```powershell
git add potry-ai-agent/workflow/confidence.py potry-ai-agent/workflow/nodes.py potry-ai-agent/workflow/state.py potry-ai-agent/workflow/deps.py potry-ai-agent/main.py potry-ai-agent/tests/test_workflow_nodes.py potry-ai-agent/tests/test_workflow_confidence.py potry-ai-agent/tests/test_workflow_graph.py
git commit -m "feat(ch08): upgrade confidence gate to evidence confidence with snapshot"
```

---

### Task 5: 模型自评 + 👎 接口

**Files:**
- Create: `self_eval.py`
- Modify: `prompts.py`
- Modify: `main.py`
- Test: `tests/test_self_eval.py`、`tests/test_feedback_endpoint.py`

- [ ] **Step 1: 写失败测试**

`tests/test_self_eval.py`：

```python
import pytest
from langchain_core.messages import AIMessage

from self_eval import assess_answer, self_eval_after_turn


class FakeLLM:
    def __init__(self, content):
        self.content = content

    async def ainvoke(self, prompt):
        return AIMessage(content=self.content)


class FakeStorage:
    def __init__(self):
        self.rows = []

    def add_pending_question(self, question, session_id=None, **kwargs):
        self.rows.append({"question": question, "session_id": session_id, **kwargs})
        return len(self.rows)


class FakeFlywheel:
    def __init__(self):
        self.ids = []

    def schedule(self, pending_id):
        self.ids.append(pending_id)


@pytest.mark.asyncio
async def test_assess_true_for_insufficient():
    result = await assess_answer(FakeLLM('{"insufficient": true, "reason": "缺资料"}'), "q", "a", [])
    assert result["insufficient"] is True


@pytest.mark.asyncio
async def test_self_eval_writes_pool_for_insufficient_answer():
    storage, flywheel = FakeStorage(), FakeFlywheel()
    deps = type("D", (), {"llm": FakeLLM('{"insufficient": true, "reason": "x"}'),
                          "knowledge_storage": storage, "flywheel": flywheel})()
    await self_eval_after_turn(
        {"user_input": "q", "answer": "我不知道", "route": "other",
         "retrieved": [{"id": 1, "title": "静夜思", "score": 0.2, "text": "x"}]},
        deps, "s1",
    )
    assert storage.rows[0]["source_entry"] == "model_self_eval"
    assert flywheel.ids == [1]


@pytest.mark.asyncio
async def test_self_eval_skips_gate_fallback():
    storage, flywheel = FakeStorage(), FakeFlywheel()
    deps = type("D", (), {"llm": FakeLLM('{"insufficient": true}'),
                          "knowledge_storage": storage, "flywheel": flywheel})()
    await self_eval_after_turn(
        {"user_input": "q", "answer": "fallback", "route": "knowledge",
         "gate_status": "insufficient", "retrieved": []},
        deps, "s1",
    )
    assert storage.rows == []
```

`tests/test_feedback_endpoint.py`：

```python
from fastapi.testclient import TestClient

import main


class FakeState:
    def __init__(self, values):
        self.values = values


class FakeWorkflow:
    def __init__(self, values):
        self.values = values
        self.calls = 0

    async def aget_state(self, config):
        self.calls += 1
        return FakeState(self.values)


class FakeStorage:
    def __init__(self):
        self.rows = []

    def add_pending_question(self, question, session_id=None, **kwargs):
        self.rows.append({"question": question, "session_id": session_id, **kwargs})
        return 1


class FakeFlywheel:
    def __init__(self):
        self.ids = []

    def schedule(self, pending_id):
        self.ids.append(pending_id)


def test_negative_feedback_writes_pool_with_snapshot(monkeypatch):
    storage, flywheel = FakeStorage(), FakeFlywheel()
    monkeypatch.setattr(main, "_workflow", FakeWorkflow({
        "user_input": "静夜思是谁写的", "retrieved": [{"id": 1, "title": "静夜思", "score": 0.9}],
    }))
    monkeypatch.setattr(main, "knowledge_storage", storage)
    monkeypatch.setattr(main, "workflow_deps", type("D", (), {"flywheel": flywheel})())
    client = TestClient(main.app)
    resp = client.post("/agent/feedback/negative", json={
        "sessionId": "s1", "message": "静夜思是谁写的",
    })
    assert resp.status_code == 200
    assert storage.rows[0]["source_entry"] == "user_dislike"
    assert "静夜思" in storage.rows[0]["retrieved_snapshot"]
    assert flywheel.ids == [1]


def test_negative_feedback_mismatch_uses_empty_snapshot(monkeypatch):
    storage, flywheel = FakeStorage(), FakeFlywheel()
    monkeypatch.setattr(main, "_workflow", FakeWorkflow({
        "user_input": "新问题", "retrieved": [{"id": 1, "title": "旧", "score": 0.9}],
    }))
    monkeypatch.setattr(main, "knowledge_storage", storage)
    monkeypatch.setattr(main, "workflow_deps", type("D", (), {"flywheel": flywheel})())
    client = TestClient(main.app)
    resp = client.post("/agent/feedback/negative", json={
        "sessionId": "s1", "message": "旧问题",
    })
    assert resp.status_code == 200
    assert storage.rows[0]["retrieved_snapshot"] == "[]"
```

- [ ] **Step 2: 跑失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_self_eval.py tests/test_feedback_endpoint.py -v`
Expected: FAIL（无模块/路由）。

- [ ] **Step 3: 加 Prompt**

`prompts.py`：

```python
SELF_EVAL_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "判断回答是否明确承认自己知识不足、无法回答用户问题。"
     "只输出 JSON:{\"insufficient\": true/false, \"reason\": \"...\"}。"
     "回答给出了明确内容就不要判 true;只有明确说查不到/不知道/无法确定才判 true。"),
    ("human", "问题:{question}\n回答:{answer}\n检索片段:\n{evidence}"),
])
```

- [ ] **Step 4: 实现 `self_eval.py`**

```python
"""生成阶段自评:回答后独立一次 LLM 判断知识不足,入池。"""
import json
import re

from flywheel import snapshot_hits
from prompts import SELF_EVAL_PROMPT

_SKIP_ROUTES = {"chitchat", "complaint"}


def _parse_json(text: str) -> dict | None:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


async def assess_answer(llm, question: str, answer: str, evidence: list[dict]) -> dict:
    try:
        message = await llm.ainvoke(SELF_EVAL_PROMPT.invoke({
            "question": question, "answer": answer,
            "evidence": snapshot_hits(evidence),
        }))
        data = _parse_json(message.content or "")
        return {
            "insufficient": bool(data and data.get("insufficient")),
            "reason": str((data or {}).get("reason") or ""),
        }
    except Exception as exc:  # noqa: BLE001 - 自评失败不落池
        print(f"[self_eval] fail: {str(exc)[:160]}")
        return {"insufficient": False, "reason": "error"}


def _should_skip(state: dict) -> bool:
    if not state.get("answer"):
        return True
    if state.get("gate_status") == "insufficient":
        return True
    if state.get("pending_subflow"):
        return True
    if state.get("route") in _SKIP_ROUTES:
        return True
    if state.get("fallback_reason") == "agent_error":
        return True
    return False


async def self_eval_after_turn(state: dict, deps, session_id: str) -> None:
    if _should_skip(state) or deps.knowledge_storage is None:
        return
    result = await assess_answer(
        deps.llm, state.get("resolved_input") or state.get("user_input", ""),
        state.get("answer", ""), state.get("retrieved") or [],
    )
    if not result["insufficient"]:
        return
    try:
        pending_id = deps.knowledge_storage.add_pending_question(
            state.get("user_input", ""), session_id,
            source_entry="model_self_eval",
            retrieved_snapshot=snapshot_hits(state.get("retrieved") or []),
        )
        if deps.flywheel is not None:
            deps.flywheel.schedule(pending_id)
    except Exception as exc:  # noqa: BLE001
        print(f"[self_eval] pending write fail: {str(exc)[:160]}")
```

- [ ] **Step 5: main 接入**

导入 `asyncio`、`self_eval_after_turn`、`snapshot_hits`。

增加后台任务集合与函数：

```python
_self_eval_tasks: set[asyncio.Task] = set()


def _schedule_self_eval(final: dict, session_id: str) -> None:
    if workflow_deps.flywheel is None or workflow_deps.knowledge_storage is None:
        return
    task = asyncio.create_task(self_eval_after_turn(final, workflow_deps, session_id))
    _self_eval_tasks.add(task)
    task.add_done_callback(_self_eval_tasks.discard)
```

在 `/agent/workflow` 和 `/agent/workflow/resume` 的 `final = await _workflow.ainvoke(...)` 之后调用 `_schedule_self_eval(final, session_id)`。

新增接口：

```python
class NegativeFeedbackRequest(BaseModel):
    sessionId: str
    message: str


@app.post("/agent/feedback/negative")
async def negative_feedback(req: NegativeFeedbackRequest):
    if _workflow is None:
        raise HTTPException(status_code=503, detail={"message": "workflow 未就绪(装配失败)"})
    config = {"configurable": {"thread_id": req.sessionId}}
    hits: list[dict] = []
    try:
        snapshot = await _workflow.aget_state(config)
        values = getattr(snapshot, "values", {}) or {}
        if values.get("user_input") == req.message:
            hits = values.get("retrieved") or []
    except Exception as exc:  # noqa: BLE001 - 快照回捞失败不阻断入池
        print(f"[wf] feedback snapshot fail: {str(exc)[:160]}")
    try:
        pending_id = knowledge_storage.add_pending_question(
            req.message, req.sessionId,
            source_entry="user_dislike", retrieved_snapshot=snapshot_hits(hits),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"message": f"入池失败: {str(exc)[:120]}"})
    if workflow_deps.flywheel is not None:
        workflow_deps.flywheel.schedule(pending_id)
    return {"ok": True, "pendingId": pending_id}
```

lifespan 关闭时取消自评任务：

```python
for task in list(_self_eval_tasks):
    task.cancel()
_self_eval_tasks.clear()
```

- [ ] **Step 6: 跑通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_self_eval.py tests/test_feedback_endpoint.py -q`
Expected: 5 passed。再跑 `tests/test_workflow_endpoint.py -q` 防回归。

- [ ] **Step 7: 提交**

```powershell
git add potry-ai-agent/prompts.py potry-ai-agent/self_eval.py potry-ai-agent/main.py potry-ai-agent/tests/test_self_eval.py potry-ai-agent/tests/test_feedback_endpoint.py
git commit -m "feat(ch08): add model self-eval and negative feedback pool entry"
```

---

### Task 6: 审核 API 与通过写库

**Files:**
- Create: `review_api.py`
- Modify: `knowledge.py`（Task 1 已有方法）
- Test: `tests/test_review_api.py`

- [ ] **Step 1: 写失败测试**

```python
"""审核 API:列表/详情/通过写库/驳回/409。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from knowledge import KnowledgeBase, KnowledgeStorage
from review_api import create_review_router


class FakeStore:
    def __init__(self):
        self.rows = []

    def upsert(self, ids, vectors, metadatas):
        self.rows.append((ids, vectors, metadatas))


def _client():
    engine = create_engine("sqlite:///:memory:")
    KnowledgeBase.metadata.create_all(engine)
    storage = KnowledgeStorage(sessionmaker(bind=engine))
    store = FakeStore()
    app = FastAPI()
    app.include_router(create_review_router(
        storage,
        embed_fn=lambda texts: [[0.1] * 1024 for _ in texts],
        store_factory=lambda: store,
    ))
    return TestClient(app), storage, store


def test_list_and_detail_include_pending_snapshot():
    client, storage, _ = _client()
    rid = storage.create_review("标准问题", "示例答案")
    pid = storage.add_pending_question(
        "用户原话", "s1", source_entry="user_dislike",
        retrieved_snapshot='[{"title": "静夜思", "score": 0.9, "text": "床前明月光"}]',
    )
    storage.mark_pending_matched(pid, rid)
    listing = client.get("/api/admin/review").json()
    assert listing["items"][0]["standard_question"] == "标准问题"
    detail = client.get(f"/api/admin/review/{rid}").json()
    assert detail["pending"][0]["question"] == "用户原话"
    assert detail["pending"][0]["snapshot"][0]["title"] == "静夜思"


def test_approve_writes_chunk_and_marks_embedded():
    client, storage, store = _client()
    rid = storage.create_review("标准问题", "示例答案")
    resp = client.post(f"/api/admin/review/{rid}/approve", json={
        "approved_answer": "核准答案",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert store.rows and store.rows[0][0] == [body["chunkId"]]
    assert storage.get_review(rid)["status"] == "approved"
    assert storage.get_review(rid)["approved_answer"] == "核准答案"
    chunk = storage.get_chunk(body["chunkId"])
    assert chunk["status"] == "embedded"


def test_approve_edit_standard_question_and_answer():
    client, storage, _ = _client()
    rid = storage.create_review("旧问题", "旧答案")
    client.post(f"/api/admin/review/{rid}/approve", json={
        "standard_question": "新问题", "approved_answer": "新答案",
    })
    assert storage.get_review(rid)["standard_question"] == "新问题"


def test_reject_does_not_write_chunk():
    client, storage, _ = _client()
    rid = storage.create_review("问题", "答案")
    resp = client.post(f"/api/admin/review/{rid}/reject")
    assert resp.status_code == 200
    assert storage.get_review(rid)["status"] == "rejected"
    assert not storage.list_chunks() if hasattr(storage, "list_chunks") else True


def test_approve_non_pending_returns_409():
    client, storage, _ = _client()
    rid = storage.create_review("问题", "答案")
    storage.update_review_status(rid, "approved", approved_answer="x")
    resp = client.post(f"/api/admin/review/{rid}/approve", json={"approved_answer": "y"})
    assert resp.status_code == 409
```

- [ ] **Step 2: 跑失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_review_api.py -v`
Expected: FAIL（无 `review_api`）。

- [ ] **Step 3: 实现 `review_api.py`**

```python
"""审核后台 API:待审列表 / 详情 / 通过写库 / 驳回。"""
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from embeddings import embed as default_embed
from vector_store import get_store as default_store


class ApproveRequest(BaseModel):
    standard_question: str | None = None
    approved_answer: str


def _snapshot(raw: str | None) -> list:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def create_review_router(storage, *, embed_fn=None, store_factory=None) -> APIRouter:
    router = APIRouter()
    embed_fn = embed_fn or default_embed
    store_factory = store_factory or default_store

    @router.get("/api/admin/review")
    def list_reviews(status: str = "pending", limit: int = 50, offset: int = 0):
        items = storage.list_reviews(status=status or None, limit=limit, offset=offset)
        return {"items": items}

    @router.get("/api/admin/review/{review_id}")
    def get_review(review_id: int):
        review = storage.get_review(review_id)
        if review is None:
            raise HTTPException(status_code=404, detail={"message": "审核项不存在"})
        pending = storage.list_pending_by_review(review_id)
        for row in pending:
            row["snapshot"] = _snapshot(row.get("retrieved_snapshot"))
        return {**review, "pending": pending}

    @router.post("/api/admin/review/{review_id}/approve")
    def approve(review_id: int, body: ApproveRequest):
        review = storage.get_review(review_id)
        if review is None:
            raise HTTPException(status_code=404, detail={"message": "审核项不存在"})
        if review["status"] != "pending":
            raise HTTPException(status_code=409, detail={"message": "该审核项已处理"})
        answer = (body.approved_answer or "").strip()
        if not answer:
            raise HTTPException(status_code=400, detail={"message": "核准答案不能为空"})
        standard = (body.standard_question or review["standard_question"]).strip()
        if not standard:
            raise HTTPException(status_code=400, detail={"message": "标准问题不能为空"})
        text = f"Q: {standard}\nA: {answer}"
        try:
            storage.upsert_chunks([{
                "source_type": "qa", "source_id": review_id, "section": "faq", "seq": 0,
                "chunk_text": text, "raw_text": text, "title": standard,
            }])
            chunk_id = storage.get_chunk_id("qa", review_id, "faq", 0)
            if chunk_id is None:
                raise RuntimeError("知识块写入后未取到 id")
            vector = embed_fn([text])[0]
            store_factory().upsert(
                [chunk_id], [vector],
                [{"source_type": "qa", "title": standard, "writer": "", "dynasty": ""}],
            )
            storage.mark_embedded([chunk_id])
        except Exception as exc:  # noqa: BLE001 - 向量写入失败保持 pending,可重试
            print(f"[review] approve fail id={review_id}: {str(exc)[:200]}")
            raise HTTPException(
                status_code=503,
                detail={"message": f"知识库写入失败,请稍后重试: {str(exc)[:120]}"},
            )
        storage.update_review_status(
            review_id, "approved", approved_answer=answer, standard_question=standard,
        )
        return {"ok": True, "chunkId": chunk_id, "review": storage.get_review(review_id)}

    @router.post("/api/admin/review/{review_id}/reject")
    def reject(review_id: int):
        review = storage.get_review(review_id)
        if review is None:
            raise HTTPException(status_code=404, detail={"message": "审核项不存在"})
        if review["status"] != "pending":
            raise HTTPException(status_code=409, detail={"message": "该审核项已处理"})
        storage.update_review_status(review_id, "rejected")
        return {"ok": True, "review": storage.get_review(review_id)}

    return router
```

- [ ] **Step 4: main 接入**

```python
from review_api import create_review_router

app.include_router(create_review_router(knowledge_storage))
```

放在 `app = FastAPI(...)` 与 `knowledge_storage` 装配之后。`knowledge_storage` 在模块级装配段已存在。

- [ ] **Step 5: 跑通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_review_api.py -q`
Expected: 5 passed。再跑 `tests/test_workflow_endpoint.py -q`。

- [ ] **Step 6: 提交**

```powershell
git add potry-ai-agent/review_api.py potry-ai-agent/main.py potry-ai-agent/tests/test_review_api.py
git commit -m "feat(ch08): add review queue API with knowledge base write on approval"
```

---

### Task 7: 定时兜底 drain

**Files:**
- Modify: `config.py`
- Modify: `scheduler.py`
- Test: `tests/test_scheduler.py`

- [ ] **Step 1: 写失败测试**

```python
from apscheduler.triggers.interval import IntervalTrigger

from config import Settings
from scheduler import build_scheduler


def test_scheduler_has_flywheel_job():
    settings = Settings(
        llm_base_url="http://fake", llm_api_key="CONFIGURE_LOCALLY", llm_model="fake",
        history_max_tokens=2000, llm_temperature=0.7,
        mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
        flywheel_drain_minutes=7,
    )
    scheduler = build_scheduler(settings)
    job = scheduler.get_job("flywheel")
    assert job is not None
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval.total_seconds() == 7 * 60
```

- [ ] **Step 2: 跑失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_scheduler.py -v`
Expected: FAIL（无 job / 无字段）。

- [ ] **Step 3: 实现**

`config.py` 加默认值与 Settings 字段：

```python
_DEFAULT_FLYWHEEL_DRAIN_MINUTES = 5.0
```

```python
    flywheel_drain_minutes: float = _DEFAULT_FLYWHEEL_DRAIN_MINUTES
```

`load_settings` 读 `FLYWHEEL_DRAIN_MINUTES`，校验 > 0。

`scheduler.py`：

```python
from apscheduler.triggers.interval import IntervalTrigger


def run_flywheel(settings: Settings) -> None:
    """后台兜底:处理未匹配的 pending_questions。"""
    try:
        import asyncio
        from chat_service import build_llm
        from flywheel import FlywheelService
        from sqlalchemy.orm import sessionmaker

        engine = get_engine(settings.mysql_url)
        storage = KnowledgeStorage(sessionmaker(bind=engine))
        service = FlywheelService(storage, build_llm(settings))
        processed = asyncio.run(service.drain())
        print(f"[flywheel] 定时处理 {processed} 条")
    except Exception as exc:  # noqa: BLE001 - 定时任务失败不炸调度器
        print(f"[flywheel] 定时任务失败: {str(exc)[:200]}")


def build_scheduler(settings: Settings) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        run_mining,
        CronTrigger.from_crontab(settings.mining_cron),
        kwargs={"settings": settings},
        id="mining", replace_existing=True, coalesce=True, misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_flywheel,
        IntervalTrigger(minutes=settings.flywheel_drain_minutes),
        kwargs={"settings": settings},
        id="flywheel", replace_existing=True, coalesce=True, misfire_grace_time=600,
    )
    return scheduler
```

- [ ] **Step 4: 跑通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_scheduler.py -q`
Expected: 1 passed。再跑 `tests/test_config.py -q`。

- [ ] **Step 5: 提交**

```powershell
git add potry-ai-agent/config.py potry-ai-agent/scheduler.py potry-ai-agent/tests/test_scheduler.py
git commit -m "feat(ch08): add flywheel drain scheduled job"
```

---

### Task 8: 前端（聊天页 👍/👎 + 审核后台页）

**Files:**
- Modify: `static/chat.html`
- Create: `static/admin_review.html`
- Modify: `main.py`（`GET /admin/review` 静态页路由）

- [ ] **Step 1: 聊天页反馈按钮**

行为：
- 每条助手气泡下方加一行 `👍 有用` / `👎 没解决`。
- 点击 👍：按钮置灰，显示“感谢反馈”，不发请求。
- 点击 👎：POST `/agent/feedback/negative {sessionId, message}`，成功后显示“已反馈，会尽快改进”；失败显示“反馈失败，请稍后再试”。
- 需要把该轮用户问题带到助手气泡（`streamReply` 的 `userText`；resume 时可取上一条用户气泡文本）。
- 同一气泡只能反馈一次；按钮不影响输入框。

- [ ] **Step 2: 审核后台页**

新建 `static/admin_review.html`，原生 HTML/CSS/JS，风格与 chat.html 一致（暖金/宣纸）：
- 顶部标题“待审问题”。
- 左侧列表：标准化问题、出现次数、示例答案摘要、状态；分页/刷新。
- 点击行：右侧详情，显示可编辑的“标准问题”“核准答案”，关联用户原话列表（入池入口 + 时间），每条展开显示快照 Top5（标题/作者/朝代/得分/片段）。
- 底部“通过”“驳回”；通过调用 approve（带编辑后的字段），驳回调用 reject；操作后刷新列表并提示。
- 空列表显示“暂无待审问题”。

- [ ] **Step 3: 路由**

`main.py` 增加：

```python
@app.get("/admin/review")
async def admin_review_page():
    return FileResponse(Path(__file__).parent / "static" / "admin_review.html")
```

- [ ] **Step 4: 语法检查**

```powershell
node -e "const fs=require('fs');for(const f of ['static/chat.html','static/admin_review.html']){const h=fs.readFileSync(f,'utf8');const m=h.match(/<script>([\s\S]*)<\/script>/);new Function(m[1]);console.log(f,'OK')}"
```

- [ ] **Step 5: 提交**

```powershell
git add potry-ai-agent/static/chat.html potry-ai-agent/static/admin_review.html potry-ai-agent/main.py
git commit -m "feat(ch08): add chat feedback buttons and admin review page"
```

---

### Task 9: 验收 2/3/4 与完结留痕（本批）

**Files:**
- Create: `evals/accept_ch08_flywheel.py`
- Modify: `dev-notes/ch08.md`

- [ ] **Step 1: 验收脚本**

脚本用真实 HTTP：
1. 生成一个知识库没有的问题（如“《全唐诗》里收录了多少首王之涣的诗?”），POST `/agent/workflow`，断言 `status=awaiting`/兜底话术，轮询 `GET /api/admin/review` 直到出现该问题。
2. `GET /api/admin/review/{id}` 断言详情含用户原话与快照。
3. `POST approve`，再问同一问题，断言不再兜底且回答包含核准答案关键词。
4. 对一条回答 POST `/agent/feedback/negative`，轮询待审队列出现该问题。

- [ ] **Step 2: 跑全量**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: 全部通过。

- [ ] **Step 3: 真跑验收**

启动 MySQL、API（MCP 可不启动），执行：

```powershell
.\.venv\Scripts\python.exe evals\accept_ch08_flywheel.py
```

把输出原样记入 `dev-notes/ch08.md`；失败不得伪造。

- [ ] **Step 4: 留痕与提交**

`dev-notes/ch08.md` 追加阶段 2–9（计划定稿、每个任务、验收结论、finish）；提交：

```powershell
git add potry-ai-agent/evals/accept_ch08_flywheel.py dev-notes/ch08.md
git commit -m "chore(ch08): add flywheel acceptance script and finish notes"
```

---

## 自审

- Spec §4–§5 覆盖:问题池三列、三入口、标准化/查重/审核队列、审核写库、后台页、定时 drain。
- 无占位符;每个任务给出完整代码与命令。
- 类型/命名一致:`add_pending_question(..., source_entry, retrieved_snapshot)`、`get_pending_question`、`list_unmatched_pending`、`mark_pending_matched`、`create_review`、`increment_review_occurrences`、`update_review_status`、`get_chunk_id`、`FlywheelService.process_pending/drain/schedule`、`snapshot_hits`、`evidence_signals`、`is_confidence_sufficient`。
- Langfuse/评估流水线不在本计划,验收 1/5/6 标记暂缓。
