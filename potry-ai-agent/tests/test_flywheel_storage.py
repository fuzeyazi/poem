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
