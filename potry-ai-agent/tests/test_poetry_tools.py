import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import db
from embeddings import EMBED_DIM, set_embedder
from knowledge import KnowledgeBase, KnowledgeStorage
from tools.poetry_tools import query_dynasty_poems, query_poem, query_poet
from vector_store import set_store


class FakeEmbedder:
    def embed(self, texts):
        # embed() 有维度校验(须等于 EMBED_DIM),故造 1024 维假向量;FakeStore 不关心内容
        return [[1.0] + [0.0] * (EMBED_DIM - 1) for _ in texts]


class FakeStore:
    def __init__(self, hits):
        self.hits = hits

    def search(self, vector, topk, source_type):
        return [h for h in self.hits if h["source_type"] == source_type][:topk]

    def query_by_dynasty(self, dynasty, limit):
        return [h for h in self.hits if h.get("dynasty") == dynasty and h["source_type"] == "poem"][:limit]

    def upsert(self, ids, vectors, metadatas):
        raise AssertionError("工具只读,不应写 Milvus")


class DownStore:
    """模拟 Milvus 不可用 / 文件锁冲突:所有读操作都抛 MilvusException。"""

    def _boom(self):
        from pymilvus.exceptions import MilvusException

        raise MilvusException(message="milvus down")

    def search(self, vector, topk, source_type):
        self._boom()

    def query_by_dynasty(self, dynasty, limit):
        self._boom()

    def upsert(self, ids, vectors, metadatas):
        raise AssertionError("工具只读,不应写 Milvus")


@pytest.fixture
def kb(tmp_path, monkeypatch):
    """知识库落 SQLite 临时文件;db 单例复位以便指向该库;诗词表用同一 engine 建。"""
    path = str(tmp_path / "kb.db")
    monkeypatch.setenv("MYSQL_URL", f"sqlite:///{path}")
    monkeypatch.setenv("SIMILARITY_THRESHOLD", "0.5")
    db.reset_engine()
    engine = db.get_engine(f"sqlite:///{path}")
    KnowledgeBase.metadata.create_all(engine)
    db.PoetryBase.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        s.add(db.Potry(id=1, title="静夜思", dynasty="唐", writer="李白", type="五言绝句",
                       content="床前明月光,疑是地上霜。举头望明月,低头思故乡。",
                       translation="明亮的月光洒在床前。", shangxi="思乡之作。", remark=None, audioUrl=None))
        s.add(db.Writer(id=1, name="李白", simpleIntro="盛唐诗仙。", detailIntro="字太白,号青莲居士。", headImageUrl=None))
        s.commit()
    storage = KnowledgeStorage(sessionmaker(bind=engine))
    set_embedder(FakeEmbedder())
    yield storage, engine
    set_embedder(None)
    set_store(None)
    db.reset_engine()


def _poem_chunk(**over):
    base = {"source_type": "poem", "source_id": 1, "section": "原文", "seq": 0,
            "chunk_text": "静夜思|唐|李白|五言\n原文\n床前明月光。", "raw_text": "床前明月光。",
            "title": "静夜思", "writer": "李白", "dynasty": "唐"}
    base.update(over)
    return base


def test_query_poem_returns_contract_shape_from_vector_hit(kb):
    storage, _ = kb
    storage.upsert_chunks([_poem_chunk()])
    cid = storage.list_chunks()[0]["id"]
    set_store(FakeStore([{"id": cid, "score": 0.91, "source_type": "poem",
                          "title": "静夜思", "writer": "李白", "dynasty": "唐"}]))
    res = query_poem.invoke({"keyword": "那首讲月亮的叫啥"})
    assert res["ok"] is True and res["found"] is True
    assert res["poem"]["title"] == "静夜思" and res["poem"]["writer"] == "李白"
    assert set(res["poem"]) == {"title", "dynasty", "writer", "type", "content", "translation", "shangxi", "remark"}


def test_query_poem_found_false_when_below_threshold(kb):
    storage, _ = kb
    storage.upsert_chunks([_poem_chunk()])
    cid = storage.list_chunks()[0]["id"]
    set_store(FakeStore([{"id": cid, "score": 0.2, "source_type": "poem",
                          "title": "静夜思", "writer": "李白", "dynasty": "唐"}]))
    assert query_poem.invoke({"keyword": "随便问问"}) == {"ok": True, "found": False}


def test_query_poem_returns_ok_false_on_failure(kb):
    class Boom:
        def embed(self, texts):
            raise RuntimeError("模型挂了")

    set_embedder(Boom())
    res = query_poem.invoke({"keyword": "静夜思"})
    assert res["ok"] is False and "模型挂了" in res["error"]


def test_query_poem_degrades_when_vector_store_down(kb):
    """向量库抛 MilvusException 时必须降级为 ok:false,不得外抛。"""
    set_store(DownStore())
    res = query_poem.invoke({"keyword": "静夜思"})
    assert res["ok"] is False
    assert "milvus down" in res["error"]


def test_query_poet_returns_contract_shape(kb):
    storage, _ = kb
    storage.upsert_chunks([{"source_type": "poet", "source_id": 1, "section": "简简介", "seq": 0,
                            "chunk_text": "李白||李白|诗人\n简简介\n盛唐诗仙。", "raw_text": "盛唐诗仙。",
                            "title": "李白", "writer": "李白", "dynasty": None}])
    cid = storage.list_chunks()[0]["id"]
    set_store(FakeStore([{"id": cid, "score": 0.88, "source_type": "poet",
                          "title": "李白", "writer": "李白", "dynasty": ""}]))
    res = query_poet.invoke({"name": "李白"})
    assert res["ok"] is True and res["found"] is True
    assert set(res["poet"]) == {"name", "simpleIntro", "detailIntro", "headImageUrl"}
    assert res["works"] == ["静夜思"]


def test_query_dynasty_poems_returns_titles_deduped(kb):
    set_store(FakeStore([
        {"id": 1, "score": 0.0, "source_type": "poem", "title": "静夜思", "writer": "李白", "dynasty": "唐"},
        {"id": 2, "score": 0.0, "source_type": "poem", "title": "静夜思", "writer": "李白", "dynasty": "唐"},
        {"id": 3, "score": 0.0, "source_type": "poem", "title": "春晓", "writer": "孟浩然", "dynasty": "唐"},
    ]))
    res = query_dynasty_poems.invoke({"dynasty": "唐"})
    assert res["ok"] is True and res["found"] is True
    assert res["titles"] == ["静夜思", "春晓"] and res["count"] == 2


def test_query_dynasty_poems_paginates_until_enough_titles(kb):
    """同一首诗块数过多时,应翻倍重扫直到凑满 20 条不同标题,而非静默少给。"""

    class PagingStore(FakeStore):
        def query_by_dynasty(self, dynasty, limit):
            if limit < 200:  # 初始 scan=100:只够扫到同一首诗的多块,去重后远不足 20
                return [{"id": i, "title": "静夜思", "writer": "李白", "dynasty": "唐",
                         "source_type": "poem"} for i in range(limit)]
            return [{"id": 1000 + i, "title": f"诗{i}", "writer": "无名", "dynasty": "唐",
                     "source_type": "poem"} for i in range(20)]

    set_store(PagingStore([]))
    res = query_dynasty_poems.invoke({"dynasty": "唐"})
    assert res["ok"] is True and res["found"] is True
    assert res["count"] == 20 and len(res["titles"]) == 20


def test_query_dynasty_poems_degrades_when_vector_store_down(kb):
    set_store(DownStore())
    res = query_dynasty_poems.invoke({"dynasty": "唐"})
    assert res["ok"] is False
    assert "milvus down" in res["error"]


def test_truncate_keeps_contract_boundary():
    """_MAX_CONTENT=300 截断是契约一部分,须有护栏测试。"""
    from tools.poetry_tools import _truncate

    assert len(_truncate("甲" * 301)) == 300
    assert _truncate("甲" * 300) == "甲" * 300  # 恰好 300 不截
    assert _truncate(None) is None
    assert _truncate("") == ""
