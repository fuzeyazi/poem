import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import mining
from knowledge import KnowledgeBase, KnowledgeStorage
from storage import ChatBase, ChatStorage


@pytest.fixture
def env():
    engine = create_engine("sqlite:///:memory:")
    KnowledgeBase.metadata.create_all(engine)
    ChatBase.metadata.create_all(engine)
    return KnowledgeStorage(sessionmaker(bind=engine)), ChatStorage(sessionmaker(bind=engine))


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def invoke(self, _messages):
        self.calls += 1

        class _Msg:
            content = self.payload

        return _Msg()


def test_parse_pairs_extracts_json_array_from_fenced_text():
    raw = '好的:\n```json\n[{"question": "月亮那首叫啥", "answer": "静夜思", "tags": ["月亮"]}]\n```'
    assert mining.parse_pairs(raw) == [{"question": "月亮那首叫啥", "answer": "静夜思", "tags": ["月亮"]}]


def test_parse_pairs_returns_empty_on_garbage():
    assert mining.parse_pairs("我不知道") == []


def test_normalize_question_strips_punctuation_and_whitespace():
    assert mining.normalize_question("《静夜思》是谁写的?") == mining.normalize_question("静夜思是谁写的")


def test_dedupe_pairs_drops_duplicates_and_existing():
    pairs = [
        {"question": "月亮那首叫啥", "answer": "A", "tags": []},
        {"question": "月亮那首叫啥?", "answer": "A2", "tags": []},
        {"question": "李白是谁", "answer": "B", "tags": []},
    ]
    out = mining.dedupe_pairs(pairs, existing_questions={mining.normalize_question("李白是谁?")})
    assert [p["question"] for p in out] == ["月亮那首叫啥"]


def test_mine_writes_staging_then_chunks_and_advances_cursor(env):
    storage, chat = env
    chat.persist_turn("s1", "月亮那首叫啥", "静夜思")
    fake = FakeLLM('[{"question": "月亮那首叫啥", "answer": "静夜思", "tags": []}]')
    stats = mining.mine(storage=storage, chat_storage=chat, llm=fake, batch_size=10)
    assert stats["extracted"] == 1 and stats["written"] == 1
    assert storage.list_staging() == []  # 挖完暂存清空
    chunks = storage.list_chunks(source_type="qa")
    assert len(chunks) == 1 and chunks[0]["raw_text"] == "静夜思"
    assert storage.get_cursor() > 0


def test_mine_is_incremental_and_idempotent(env):
    storage, chat = env
    chat.persist_turn("s1", "月亮那首叫啥", "静夜思")
    fake = FakeLLM('[{"question": "月亮那首叫啥", "answer": "静夜思", "tags": []}]')
    mining.mine(storage=storage, chat_storage=chat, llm=fake, batch_size=10)
    first_calls = fake.calls
    mining.mine(storage=storage, chat_storage=chat, llm=fake, batch_size=10)  # 再跑
    assert fake.calls == first_calls  # 水位之内,无新对话 → 不再喂 LLM
    assert len(storage.list_chunks(source_type="qa")) == 1  # 幂等不重复


def test_mine_pairs_final_answer_not_tool_intermediate(env):
    """工具轮的最终答案必须配对到用户问题,不能配到 content 为空的中间态 assistant。"""
    from storage import Conversation, Message

    storage, chat = env
    with chat._factory() as session:
        session.add(Conversation(session_id="s1"))
        session.flush()
        session.add(Message(conversation_id=1, role="user", content="静夜思谁写的"))
        session.add(Message(conversation_id=1, role="assistant", content="", tool_call_id="call_1"))
        session.add(Message(conversation_id=1, role="tool", content='{"ok": true}'))
        session.add(Message(conversation_id=1, role="assistant", content="李白。"))
        session.commit()
    transcripts = mining._load_transcripts(chat, 0)
    assert transcripts[0]["pairs"] == [{"user": "静夜思谁写的", "assistant": "李白。"}]


def test_mine_does_not_advance_cursor_past_failed_session(env):
    storage, chat = env
    chat.persist_turn("s1", "q1", "a1")

    class BoomLLM:
        def invoke(self, _m):
            raise RuntimeError("network boom")

    stats = mining.mine(storage=storage, chat_storage=chat, llm=BoomLLM(), batch_size=10)
    assert stats["extracted"] == 0
    assert stats["cursor"] == 0
    assert storage.get_cursor() == 0  # 失败会话未被水位越过,下轮可重挖


def test_mine_retries_failed_session_next_round(env):
    storage, chat = env
    chat.persist_turn("s1", "月亮那首叫啥", "静夜思")

    class BoomLLM:
        def invoke(self, _m):
            raise RuntimeError("network boom")

    mining.mine(storage=storage, chat_storage=chat, llm=BoomLLM(), batch_size=10)
    ok = FakeLLM('[{"question": "月亮那首叫啥", "answer": "静夜思", "tags": []}]')
    stats = mining.mine(storage=storage, chat_storage=chat, llm=ok, batch_size=10)
    assert stats["written"] == 1
    assert storage.get_cursor() > 0


def test_parse_pairs_ignores_prose_brackets():
    raw = '参考 [1]:\n[{"question": "q", "answer": "a", "tags": []}]'
    assert mining.parse_pairs(raw) == [{"question": "q", "answer": "a", "tags": []}]


def test_mine_returns_zeros_when_no_new_transcripts(env):
    storage, chat = env
    assert mining.mine(storage=storage, chat_storage=chat, llm=FakeLLM("[]"), batch_size=10) == {
        "transcripts": 0, "batches": 0, "extracted": 0, "written": 0, "cursor": 0,
    }
