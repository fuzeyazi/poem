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
            llm_base_url="http://fake", llm_api_key="sk-fake", llm_model="fake",
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
