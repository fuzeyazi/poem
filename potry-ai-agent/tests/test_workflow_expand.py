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
