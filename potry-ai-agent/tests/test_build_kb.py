import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import build_kb
from db import PoetryBase, Potry, Writer
from knowledge import KnowledgeBase, KnowledgeStorage
from vector_store import MilvusLiteVectorStore


class FakeEmbedder:
    def embed(self, texts):
        # 长度编码的假向量,维度固定 4,足够断言"写过 Milvus"
        return [[float(len(t))] * 4 for t in texts]


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    KnowledgeBase.metadata.create_all(engine)
    storage = KnowledgeStorage(sessionmaker(bind=engine))
    store = MilvusLiteVectorStore(str(tmp_path / "kb.db"), "knowledge", dim=4)
    monkeypatch.setattr(build_kb, "embed", FakeEmbedder().embed)
    return storage, store


def _chunk(**over):
    base = {"source_type": "poem", "source_id": 1, "section": "原文", "seq": 0,
            "chunk_text": "x", "raw_text": "x", "title": "t", "writer": "w", "dynasty": "d"}
    base.update(over)
    return base


def test_embed_pending_moves_all_to_embedded(env):
    storage, store = env
    storage.upsert_chunks([_chunk(seq=0), _chunk(seq=1, section="译文")])
    stats = build_kb.embed_pending(storage, store, batch_size=1)
    assert stats == {"embedded": 2, "failed": 0, "remaining": 0}
    assert storage.count_by_status() == {"embedded": 2}
    assert store.search([9.0, 9.0, 9.0, 9.0], topk=5, source_type="poem")


def test_embed_pending_keeps_pending_and_reports_failure(env, monkeypatch):
    storage, store = env

    def boom(texts):
        raise RuntimeError("模型挂了")

    monkeypatch.setattr(build_kb, "embed", boom)
    storage.upsert_chunks([_chunk()])
    stats = build_kb.embed_pending(storage, store, batch_size=1)
    assert stats["embedded"] == 0 and stats["failed"] == 1 and stats["remaining"] == 1
    assert storage.count_by_status() == {"pending": 1}  # 挂了能重跑


def test_embed_pending_picks_up_pending_after_interruption(env):
    """模拟"中断后重跑":上一轮已嵌一半就被中断(进程被杀),本轮只补剩下的、不重复嵌已完成块。

    embed_pending 一次调用会把当前所有 pending 处理完(见 test_embed_pending_moves_all_to_embedded),
    故"上一轮嵌了一半"用外部预标记模拟(进程中断后块留在 embedded,是真实的库状态)。
    """
    storage, store = env
    storage.upsert_chunks([_chunk(seq=i, section=f"原文{i}") for i in range(4)])
    done = [c["id"] for c in storage.list_pending(limit=2)]
    storage.mark_embedded(done)  # 模拟上一轮已完成的前一半
    assert storage.count_by_status() == {"embedded": 2, "pending": 2}
    stats = build_kb.embed_pending(storage, store, batch_size=2)
    assert stats == {"embedded": 2, "failed": 0, "remaining": 0}
    assert storage.count_by_status() == {"embedded": 4}


def _make_poetry_session():
    engine = create_engine("sqlite:///:memory:")
    PoetryBase.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Potry(id=1, title="静夜思", dynasty="唐", writer="李白", type="五言",
                      content="床前明月光,疑是地上霜。", translation="月光洒在床前。",
                      shangxi=None, remark=None, audioUrl=None))
    session.add(Potry(id=2, title="春晓", dynasty="唐", writer="孟浩然", type="五言",
                      content="春眠不觉晓。", translation=None, shangxi=None, remark=None, audioUrl=None))
    session.add(Writer(id=1, name="李白", simpleIntro="盛唐诗仙。", detailIntro=None, headImageUrl=None))
    session.commit()
    return session


def test_collect_poem_chunks_maps_source_and_metadata():
    session = _make_poetry_session()
    try:
        rows = build_kb.collect_poem_chunks(session, chunk_size=400, overlap=60)
        assert {r["source_id"] for r in rows} == {1, 2}
        first = [r for r in rows if r["source_id"] == 1]
        assert all(r["source_type"] == "poem" and r["title"] == "静夜思"
                   and r["writer"] == "李白" and r["dynasty"] == "唐" for r in first)
        assert {r["section"] for r in first} == {"原文", "译文"}
    finally:
        session.close()


def test_collect_poem_chunks_respects_limit():
    session = _make_poetry_session()
    try:
        rows_one = build_kb.collect_poem_chunks(session, 400, 60, limit=1)
        assert {r["source_id"] for r in rows_one} == {1}
        # limit=0 必须返回空,而不是被当成"不限制"返回全量(旧 if limit: 实现会失败)
        assert build_kb.collect_poem_chunks(session, 400, 60, limit=0) == []
        # 不传 limit 才是"不限制"
        assert {r["source_id"] for r in build_kb.collect_poem_chunks(session, 400, 60)} == {1, 2}
    finally:
        session.close()


def test_collect_poet_chunks_maps_source_and_metadata():
    session = _make_poetry_session()
    try:
        rows = build_kb.collect_poet_chunks(session, 400, 60)
        assert len(rows) == 1
        r = rows[0]
        assert r["source_type"] == "poet" and r["source_id"] == 1
        assert r["title"] == "李白" and r["writer"] == "李白" and r["dynasty"] is None
        assert r["section"] == "简简介"
    finally:
        session.close()


def test_embed_pending_resumes_after_midway_batch_failure(env):
    """混合路径:前批成功、后批失败 → remaining 留待重跑 → 重跑补齐(验收标准 2 的核心交互)。"""
    storage, store = env
    storage.upsert_chunks([_chunk(seq=i, section=f"原文{i}") for i in range(4)])
    real = FakeEmbedder()
    calls = {"n": 0}

    def flaky(texts):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("第二批挂了")
        return real.embed(texts)

    import build_kb as bk

    original = bk.embed
    bk.embed = flaky
    try:
        stats = bk.embed_pending(storage, store, batch_size=2)
    finally:
        bk.embed = original
    assert stats == {"embedded": 2, "failed": 2, "remaining": 2}
    assert storage.count_by_status() == {"embedded": 2, "pending": 2}

    stats2 = bk.embed_pending(storage, store, batch_size=2)  # 重跑补齐
    assert stats2 == {"embedded": 2, "failed": 0, "remaining": 0}
    assert storage.count_by_status() == {"embedded": 4}


def test_embed_pending_propagates_value_error_and_keeps_pending(env, monkeypatch):
    """配置类错误(维度/长度校验不通过)必须上抛,不能被当成"暂时失败"吞掉,也不得标记已嵌入。"""
    storage, store = env
    storage.upsert_chunks([_chunk(seq=i, section=f"原文{i}") for i in range(2)])

    def bad_dim(texts):
        raise ValueError("嵌入维度与 EMBED_DIM(1024) 不一致")

    monkeypatch.setattr(build_kb, "embed", bad_dim)
    with pytest.raises(ValueError):  # 若被 except Exception 吞掉,此处失败 → 同时守护 except 顺序契约
        build_kb.embed_pending(storage, store, batch_size=2)
    assert storage.count_by_status() == {"pending": 2}  # 未误标 embedded,可重跑


def test_run_writes_chunks_and_reports_stats(tmp_path, monkeypatch):
    import build_kb as bk

    engine = create_engine("sqlite:///:memory:")
    KnowledgeBase.metadata.create_all(engine)
    PoetryBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as s:
        s.add(Potry(id=1, title="静夜思", dynasty="唐", writer="李白", type="五言",
                    content="床前明月光,疑是地上霜。", translation="月光洒在床前。",
                    shangxi=None, remark=None, audioUrl=None))
        s.add(Writer(id=1, name="李白", simpleIntro="盛唐诗仙。", detailIntro=None, headImageUrl=None))
        s.commit()

    class _S:
        mysql_url = "sqlite:///:memory:"
        chunk_size = 400
        chunk_overlap = 60
        milvus_db_path = str(tmp_path / "kb.db")
        milvus_collection = "knowledge"

    monkeypatch.setattr(bk, "load_settings", lambda: _S())
    monkeypatch.setattr(bk, "get_engine", lambda url: engine)
    monkeypatch.setattr(bk, "new_session", lambda url: factory())
    monkeypatch.setattr(bk, "embed", FakeEmbedder().embed)
    # run() 默认建 1024 维集合,而假 embedder 是 4 维,故此处固定 dim=4
    monkeypatch.setattr(bk, "MilvusLiteVectorStore", lambda p, c: MilvusLiteVectorStore(p, c, dim=4))

    stats = bk.run(only="poem")
    assert stats["chunks_written"] == 2  # 只切诗(不含诗人):静夜思 原文+译文 = 2
    assert stats["embedded"] == 2 and stats["failed"] == 0 and stats["remaining"] == 0
    assert stats["status_counts"] == {"embedded": 2}

    stats2 = bk.run(skip_chunk=True, only="poem")  # 只补向量化,不重切
    assert stats2["chunks_written"] == 0
    assert stats2["embedded"] == 0 and stats2["remaining"] == 0


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
