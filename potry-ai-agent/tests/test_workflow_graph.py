"""图装配:可编译、节点齐备、四种出口各走对分支、ReAct 循环 > 1 轮、checkpointer 落盘。"""
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from config import Settings
from prompts import CHITCHAT_REPLY, COMPLAINT_REPLY, FALLBACK_REPLY, SLOT_PROMPT_REPLY
from tool_system.catalog import ToolCatalog
from tool_system.engine import ToolEngine
from workflow import intent
from workflow.deps import WorkflowDeps, configure
from workflow.graph import build_graph, open_checkpointer


class ScriptedLLM:
    """按脚本吐 AIMessage;取空后返回固定收敛文本。记录每次调用的输入消息。"""

    def __init__(self, script=None, default="默认收敛"):
        self.script = list(script or [])
        self.default = default
        self.calls = []                     # 每次 ainvoke 收到的消息

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages, config=None):
        self.calls.append(list(messages))
        if self.script:
            return self.script.pop(0)
        return AIMessage(content=self.default)


class FakeKnowledgeStorage:
    def __init__(self, chunks=None):
        self.chunks = chunks or {}
        self.pending = []

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
        self.summary_upto = 0
        self.layer1_from = 0

    def persist_turn(self, session_id, user_text, answer, userid=None):
        self.turns.append((session_id, user_text, answer))
        user_id = None
        if (user_text or "").strip():
            self._id += 1
            user_id = self._id
            self.rows.append({"id": user_id, "role": "user", "content": user_text})
        self._id += 1
        self.rows.append({"id": self._id, "role": "assistant", "content": answer})
        return 1, user_id, self._id

    def load_context(self, session_id):
        return {"conversationId": 1, "summaryUpto": self.summary_upto,
                "layer1From": self.layer1_from, "rows": list(self.rows), "summaries": []}

    def advance_layer1_anchor(self, conversation_id, msg_id):
        self.layer1_from = msg_id

    def add_summary(self, conversation_id, content, upto_msg_id):
        return None


def make_settings(**over):
    base = dict(
        llm_base_url="http://fake", llm_api_key="sk-fake", llm_model="fake",
        history_max_tokens=2000, llm_temperature=0.7,
        mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
        similarity_threshold=0.5,
        evidence_min_score=0.3, evidence_confidence_threshold=0.5,
    )
    base.update(over)
    return Settings(**base)


class FakeAudit:
    def __init__(self):
        self.rows = []

    async def record(self, **fields):
        self.rows.append(fields)


def make_catalog():
    calls = []

    @tool
    def query_poet(name: str) -> dict:
        """查诗人。

        Args:
            name: 诗人名
        """
        calls.append(name)
        return {"ok": True, "found": True, "poet": {"name": "李白"}}

    settings = make_settings()
    audit = FakeAudit()
    catalog = ToolCatalog(
        engine=ToolEngine(settings, audit), audit=audit,
        plugin_dir=None, mcp_provider=None,
    )
    catalog.register_builtin(query_poet)
    return catalog, calls


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    configure(None)


def _wire(llm, catalog, knowledge=None, chat=None, **over):
    deps = WorkflowDeps(make_settings(**over), llm, catalog, knowledge, chat)
    configure(deps)
    return deps


async def _run(graph, message, session_id="s1", **extra):
    return await graph.ainvoke(
        {"session_id": session_id, "user_input": message, "started_at": 0.0,
         "messages": [], "tool_trace": [], **extra},
        config={"configurable": {"thread_id": session_id}},
    )


def test_graph_builds_and_has_all_nodes():
    catalog, _ = make_catalog()
    _wire(ScriptedLLM(), catalog)
    graph = build_graph(InMemorySaver())
    nodes = set(graph.get_graph().nodes)
    assert {"resolve", "classify", "route", "retrieve", "gate", "agent", "tool_node", "log",
            "slot_check", "expand_query", "retrieve_policy"} <= nodes


@pytest.mark.asyncio
async def test_chitchat_outlet_uses_preset_reply_and_no_tools():
    catalog, calls = make_catalog()
    _wire(ScriptedLLM([AIMessage(content='{"intent": "chitchat"}')]), catalog, chat=FakeChatStorage())
    graph = build_graph(InMemorySaver())
    final = await _run(graph, "今天天气不错")
    assert final["route"] == intent.ROUTE_CHITCHAT
    assert final["answer"] == CHITCHAT_REPLY
    assert final.get("tool_trace", []) == []
    assert final.get("iterations", 0) == 0     # 未进 Agent
    assert calls == []


@pytest.mark.asyncio
async def test_complaint_outlet_carries_two_actions_and_skips_agent():
    catalog, _ = make_catalog()
    _wire(ScriptedLLM([AIMessage(content='{"intent": "complaint"}')]), catalog, chat=FakeChatStorage())
    final = await _run(build_graph(InMemorySaver()), "答得不对,我不满意")
    assert final["route"] == intent.ROUTE_COMPLAINT
    assert final["answer"] == COMPLAINT_REPLY
    assert final["actions"] == ["handoff", "feedback"]
    assert final.get("iterations", 0) == 0


@pytest.mark.asyncio
async def test_business_outlet_agent_calls_tool():
    catalog, calls = make_catalog()
    llm = ScriptedLLM([
        AIMessage(content='{"intent": "find_poet"}'),
        AIMessage(content="", tool_calls=[{"name": "query_poet", "args": {"name": "李白"}, "id": "c1", "type": "tool_call"}]),
        AIMessage(content="李白是唐代诗人"),
    ])
    _wire(llm, catalog, chat=FakeChatStorage())
    final = await _run(build_graph(InMemorySaver()), "李白是什么朝代的")
    assert final["route"] == intent.ROUTE_BUSINESS
    assert calls == ["李白"]                                  # Agent 自主调工具
    assert final["iterations"] == 2                           # ReAct 迭代 > 1 轮
    assert final["answer"] == "李白是唐代诗人"
    assert final["tool_trace"][0]["tool"] == "query_poet"


@pytest.mark.asyncio
async def test_knowledge_outlet_retrieves_then_agent(monkeypatch):
    catalog, _ = make_catalog()
    knowledge = FakeKnowledgeStorage(chunks={1: {"id": 1, "raw_text": "床前明月光"}})
    _wire(ScriptedLLM([AIMessage(content='{"intent": "poem_explain"}'), AIMessage(content="写的是思乡")]),
          catalog, knowledge=knowledge, chat=FakeChatStorage())

    import workflow.nodes as nodes_module
    monkeypatch.setattr(
        nodes_module, "retrieve_evidence",
        lambda question, settings: ([{"id": 1, "score": 0.9, "source_type": "poem", "title": "静夜思"}], 0.9),
    )
    final = await _run(build_graph(InMemorySaver()), "《静夜思》表达了什么感情")
    assert final["route"] == intent.ROUTE_KNOWLEDGE
    assert final["gate_status"] == "pass"
    assert final["evidence_score"] == 0.9
    assert final["answer"] == "写的是思乡"
    assert final["retrieved"][0]["text"] == "床前明月光"


@pytest.mark.asyncio
async def test_knowledge_gate_blocks_agent_when_evidence_insufficient(monkeypatch):
    catalog, calls = make_catalog()
    knowledge = FakeKnowledgeStorage()
    _wire(ScriptedLLM([AIMessage(content='{"intent": "poem_explain"}')]), catalog,
          knowledge=knowledge, chat=FakeChatStorage())

    import workflow.nodes as nodes_module
    monkeypatch.setattr(
        nodes_module, "retrieve_evidence",
        lambda question, settings: ([{"id": 9, "score": 0.1, "source_type": "poem"}], 0.1),
    )
    final = await _run(build_graph(InMemorySaver()), "这句出自哪首冷门诗")
    assert final["gate_status"] == "insufficient"
    assert final["answer"] == FALLBACK_REPLY
    assert final["fallback_reason"] == "insufficient_evidence"
    assert final.get("iterations", 0) == 0                      # 未进 Agent
    assert knowledge.pending == [("这句出自哪首冷门诗", "s1")]   # 已记录待处理


@pytest.mark.asyncio
async def test_checkpointer_persists_state_across_turns():
    """同 thread_id 二轮调用:首轮状态仍在 checkpointer 里(持久化生效)。"""
    catalog, _ = make_catalog()
    _wire(ScriptedLLM([
        AIMessage(content='{"intent": "chitchat"}'),                              # 首轮:分类
        AIMessage(content='{"query": "第二轮", "changed": false}'),                 # 次轮:消解
        AIMessage(content='{"intent": "chitchat"}'),                              # 次轮:分类
    ]), catalog, chat=FakeChatStorage())
    saver, conn = await open_checkpointer(":memory:")
    try:
        graph = build_graph(saver)
        await _run(graph, "第一轮", session_id="thread-x")
        await _run(graph, "第二轮", session_id="thread-x")
        state = await graph.aget_state(config={"configurable": {"thread_id": "thread-x"}})
        assert state.values["user_input"] == "第二轮"
        assert state.values["route"] == intent.ROUTE_CHITCHAT
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_second_turn_does_not_leak_previous_turn_state():
    """实测缺陷回归:投诉轮之后,同一 session 的普通问题不得再带出 actions/证据/gate 等上一轮字段。"""
    catalog, _ = make_catalog()
    llm = ScriptedLLM([
        AIMessage(content='{"intent": "complaint"}'),                        # 首轮:分类
        AIMessage(content='{"query": "李白是什么朝代的", "changed": false}'),   # 次轮:消解
        AIMessage(content='{"intent": "find_poet"}'),                        # 次轮:分类
        AIMessage(content="李白是唐代诗人"),                                    # 次轮:Agent 收敛
    ])
    _wire(llm, catalog, chat=FakeChatStorage())
    graph = build_graph(InMemorySaver())

    turn1 = await _run(graph, "我要投诉", session_id="leak")
    assert turn1["actions"] == ["handoff", "feedback"]

    turn2 = await _run(graph, "李白是什么朝代的", session_id="leak")
    assert turn2["route"] == intent.ROUTE_BUSINESS
    assert turn2["actions"] == []                       # 关键:不得泄漏
    assert turn2["gate_status"] == "skip"
    assert turn2.get("tool_trace", []) == []
    assert turn2.get("evidence_score") is None
    assert turn2.get("retrieved") == []
    assert turn2.get("fallback_reason") == ""


@pytest.mark.asyncio
async def test_knowledge_evidence_injected_on_second_turn(monkeypatch):
    """实测缺陷回归:同一 session 的第二轮知识类问题,检索片段仍要注入 Agent 的 prompt。

    首轮刻意走**业务类**(经 Agent 收敛),使 `messages` 通道非空 —— 旧代码
    `seed = [] if prev else _seed_messages(state)` 在该场景下会漏掉第二轮的证据注入,
    故本用例在旧实现下必红、新实现下转绿。
    """
    from langchain_core.messages import HumanMessage

    catalog, _ = make_catalog()
    knowledge = FakeKnowledgeStorage(chunks={1: {"id": 1, "raw_text": "床前明月光"}})
    llm = ScriptedLLM([
        AIMessage(content='{"intent": "find_poet"}'),        # 首轮意图:业务类
        AIMessage(content="李白是唐代诗人"),                  # 首轮 Agent 收敛
        AIMessage(content='{"query": "《静夜思》表达了什么感情", "changed": false}'),  # 次轮:消解
        AIMessage(content='{"intent": "poem_explain"}'),     # 次轮意图:知识类
        AIMessage(content="写的是思乡"),                      # 次轮 Agent 收敛
    ])
    _wire(llm, catalog, knowledge=knowledge, chat=FakeChatStorage())

    import workflow.nodes as nodes_module
    monkeypatch.setattr(
        nodes_module, "retrieve_evidence",
        lambda question, settings: ([{"id": 1, "score": 0.9, "source_type": "poem", "title": "静夜思"}], 0.9),
    )
    graph = build_graph(InMemorySaver())

    turn1 = await _run(graph, "李白是什么朝代的", session_id="rag2")
    assert turn1["route"] == intent.ROUTE_BUSINESS
    assert turn1["messages"], "首轮应经 Agent,使 messages 通道非空"

    final = await _run(graph, "《静夜思》表达了什么感情", session_id="rag2")
    assert final["gate_status"] == "pass"
    injected = [
        m for m in llm.calls[-1]
        if isinstance(m, HumanMessage) and "床前明月光" in m.content
    ]
    assert injected, "第二轮知识类必须把检索片段注入模型输入"


@pytest.mark.asyncio
async def test_other_outlet_goes_to_agent_for_clarification():
    catalog, _ = make_catalog()
    llm = ScriptedLLM([AIMessage(content='{"intent": "other", "confidence": 0.3}'), AIMessage(content="想聊什么?我陪你读诗。")])
    _wire(llm, catalog, chat=FakeChatStorage())
    final = await _run(build_graph(InMemorySaver()), "帮我写个 Java 排序")
    assert final["route"] == intent.ROUTE_OTHER
    assert final["iterations"] == 1
    assert final["answer"] == "想聊什么?我陪你读诗。"


@pytest.mark.asyncio
async def test_ruling_outlet_asks_cards_when_slot_missing(monkeypatch):
    """缺槽位:不发 token、判定子流程收尾在下发卡片处。"""
    catalog, _ = make_catalog()
    _wire(ScriptedLLM([AIMessage(content='{"intent": "poem_meter", "confidence": 0.8}'),
                       AIMessage(content='{"title": null}')]),
          catalog, knowledge=FakeKnowledgeStorage(chunks={1: {"source_id": 11, "title": "静夜思",
                                                               "writer": "李白", "dynasty": "唐"}}),
          chat=FakeChatStorage())

    import workflow.ruling as ruling
    monkeypatch.setattr(ruling.expand, "search_multi",
                        lambda queries, source_type, topk: [{"id": 1, "score": 0.9, "source_type": source_type}])
    final = await _run(build_graph(InMemorySaver()), "这句合不合律", session_id="slot1")
    assert final["route"] == intent.ROUTE_RULING
    assert final["subflow_kind"] == "meter"
    assert final["pending_subflow"] is True
    assert final["answer"] == SLOT_PROMPT_REPLY
    assert final["candidates"][0]["poemId"] == 11
    assert final.get("iterations", 0) == 0        # 未进 Agent


@pytest.mark.asyncio
async def test_ruling_resume_after_card_pick_judges(monkeypatch):
    """两段式续跑:第一段缺槽位下发卡片;第二段带 selectedPoemId → 跳过分类/消解,直接判定。"""
    catalog, _ = make_catalog()
    llm = ScriptedLLM([
        AIMessage(content='{"intent": "poem_meter", "confidence": 0.8}'),            # 第一段:分类
        AIMessage(content='{"queries": ["七律句数字数", "律诗对仗"]}'),                  # 第二段:扩写
        AIMessage(content="这首是七律,八句七字,中间两联对仗。"),                        # 第二段:Agent 判定
    ])
    _wire(llm, catalog, chat=FakeChatStorage())

    import workflow.nodes as nodes_module
    import workflow.ruling as ruling

    async def fake_resolve_slot(state, deps):
        # 无 selectedPoemId → 缺槽位等回填;有 selectedPoemId → 取到对象继续
        if state.get("selected_poem_id"):
            return {"slot_target": {"poemId": 11, "title": "静夜思", "content": "床前明月光"},
                    "pending_subflow": False}
        return {"candidates": [{"poemId": 11, "title": "静夜思"}], "pending_subflow": True,
                "slot_target": None, "answer": SLOT_PROMPT_REPLY}

    monkeypatch.setattr(nodes_module.ruling, "resolve_slot", fake_resolve_slot)
    monkeypatch.setattr(ruling.expand, "search_multi",
                        lambda queries, source_type, topk: [{"id": 5, "score": 0.8,
                                                             "source_type": source_type,
                                                             "raw_text": "七言律诗八句每句七字。"}])
    graph = build_graph(InMemorySaver())
    # 第一段:缺槽位,建立等待态(只用了 1 次 LLM 调用:分类)
    turn1 = await _run(graph, "这句合不合律", session_id="resume1")
    assert turn1["pending_subflow"] is True and turn1["subflow_kind"] == "meter"
    # 第二段:点选卡片续跑(message 空 + selectedPoemId;续跑不重新消解,故不额外调模型)
    final = await _run(graph, "", session_id="resume1", selected_poem_id=11)
    assert final["slot_target"]["poemId"] == 11
    assert final["policy_hits"][0]["raw_text"] == "七言律诗八句每句七字。"
    assert final["correction_categories"]                  # 判定完成 → 总是挂纠错单入口
    injected = [m for m in llm.calls[-1]
                if isinstance(m, HumanMessage) and "床前明月光" in m.content]
    assert injected, "判定子流程必须把诗作权威数据注入模型输入"
