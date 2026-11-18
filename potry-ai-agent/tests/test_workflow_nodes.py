"""六个非 Agent 节点 + 条件边判定:透传 / 分类降级 / 硬编码分流 / 检索 / 闸 / 日志。"""
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from app_storage import CORRECTION_CATEGORIES
from config import Settings
from prompts import CHITCHAT_REPLY, COMPLAINT_REPLY, FALLBACK_REPLY
from workflow import intent
from workflow.deps import WorkflowDeps, configure
from workflow.nodes import (
    after_gate,
    after_resolve,
    after_route,
    after_slot_check,
    classify_node,
    expand_query_node,
    gate_node,
    log_node,
    resolve_node,
    retrieve_node,
    retrieve_policy_node,
    route_node,
    slot_check_node,
)


class ScriptedLLM:
    def __init__(self, reply="", boom=False):
        self.reply = reply
        self.boom = boom

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        if self.boom:
            raise ConnectionError("upstream down")
        return AIMessage(content=self.reply)


class FakeKnowledgeStorage:
    def __init__(self):
        self.pending = []
        self.chunks = {}

    def get_chunk(self, chunk_id):
        return self.chunks.get(chunk_id)

    def add_pending_question(self, question, session_id=None, **kwargs):
        self.pending.append((question, session_id))
        return len(self.pending)


class FakeChatStorage:
    def __init__(self):
        self.turns = []
        self.rows = []
        self._id = 0

    def persist_turn(self, session_id, user_text, answer, userid=None):
        self.turns.append((session_id, user_text, answer))
        self._id += 1
        user_id = self._id
        self.rows.append({"id": user_id, "role": "user", "content": user_text})
        self._id += 1
        self.rows.append({"id": self._id, "role": "assistant", "content": answer})
        return 1, user_id, self._id

    def load_context(self, session_id):
        return {"conversationId": 1, "summaryUpto": 0, "layer1From": 0,
                "rows": list(self.rows), "summaries": []}

    def advance_layer1_anchor(self, conversation_id, msg_id):
        pass

    def add_summary(self, conversation_id, content, upto_msg_id):
        return None


def make_settings(**over):
    base = dict(
        llm_base_url="http://fake", llm_api_key="sk-fake", llm_model="fake",
        history_max_tokens=2000, llm_temperature=0.7,
        mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
        similarity_threshold=0.5,
    )
    base.update(over)
    return Settings(**base)


def _deps(llm=None, knowledge=None, chat=None, **over):
    deps = WorkflowDeps(make_settings(**over), llm or ScriptedLLM(), None, knowledge, chat)
    configure(deps)
    return deps


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    configure(None)


@pytest.mark.asyncio
async def test_resolve_node_passes_through_and_resets_turn_fields():
    _deps(ScriptedLLM())
    out = await resolve_node({"user_input": "那首讲月亮的叫啥"})
    assert out["resolved_input"] == "那首讲月亮的叫啥"
    assert out["actions"] == []
    assert out["iterations"] == 0
    assert out["tokens_used"] == 0
    assert out["gate_status"] == "skip"
    assert out["tool_trace"] == []
    assert out["retrieved"] == []
    assert out["evidence_score"] is None
    assert out["answer"] == ""
    assert out["fallback_reason"] == ""
    assert out["confidence"] == 0.0
    assert out["query_changed"] is False
    assert out["policy_hits"] == []
    assert out["correction_categories"] == []
    assert out["pending_subflow"] is False and out["candidates"] == []
    assert out["turn_message_start"] == 0
    assert [m.content for m in out["messages"]] == ["那首讲月亮的叫啥"]


@pytest.mark.asyncio
async def test_classify_node_parses_json_with_confidence():
    _deps(ScriptedLLM(reply='{"intent": "find_poem", "confidence": 0.7}'))
    assert await classify_node({"resolved_input": "找那首讲月亮的"}) == {"intent": "find_poem", "confidence": 0.7}


@pytest.mark.asyncio
async def test_classify_node_degrades_to_other_on_bad_json():
    _deps(ScriptedLLM(reply="我觉得这是查诗人吧"))
    assert await classify_node({"resolved_input": "x"}) == {"intent": intent.DEFAULT_INTENT, "confidence": 0.0}


@pytest.mark.asyncio
async def test_classify_node_degrades_to_other_on_model_failure():
    _deps(ScriptedLLM(boom=True))
    assert await classify_node({"resolved_input": "x"}) == {"intent": intent.DEFAULT_INTENT, "confidence": 0.0}


def test_route_node_knowledge_and_business_do_not_answer():
    _deps()
    assert route_node({"intent": "poem_explain"}) == {"route": intent.ROUTE_KNOWLEDGE, "subflow_kind": ""}
    assert route_node({"intent": "find_poet"}) == {"route": intent.ROUTE_BUSINESS, "subflow_kind": ""}


def test_route_node_ruling_marks_subflow_kind():
    assert route_node({"intent": "poem_meter"}) == {"route": intent.ROUTE_RULING, "subflow_kind": "meter"}
    assert route_node({"intent": "poem_verify"}) == {"route": intent.ROUTE_RULING, "subflow_kind": "verify"}


def test_route_node_complaint_carries_two_independent_actions():
    out = route_node({"intent": "complaint"})
    assert out["route"] == intent.ROUTE_COMPLAINT
    assert out["answer"] == COMPLAINT_REPLY
    assert out["actions"] == ["handoff", "feedback"]   # 两个独立操作标识


def test_route_node_chitchat_uses_preset_reply():
    out = route_node({"intent": "chitchat"})
    assert out == {"route": intent.ROUTE_CHITCHAT, "subflow_kind": "", "answer": CHITCHAT_REPLY}


def test_route_node_unknown_intent_falls_to_other():
    # 兜底类改为 other(原降级 chitchat):拿不准不硬塞业务意图
    assert route_node({"intent": "no_such"})["route"] == intent.ROUTE_OTHER


def test_after_route_branches_six_outlets():
    assert after_route({"route": intent.ROUTE_KNOWLEDGE}) == "retrieve"
    assert after_route({"route": intent.ROUTE_RULING}) == "slot_check"
    assert after_route({"route": intent.ROUTE_BUSINESS}) == "agent"
    assert after_route({"route": intent.ROUTE_OTHER}) == "agent"
    assert after_route({"route": intent.ROUTE_COMPLAINT}) == "log"
    assert after_route({"route": intent.ROUTE_CHITCHAT}) == "log"


def test_retrieve_node_enriches_hit_with_text(monkeypatch):
    knowledge = FakeKnowledgeStorage()
    knowledge.chunks[7] = {"id": 7, "raw_text": "床前明月光,疑是地上霜。"}
    _deps(knowledge=knowledge)

    import workflow.nodes as nodesModule

    monkeypatch.setattr(
        nodesModule,
        "retrieve_evidence",
        lambda question, settings: ([{"id": 7, "score": 0.8, "source_type": "poem", "title": "静夜思"}], 0.8),
    )
    out = retrieve_node({"resolved_input": "静夜思什么意思"})
    assert out["evidence_score"] == 0.8
    assert out["retrieved"][0]["text"] == "床前明月光,疑是地上霜。"


def test_retrieve_node_survives_chunk_lookup_failure(monkeypatch):
    class BoomChunkStorage:
        def get_chunk(self, chunk_id):
            raise RuntimeError("mysql down")

        def add_pending_question(self, question, session_id=None, **kwargs):
            return 1

    _deps(knowledge=BoomChunkStorage())

    import workflow.nodes as nodes_module
    monkeypatch.setattr(
        nodes_module,
        "retrieve_evidence",
        lambda question, settings: ([{"id": 1, "score": 0.9, "source_type": "poem"}], 0.9),
    )
    out = retrieve_node({"resolved_input": "x"})   # 不抛即通过
    assert out["retrieved"][0]["text"] == ""
    assert out["evidence_score"] == 0.9


def test_gate_node_passes_when_evidence_confidence_meets_threshold():
    _deps(evidence_min_score=0.3, evidence_confidence_threshold=0.5)
    hits = [{"id": 1, "score": 0.9}, {"id": 2, "score": 0.8}]
    out = gate_node({"retrieved": hits})
    assert out["gate_status"] == "pass"
    assert out["evidence_confidence"] >= 0.5
    assert out["gate_signals"]["top1"] == 0.9


def test_gate_node_falls_back_and_records_pending():
    knowledge = FakeKnowledgeStorage()
    _deps(knowledge=knowledge, evidence_min_score=0.3, evidence_confidence_threshold=0.5)
    out = gate_node({
        "retrieved": [{"id": 1, "score": 0.2}],
        "user_input": "冷门问题", "session_id": "s1",
    })
    assert out["gate_status"] == "insufficient"
    assert out["answer"] == FALLBACK_REPLY
    assert out["fallback_reason"] == "insufficient_evidence"
    assert knowledge.pending == [("冷门问题", "s1")]


def test_gate_insufficient_writes_snapshot_and_schedules(monkeypatch):
    scheduled = []

    class FakePending:
        def __init__(self):
            self.kwargs = {}

        def add_pending_question(self, question, session_id=None, **kwargs):
            self.kwargs = kwargs
            return 7

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


def test_after_gate_branches():
    assert after_gate({"gate_status": "pass"}) == "agent"
    assert after_gate({"gate_status": "insufficient"}) == "log"


@pytest.mark.asyncio
async def test_log_node_prints_structured_line_and_persists(capsys):
    chat = FakeChatStorage()
    _deps(chat=chat)
    state = {
        "session_id": "s1", "user_input": "《静夜思》是谁写的", "intent": "find_poet",
        "route": "business", "gate_status": "skip", "iterations": 2, "tokens_used": 321,
        "answer": "是李白", "started_at": 0.0,
        "tool_trace": [{"tool": "query_poet", "args": {"name": "李白"}, "tool_call_id": "c1", "content": "{}", "durationMs": 12, "status": "done"}],
    }
    await log_node(state)
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert line.startswith("[wf] intent=find_poet conf=- route=business gate=skip score=- confidence=- iters=2 tokens=321 elapsed=")
    session_id, user_text, answer = chat.turns[0]
    assert session_id == "s1"
    assert (user_text, answer) == ("《静夜思》是谁写的", "是李白")


@pytest.mark.asyncio
async def test_log_node_prints_score_when_retrieval_happened(capsys):
    _deps()
    await log_node({"user_input": "x", "intent": "poem_explain", "route": "knowledge",
                    "gate_status": "pass", "evidence_score": 0.8123, "iterations": 1, "tokens_used": 5})
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert "gate=pass score=0.8123" in line


@pytest.mark.asyncio
async def test_log_node_survives_storage_failure(capsys):
    class BoomChat:
        def persist_turn(self, session_id, user_text, answer, userid=None):
            raise RuntimeError("mysql down")

    _deps(chat=BoomChat())
    await log_node({"session_id": "s1", "user_input": "x", "answer": "y"})   # 不抛即通过


@pytest.mark.asyncio
async def test_log_node_survives_after_persist_failure(capsys):
    class AfterPersistBoomStorage(FakeChatStorage):
        def load_context(self, session_id):
            raise RuntimeError("read fail")

    _deps(chat=AfterPersistBoomStorage())
    await log_node({"session_id": "s1", "user_input": "x", "answer": "y"})   # 不抛即通过
    assert "[wf] after persist fail: read fail" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_resolve_node_rewrites_with_history(monkeypatch):
    import workflow.nodes as nodes_module

    async def fake_resolve(llm, question, history):
        return ("《静夜思》这首诗合不合律", True)

    monkeypatch.setattr(nodes_module, "resolve_input", fake_resolve)
    chat = FakeChatStorage()
    chat.persist_turn("s1", "《静夜思》是谁写的", "李白")
    _deps(chat=chat)
    out = await resolve_node({"session_id": "s1", "user_input": "它合不合律"})
    assert out["resolved_input"] == "《静夜思》这首诗合不合律"
    assert out["query_changed"] is True
    assert out["turn_message_start"] == 0


@pytest.mark.asyncio
async def test_resolve_node_resumes_without_calling_model(monkeypatch):
    import workflow.nodes as nodes_module
    calls = {"n": 0}

    async def fake_resolve(llm, question, history):
        calls["n"] += 1
        return ("不该被调用", True)

    monkeypatch.setattr(nodes_module, "resolve_input", fake_resolve)
    _deps(ScriptedLLM())
    state = {"user_input": "", "selected_poem_id": 7, "pending_subflow": True,
             "resolved_input": "这句合不合律", "subflow_kind": "meter", "messages": []}
    out = await resolve_node(state)
    assert calls["n"] == 0                       # 续跑不重新消解
    assert out["pending_subflow"] is True
    assert out["resolved_input"] == "这句合不合律"  # 沿用上一轮结果(本节点不覆盖)
    assert out.get("messages") is None           # 续跑不追加用户消息


def test_after_resolve_branches():
    assert after_resolve({"pending_subflow": True}) == "slot_check"
    assert after_resolve({"pending_subflow": False}) == "classify"


@pytest.mark.asyncio
async def test_slot_check_node_delegates_to_ruling(monkeypatch):
    import workflow.nodes as nodes_module

    async def fake_resolve_slot(state, deps):
        return {"slot_target": {"poemId": 1}, "pending_subflow": False}

    monkeypatch.setattr(nodes_module.ruling, "resolve_slot", fake_resolve_slot)
    _deps()
    assert await slot_check_node({"resolved_input": "x"}) == {"slot_target": {"poemId": 1}, "pending_subflow": False}


def test_after_slot_check_branches():
    assert after_slot_check({"slot_target": {"poemId": 1}}) == "expand_query"
    assert after_slot_check({"slot_target": None}) == "log"


@pytest.mark.asyncio
async def test_expand_query_node_fills_queries(monkeypatch):
    import workflow.nodes as nodes_module

    async def fake_expand(llm, question):
        return ["七律的句数字数", "律诗对仗要求"]

    monkeypatch.setattr(nodes_module.expand, "expand_queries", fake_expand)
    _deps()
    assert await expand_query_node({"resolved_input": "这首是不是七律"}) == {
        "expanded_queries": ["七律的句数字数", "律诗对仗要求"]
    }


def test_retrieve_policy_node_records_clauses_and_categories(monkeypatch):
    _deps()
    import workflow.nodes as nodes_module
    monkeypatch.setattr(
        nodes_module.expand, "search_multi",
        lambda queries, source_type, topk: [{"id": 3, "score": 0.7, "source_type": source_type, "raw_text": "偶句押韵"}],
    )
    out = retrieve_policy_node({"expanded_queries": ["押韵"], "subflow_kind": "meter", "slot_target": {"title": "静夜思"}})
    assert out["policy_hits"][0]["raw_text"] == "偶句押韵"
    assert out["correction_categories"] == list(CORRECTION_CATEGORIES)


@pytest.mark.asyncio
async def test_log_node_skips_user_row_on_resume():
    chat = FakeChatStorage()
    _deps(chat=chat)
    await log_node({"session_id": "s1", "user_input": "", "answer": "判定结果"})
    _, user_text, _ = chat.turns[0]
    assert user_text == ""      # 续跑轮 user_input 为空,存储层不写 user 行


class AnchoredFakeStorage:
    """可配置锚点/消息的假存储,专门验证降级与摘要触发。"""

    def __init__(self, rows, summary_upto=0, layer1_from=0):
        self.rows = rows
        self.summary_upto = summary_upto
        self.layer1_from = layer1_from
        self.summaries = []
        self.advanced = []

    def persist_turn(self, session_id, user_text, answer, userid=None):
        return 1, 100, 101

    def load_context(self, session_id):
        return {"conversationId": 1, "summaryUpto": self.summary_upto,
                "layer1From": self.layer1_from, "rows": list(self.rows),
                "summaries": list(self.summaries)}

    def advance_layer1_anchor(self, conversation_id, msg_id):
        self.advanced.append(msg_id)
        self.layer1_from = msg_id

    def add_summary(self, conversation_id, content, upto_msg_id):
        self.summaries.append({"seq": len(self.summaries) + 1, "uptoMsgId": upto_msg_id, "content": content})
        self.summary_upto = upto_msg_id
        return len(self.summaries)


@pytest.mark.asyncio
async def test_log_node_downgrades_layer1_when_over_budget(capsys, monkeypatch):
    import workflow.nodes as nodes_module

    monkeypatch.setattr(nodes_module, "schedule_summary", lambda *a, **k: None)
    rows = [
        {"id": 1, "role": "user", "content": "问" * 100},
        {"id": 2, "role": "assistant", "content": "答" * 100},
        {"id": 3, "role": "user", "content": "问" * 100},
        {"id": 4, "role": "assistant", "content": "答" * 100},
    ]
    chat = AnchoredFakeStorage(rows)
    _deps(chat=chat, keep_turns=1, turn_steady_tokens=50)
    await log_node({"session_id": "s1", "user_input": "x", "answer": "y"})
    assert chat.advanced                                  # 至少前移一次
    assert "layer1 降级 0→" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_log_node_skips_summary_when_layer2_within_budget(capsys, monkeypatch):
    import workflow.nodes as nodes_module

    monkeypatch.setattr(nodes_module, "schedule_summary", lambda *a, **k: None)
    rows = [{"id": i, "role": "user" if i % 2 else "assistant", "content": "短"} for i in range(1, 5)]
    chat = AnchoredFakeStorage(rows, summary_upto=0, layer1_from=2)
    _deps(chat=chat)
    await log_node({"session_id": "s1", "user_input": "x", "answer": "y"})
    assert "summary trigger" not in capsys.readouterr().out


@pytest.mark.asyncio
async def test_log_node_triggers_summary_when_layer2_over_budget(capsys, monkeypatch):
    import workflow.nodes as nodes_module

    called = {}

    def fake_schedule(deps, sid, cid, from_id, to_id, layer2_tokens):
        # 真 summary 的触发日志在其内部;此处桩函数镜像同一行,保持"只验证投递"的隔离
        print(f"summary trigger 会话={sid} 层2 约 {layer2_tokens} token > 预算 {deps.budget.layer2}")
        called.update(sid=sid, from_id=from_id, to_id=to_id, tokens=layer2_tokens)

    monkeypatch.setattr(nodes_module, "schedule_summary", fake_schedule)
    rows = [
        {"id": 1, "role": "user", "content": "问" * 300},
        {"id": 2, "role": "assistant", "content": "答" * 300},
    ]
    chat = AnchoredFakeStorage(rows, summary_upto=0, layer1_from=2)
    _deps(chat=chat, keep_turns=1, turn_steady_tokens=50)
    await log_node({"session_id": "s1", "user_input": "x", "answer": "y"})
    out = capsys.readouterr().out
    assert "summary trigger 会话=s1 层2 约" in out and "> 预算" in out
    assert called == {"sid": "s1", "from_id": 0, "to_id": 2, "tokens": called["tokens"]}
    assert called["tokens"] > 0
