import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from storage import (
    ChatBase,
    ChatStorage,
    Conversation,
    ConversationSummary,
    Message,
    ensure_schema,
)


def make_storage():
    engine = create_engine("sqlite:///:memory:")
    ChatBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    return ChatStorage(factory), factory


def test_persist_turn_writes_two_rows_and_returns_ids():
    st, _ = make_storage()
    cid, uid, aid = st.persist_turn("s1", "《静夜思》是谁写的", "是李白", userid="u1")
    assert uid is not None and aid is not None and uid < aid
    rows = st.load_messages(cid)
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert rows[0]["content"] == "《静夜思》是谁写的"
    assert rows[1]["content"] == "是李白"


def test_resume_turn_skips_empty_user_row():
    st, _ = make_storage()
    _, uid, aid = st.persist_turn("s1", "", "判定结果")
    assert uid is None
    assert [r["role"] for r in st.load_messages(1)] == ["assistant"]


def test_conversation_reused_and_userid_kept():
    st, _ = make_storage()
    cid1, _, _ = st.persist_turn("s1", "第一句", "答一", userid="u1")
    cid2, _, _ = st.persist_turn("s1", "第二句", "答二", userid="u1")
    assert cid1 == cid2
    assert len(st.load_messages(cid1)) == 4


def test_load_context_returns_rows_anchors_and_summaries():
    st, _ = make_storage()
    st.persist_turn("s1", "第一问", "第一答")
    st.persist_turn("s1", "第二问", "第二答")
    snapshot = st.load_context("s1")
    assert [r["role"] for r in snapshot["rows"]] == ["user", "assistant", "user", "assistant"]
    assert snapshot["summaryUpto"] == 0 and snapshot["layer1From"] == 0
    assert snapshot["conversationId"] == 1


def test_add_summary_appends_seq_and_advances_anchor():
    st, _ = make_storage()
    st.persist_turn("s1", "问", "答")
    assert st.add_summary(1, "用户问了《静夜思》。", upto_msg_id=2) == 1
    assert st.add_summary(1, "用户又问了李白。", upto_msg_id=4) == 2
    snapshot = st.load_context("s1")
    assert snapshot["summaryUpto"] == 4
    assert [s["seq"] for s in snapshot["summaries"]] == [1, 2]


def test_summary_unique_key_enforced():
    _, factory = make_storage()
    with factory() as session:
        session.add(Conversation(session_id="s1"))
        session.flush()
        session.add(ConversationSummary(conversation_id=1, seq=1, upto_msg_id=2, content="a"))
        session.commit()
    with pytest.raises(IntegrityError):
        with factory() as session:
            session.add(ConversationSummary(conversation_id=1, seq=1, upto_msg_id=3, content="b"))
            session.commit()


def test_list_conversations_sorted_preview_and_summarized():
    st, _ = make_storage()
    st.persist_turn("old", "《静夜思》是谁写的", "李白", userid="u1")
    _, _, _ = st.persist_turn("new", "找一首写月亮的诗", "《静夜思》", userid="u1")
    st.add_summary(1, "梗概", upto_msg_id=2)
    convs = st.list_conversations("u1")
    assert [c["sessionId"] for c in convs] == ["new", "old"]
    assert convs[0]["preview"].startswith("找一首写月亮的诗")
    assert convs[1]["summarized"] is True
    assert st.list_conversations("u2") == []


def test_load_conversation_messages_filters_tool_and_checks_user():
    st, factory = make_storage()
    st.persist_turn("s1", "问", "答", userid="u1")
    with factory() as session:
        session.add(Message(conversation_id=1, role="tool", content='{"ok": true}'))
        session.commit()
    rows = st.load_conversation_messages("s1", "u1")
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert st.load_conversation_messages("s1", "u2") is None
    assert st.load_conversation_messages("nope", "u1") is None


def test_ensure_schema_adds_missing_columns(tmp_path):
    db = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE conversations (id INTEGER PRIMARY KEY, session_id VARCHAR(64), created_at DATETIME)"
        ))
    ensure_schema(engine)
    names = {c["name"] for c in inspect(engine).get_columns("conversations")}
    assert {"userid", "summary_upto_msg_id", "layer1_from_msg_id", "updated_at"} <= names
