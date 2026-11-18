from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from config import Settings
from context_budget import derive_budget, estimate_tokens
from context_builder import build_agent_context, build_history_context, compose_summary_text


def make_settings(**over):
    base = dict(
        llm_base_url="http://fake", llm_api_key="sk-fake", llm_model="fake",
        history_max_tokens=2000, llm_temperature=0.7,
        mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
    )
    base.update(over)
    return Settings(**base)


class FakeStorage:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def load_context(self, session_id):
        return self.snapshot


class FakeDeps:
    def __init__(self, snapshot, settings=None):
        self.chat_storage = FakeStorage(snapshot)
        self.settings = settings or make_settings()
        self.budget = derive_budget(self.settings)


SNAPSHOT = {
    "conversationId": 1, "summaryUpto": 2, "layer1From": 4,
    "rows": [
        {"id": 1, "role": "user", "content": "问一"},
        {"id": 2, "role": "assistant", "content": "答一"},
        {"id": 3, "role": "user", "content": "问二"},
        {"id": 4, "role": "assistant", "content": "答二"},
        {"id": 5, "role": "user", "content": "问三"},
        {"id": 6, "role": "assistant", "content": "答三"},
    ],
    "summaries": [{"seq": 1, "uptoMsgId": 2, "content": "早期梗概正文"}],
}


def test_agent_context_order_and_no_summary_system():
    deps = FakeDeps(SNAPSHOT)
    state = {
        "session_id": "s1", "user_input": "问四", "turn_message_start": 0,
        "messages": [HumanMessage(content="问四")],
        "retrieved": [{"source_type": "poem", "title": "静夜思", "text": "床前明月光"}],
    }
    ctx = build_agent_context(state, deps)
    roles = [type(m).__name__ for m in ctx.messages]
    assert roles[0] == "SystemMessage" and roles.count("SystemMessage") == 1
    assert isinstance(ctx.messages[1], HumanMessage) and ctx.messages[1].content == "问二"
    assert isinstance(ctx.messages[2], AIMessage) and ctx.messages[2].content.startswith("答二")
    assert ctx.messages[3].content == "问三"
    assert ctx.messages[4].content == "答三"
    assert ctx.messages[5].content == "问四"                    # 当前句
    combined = ctx.messages[6]
    assert "【早期梗概" in combined.content and "【检索资料】" in combined.content
    assert "第1段最早" in combined.content
    assert "床前明月光" in combined.content
    assert ctx.summary == "早期梗概正文"


def test_agent_context_ruling_evidence_is_one_message_after_question():
    deps = FakeDeps({**SNAPSHOT, "summaryUpto": 0, "summaries": []})
    state = {
        "session_id": "s1", "user_input": "这首合律吗", "turn_message_start": 0,
        "messages": [HumanMessage(content="这首合律吗")],
        "subflow_kind": "meter",
        "slot_target": {"title": "静夜思", "writer": "李白", "content": "床前明月光"},
        "policy_hits": [{"raw_text": "偶句押韵"}],
    }
    ctx = build_agent_context(state, deps)
    combined = ctx.messages[-1]
    assert isinstance(combined, HumanMessage)
    assert "【待判定的诗作" in combined.content and "偶句押韵" in combined.content
    assert combined.content.index("【待判定的诗作") < combined.content.index("【任务】")


def test_agent_context_appends_this_turn_react_messages():
    deps = FakeDeps({**SNAPSHOT, "rows": [], "summaryUpto": 0, "layer1From": 0, "summaries": []})
    state = {
        "session_id": "s1", "user_input": "问", "turn_message_start": 0,
        "messages": [HumanMessage(content="问"), AIMessage(content="", tool_calls=[{"id": "c1", "name": "x", "args": {}}])],
    }
    ctx = build_agent_context(state, deps)
    assert isinstance(ctx.messages[-1], AIMessage) and ctx.messages[-1].tool_calls


def test_agent_context_resume_keeps_tool_call_and_tool_message():
    deps = FakeDeps({**SNAPSHOT, "rows": [], "summaryUpto": 0, "layer1From": 0, "summaries": []})
    state = {
        "session_id": "s1", "user_input": "", "turn_message_start": 1,
        "messages": [
            HumanMessage(content="上一轮"),
            AIMessage(content="", tool_calls=[{"id": "c1", "name": "x", "args": {}}]),
            ToolMessage(content="{}", tool_call_id="c1"),
        ],
    }
    ctx = build_agent_context(state, deps)
    assert isinstance(ctx.messages[-2], AIMessage) and ctx.messages[-2].tool_calls
    assert isinstance(ctx.messages[-1], ToolMessage)


def test_agent_context_surfaces_earliest_fact_for_recall_questions():
    snapshot = {
        **SNAPSHOT,
        "summaries": [
            {"seq": 1, "uptoMsgId": 2, "content": "用户依次问《静夜思》作者。之后又问李白朝代。"},
        ],
    }
    ctx = build_agent_context(
        {"session_id": "s1", "user_input": "最开始问的那首诗后来怎么说", "messages": []},
        FakeDeps(snapshot),
    )
    combined = ctx.messages[-1].content
    assert combined.startswith("【最早事实(摘自第1段梗概)】")
    assert "静夜思" in combined.splitlines()[0]


def test_agent_context_skips_earliest_hint_for_normal_questions():
    snapshot = {
        **SNAPSHOT,
        "summaries": [{"seq": 1, "uptoMsgId": 2, "content": "用户依次问《静夜思》作者。"}],
    }
    ctx = build_agent_context(
        {"session_id": "s1", "user_input": "《春望》是不是五律", "messages": []},
        FakeDeps(snapshot),
    )
    assert "【最早事实" not in ctx.messages[-1].content


def test_history_context_is_summary_line_plus_window():
    deps = FakeDeps(SNAPSHOT)
    hc = build_history_context(SNAPSHOT, deps.settings)
    llm_rows = hc.for_llm()
    assert llm_rows[0] == {"role": "summary", "content": "早期梗概正文"}
    assert [r["role"] for r in llm_rows[1:]] == ["user", "assistant", "user", "assistant"]
    assert hc.tokens > 0


def test_history_context_trimmed_to_budget_keeps_latest_turn():
    snapshot = {"conversationId": 1, "summaryUpto": 0, "layer1From": 0,
                "rows": [
                    {"id": 1, "role": "user", "content": "旧" * 100},
                    {"id": 2, "role": "assistant", "content": "旧答" * 100},
                    {"id": 3, "role": "user", "content": "新问"},
                    {"id": 4, "role": "assistant", "content": "新答"},
                ], "summaries": []}
    settings = make_settings(history_ctx_max_tokens=30)
    hc = build_history_context(snapshot, settings)
    assert [r["id"] for r in hc.layer2 + hc.layer1] == [3, 4]


def _five_summary_snapshot():
    return {
        "conversationId": 1, "summaryUpto": 0, "layer1From": 0, "rows": [],
        "summaries": [
            {"seq": i, "content": f"第{i}段" + "早" * 96}   # 每段约 60 token
            for i in range(1, 6)
        ],
    }


def test_compose_summary_keeps_first_and_newest_within_budget():
    snapshot = _five_summary_snapshot()
    out = compose_summary_text(snapshot, 150)
    assert "第1段" in out and "第5段" in out             # 最早事实必在,最新段也在
    assert "第2段" not in out and "第3段" not in out and "第4段" not in out
    assert out.index("第1段") < out.index("第5段")        # 仍按 seq 排序
    assert "…(中间梗概已省略)…" in out                    # 丢弃中间段时插入省略标记
    assert out.index("第1段") < out.index("…(中间梗概已省略)…") < out.index("第5段")
    assert estimate_tokens(out) <= 150
    # 预算充足时全量拼接
    assert compose_summary_text(snapshot, 10_000) == "\n".join(
        f"第{i}段" + "早" * 96 for i in range(1, 6)
    )


def test_summary_composition_uses_reserve_budget_in_both_builders():
    snapshot = _five_summary_snapshot()
    settings = make_settings(summary_reserve_tokens=150)
    hc = build_history_context(snapshot, settings)
    ctx = build_agent_context({"session_id": "s1", "user_input": "问"}, FakeDeps(snapshot, settings))
    for summary in (hc.summary, ctx.summary):
        assert "第1段" in summary and "第5段" in summary
        assert "第2段" not in summary and "第3段" not in summary and "第4段" not in summary
