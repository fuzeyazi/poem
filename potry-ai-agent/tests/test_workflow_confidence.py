"""知识检索(三源合并)与置信度闸判定;待处理问题落库。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import Settings
from embeddings import set_embedder
from knowledge import KnowledgeBase, KnowledgeStorage, PendingQuestion
from vector_store import set_store
from workflow.confidence import is_evidence_sufficient, retrieve_evidence

_DIM = 1024


def make_settings(**over):
    base = dict(
        llm_base_url="http://fake",
        llm_api_key="sk-fake",
        llm_model="fake",
        history_max_tokens=2000,
        llm_temperature=0.7,
        mysql_url="sqlite:///:memory:",
        embedding_model_path="fake-model-path",
    )
    base.update(over)
    return Settings(**base)


class FakeEmbedder:
    def embed(self, texts):
        return [[0.0] * _DIM for _ in texts]


class FakeStore:
    """按 source_type 返回不同分数,验证三源合并与降序。"""

    def __init__(self, scores=None, boom=False):
        self.scores = scores or {"poem": 0.9, "poet": 0.3, "qa": 0.6}
        self.boom = boom
        self.calls = []

    def search(self, vector, topk, source_type):
        self.calls.append(source_type)
        if self.boom:
            raise RuntimeError("milvus 不可用")
        return [
            {
                "id": abs(hash(source_type)) % 1000,
                "score": self.scores[source_type],
                "source_type": source_type,
                "title": "静夜思",
                "writer": "李白",
                "dynasty": "唐",
            }
        ]


@pytest.fixture
def inject():
    """注入 fake 嵌入器/向量库,测试后务必复位(否则污染其它用例)。"""
    def _inject(store):
        set_embedder(FakeEmbedder())
        set_store(store)
    yield _inject
    set_embedder(None)
    set_store(None)


def test_is_evidence_sufficient_boundary():
    assert is_evidence_sufficient(0.5, 0.5) is True    # >= 阈值即通过
    assert is_evidence_sufficient(0.4999, 0.5) is False


def test_retrieve_merges_three_sources_and_sorts(inject):
    store = FakeStore()
    inject(store)
    hits, score = retrieve_evidence("那首讲月亮的", make_settings())
    assert store.calls == ["poem", "poet", "qa"]       # 三类各查一次
    assert score == 0.9                                # top1 相似度
    assert [h["score"] for h in hits] == [0.9, 0.6, 0.3]  # 合并后降序


def test_retrieve_degrades_to_empty_on_store_failure(inject):
    inject(FakeStore(boom=True))
    hits, score = retrieve_evidence("随便问问", make_settings())
    assert hits == [] and score == 0.0                 # 检索失败视为证据不足(spec §10)


def test_retrieve_degrades_when_embedder_unavailable(monkeypatch):
    # 嵌入不可用(模型目录不存在等) → 整段降级为证据不足;用 monkeypatch 避免真的加载重模型
    def boom():
        raise RuntimeError("模型目录不存在")

    monkeypatch.setattr("embeddings.get_embedder", boom)
    hits, score = retrieve_evidence("随便问问", make_settings())
    assert hits == [] and score == 0.0


def test_add_pending_question_persists():
    engine = create_engine("sqlite:///:memory:")
    KnowledgeBase.metadata.create_all(engine)
    storage = KnowledgeStorage(sessionmaker(bind=engine))
    qid = storage.add_pending_question("一个没查到资料的问题", "s1")
    assert qid is not None
    with sessionmaker(bind=engine)() as session:
        row = session.get(PendingQuestion, qid)
        assert row.question == "一个没查到资料的问题"
        assert row.session_id == "s1"
