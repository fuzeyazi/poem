from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from knowledge import KnowledgeBase, KnowledgeStorage


def make_storage():
    engine = create_engine("sqlite:///:memory:")
    KnowledgeBase.metadata.create_all(engine)
    return KnowledgeStorage(sessionmaker(bind=engine))


def _chunk(**over):
    base = {
        "source_type": "poem",
        "source_id": 1,
        "section": "原文",
        "seq": 0,
        "chunk_text": "静夜思|唐|李白|五言\n原文\n床前明月光。",
        "raw_text": "床前明月光。",
        "title": "静夜思",
        "writer": "李白",
        "dynasty": "唐",
    }
    base.update(over)
    return base


def test_upsert_chunks_is_idempotent_by_unique_key():
    st = make_storage()
    assert st.upsert_chunks([_chunk()]) == 1
    assert st.upsert_chunks([_chunk()]) == 1  # 同键重跑不新增
    assert st.count_by_status() == {"pending": 1}


def test_upsert_chunks_resets_status_when_text_changes():
    st = make_storage()
    st.upsert_chunks([_chunk()])
    st.mark_embedded([st.list_pending()[0]["id"]])
    assert st.count_by_status() == {"embedded": 1}
    st.upsert_chunks([_chunk(chunk_text="静夜思|唐|李白|五言\n原文\n床前明月光。疑是地上霜。")])
    assert st.count_by_status() == {"pending": 1}  # 文本变了要重嵌


def test_mark_embedded_sets_vector_id_equal_chunk_id():
    st = make_storage()
    st.upsert_chunks([_chunk()])
    cid = st.list_pending()[0]["id"]
    st.mark_embedded([cid])
    assert st.get_chunk(cid)["vector_id"] == cid
    assert st.get_chunk(cid)["status"] == "embedded"


def test_list_pending_respects_limit():
    st = make_storage()
    st.upsert_chunks([_chunk(seq=i, section=f"原文{i}") for i in range(5)])
    assert len(st.list_pending(limit=2)) == 2


def test_staging_and_cursor_round_trip():
    st = make_storage()
    st.add_staging([{"question": "月亮那首叫啥", "answer": "静夜思", "tags": "[]", "source_session_id": "s1"}])
    assert len(st.list_staging()) == 1
    st.clear_staging()
    assert st.list_staging() == []
    assert st.get_cursor() == 0
    st.set_cursor(42)
    assert st.get_cursor() == 42


def test_get_chunk_returns_none_for_unknown_id():
    st = make_storage()
    assert st.get_chunk(999) is None


def test_list_chunks_filters_by_source_type():
    st = make_storage()
    st.upsert_chunks([_chunk(), _chunk(source_type="poet", source_id=9, section="简简介")])
    assert len(st.list_chunks()) == 2
    assert [c["source_type"] for c in st.list_chunks(source_type="poet")] == ["poet"]


def test_count_by_status_reports_mixed_states():
    st = make_storage()
    st.upsert_chunks([_chunk(seq=0), _chunk(seq=1), _chunk(seq=2)])
    st.mark_embedded([st.list_pending()[0]["id"]])
    assert st.count_by_status() == {"pending": 2, "embedded": 1}


def test_set_cursor_updates_existing_row_second_time():
    st = make_storage()
    st.set_cursor(10)
    st.set_cursor(20)
    assert st.get_cursor() == 20


def test_clear_staging_does_not_touch_cursor():
    st = make_storage()
    st.set_cursor(7)
    st.add_staging([{"question": "q", "answer": "a", "tags": "[]", "source_session_id": "s"}])
    st.clear_staging()
    assert st.list_staging() == []
    assert st.get_cursor() == 7


def test_upsert_chunks_retries_once_on_unique_conflict(monkeypatch):
    from sqlalchemy.exc import IntegrityError

    st = make_storage()
    calls = {"n": 0}
    real = st._upsert_chunks_once

    def flaky(chunks):
        calls["n"] += 1
        if calls["n"] == 1:
            raise IntegrityError("stmt", {}, Exception("uq_knowledge_chunk_key"))
        return real(chunks)

    monkeypatch.setattr(st, "_upsert_chunks_once", flaky)
    assert st.upsert_chunks([_chunk()]) == 1
    assert calls["n"] == 2
    assert st.count_by_status() == {"pending": 1}


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
