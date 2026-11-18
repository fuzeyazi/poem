"""ReAct 子循环:agent 节点收敛 / tool 节点执行回灌 / should_continue 停止判定三条。"""
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from config import Settings
from tool_system.catalog import ToolCatalog
from tool_system.engine import ToolEngine
from workflow.agent_react import agent_node, should_continue, tool_node
from workflow.deps import WorkflowDeps, configure


class ScriptedLLM:
    """按脚本吐 AIMessage;脚本取空后返回固定收敛文本。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.last_messages = []

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages, config=None):
        self.calls += 1
        self.last_messages = list(messages)
        if self.script:
            return self.script.pop(0)
        return AIMessage(content="兜底收敛")


def make_settings(**over):
    base = dict(
        llm_base_url="http://fake", llm_api_key="sk-fake", llm_model="fake",
        history_max_tokens=2000, llm_temperature=0.7,
        mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
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
    def query_poem(keyword: str) -> dict:
        """查诗词。

        Args:
            keyword: 关键词
        """
        calls.append(keyword)
        return {"ok": True, "found": True, "poem": {"title": "静夜思"}}

    settings = make_settings()
    audit = FakeAudit()
    catalog = ToolCatalog(
        engine=ToolEngine(settings, audit), audit=audit,
        plugin_dir=None, mcp_provider=None,
    )
    catalog.register_builtin(query_poem)
    return catalog, calls


def _deps(llm, catalog, **over):
    deps = WorkflowDeps(make_settings(**over), llm, catalog, None, None)
    configure(deps)
    return deps


def _tc(call_id="c1"):
    return {"name": "query_poem", "args": {"keyword": "静夜思"}, "id": call_id, "type": "tool_call"}


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    configure(None)


@pytest.mark.asyncio
async def test_agent_converges_in_one_iteration_without_tools():
    catalog, calls = make_catalog()
    llm = ScriptedLLM([AIMessage(content="《静夜思》写的是思乡")])
    _deps(llm, catalog)
    out = await agent_node({"user_input": "《静夜思》表达了什么", "messages": [], "iterations": 0})
    assert out["answer"] == "《静夜思》写的是思乡"
    assert out["iterations"] == 1
    assert len(out["messages"]) == 1                # 只回吐本轮 AI,seed 不再进 state
    assert isinstance(out["messages"][0], AIMessage)
    assert isinstance(llm.last_messages[0], SystemMessage)
    assert llm.last_messages[-1].content == "《静夜思》表达了什么"
    assert calls == []


@pytest.mark.asyncio
async def test_agent_keeps_seed_when_retrieved_present():
    catalog, _ = make_catalog()
    llm = ScriptedLLM([AIMessage(content="答")])
    _deps(llm, catalog)
    state = {
        "resolved_input": "这首诗什么意思", "messages": [], "iterations": 0,
        "retrieved": [{"source_type": "poem", "title": "静夜思", "text": "床前明月光", "score": 0.9, "id": 1}],
    }
    await agent_node(state)
    combined = llm.last_messages[-1]
    assert "床前明月光" in combined.content and "【检索资料】" in combined.content


@pytest.mark.asyncio
async def test_agent_emits_tool_calls_without_answer():
    catalog, _ = make_catalog()
    _deps(ScriptedLLM([AIMessage(content="", tool_calls=[_tc()])]), catalog)
    out = await agent_node({"resolved_input": "查静夜思", "messages": [], "iterations": 0})
    assert "answer" not in out          # 有 tool_calls 时不收敛
    assert out["messages"][-1].tool_calls


@pytest.mark.asyncio
async def test_agent_resume_turn_keeps_tool_call_and_tool_message():
    """续跑轮 start 指向上一轮 assistant 时,不应把 AI(tool_calls) 切掉只剩孤立 ToolMessage。"""
    catalog, _ = make_catalog()
    llm = ScriptedLLM([AIMessage(content="续跑结论")])
    _deps(llm, catalog)
    state = {
        "user_input": "", "turn_message_start": 1, "iterations": 1,
        "messages": [
            HumanMessage(content="上一轮"),
            AIMessage(content="", tool_calls=[_tc()]),
            ToolMessage(content="{}", tool_call_id="c1"),
        ],
    }
    await agent_node(state)
    tool_call_idx = [
        i for i, m in enumerate(llm.last_messages) if getattr(m, "tool_calls", None)
    ]
    assert tool_call_idx, "续跑轮必须保留 AI(tool_calls)"
    assert isinstance(llm.last_messages[tool_call_idx[0] + 1], ToolMessage)


@pytest.mark.asyncio
async def test_tool_node_executes_and_records_trace():
    catalog, calls = make_catalog()
    _deps(ScriptedLLM([]), catalog)
    out = await tool_node({"messages": [AIMessage(content="", tool_calls=[_tc()])]})
    assert calls == ["静夜思"]
    assert isinstance(out["messages"][0], ToolMessage)
    assert out["tool_trace"][0]["tool"] == "query_poem"
    assert out["tool_trace"][0]["status"] == "done"


def test_should_continue_routes_two_ways():
    catalog, _ = make_catalog()
    _deps(ScriptedLLM([]), catalog)
    with_tools = {"messages": [AIMessage(content="", tool_calls=[_tc()])], "iterations": 1, "tokens_used": 10}
    assert should_continue(with_tools) == "tool_node"
    assert should_continue({"messages": [AIMessage(content="答")], "iterations": 1}) == "log"
    assert should_continue({}) == "log"


def test_should_continue_stops_at_iteration_limit():
    catalog, _ = make_catalog()
    _deps(ScriptedLLM([]), catalog, max_agent_steps=2)
    state = {"messages": [AIMessage(content="", tool_calls=[_tc()])], "iterations": 2}
    assert should_continue(state) == "log"


def test_should_continue_stops_at_token_limit():
    catalog, _ = make_catalog()
    _deps(ScriptedLLM([]), catalog, workflow_max_tokens=100)
    state = {"messages": [AIMessage(content="", tool_calls=[_tc()])], "iterations": 1, "tokens_used": 100}
    assert should_continue(state) == "log"


@pytest.mark.asyncio
async def test_agent_force_converges_at_iteration_limit():
    catalog, _ = make_catalog()
    _deps(ScriptedLLM([AIMessage(content="", tool_calls=[_tc()]), AIMessage(content="强制作答")]), catalog, max_agent_steps=1)
    out = await agent_node({"resolved_input": "hi", "messages": [], "iterations": 0})
    assert out["iterations"] == 1
    assert out["fallback_reason"] == "max_iter"
    assert out["answer"] == "强制作答"
    assert out["messages"] == []


@pytest.mark.asyncio
async def test_agent_degrades_when_model_fails():
    catalog, _ = make_catalog()

    class BoomLLM(ScriptedLLM):
        async def ainvoke(self, messages, config=None):
            raise ConnectionError("upstream down")

    _deps(BoomLLM([]), catalog)
    out = await agent_node({"resolved_input": "hi", "messages": [], "iterations": 0})
    assert out["fallback_reason"] == "agent_error"
    assert out["messages"] == []
    assert out["answer"]   # 有兜底话术,不是空


@pytest.mark.asyncio
async def test_agent_force_converges_at_token_limit():
    catalog, _ = make_catalog()
    _deps(
        ScriptedLLM([AIMessage(content="", tool_calls=[_tc()]), AIMessage(content="强制作答")]),
        catalog,
        workflow_max_tokens=1,
    )
    out = await agent_node({"resolved_input": "hi", "messages": [], "iterations": 0})
    assert out["fallback_reason"] == "max_tokens"
    assert out["answer"] == "强制作答"
    assert not any(getattr(m, "tool_calls", None) for m in out["messages"])


@pytest.mark.asyncio
async def test_tool_node_marks_error_status_on_tool_failure():
    settings = make_settings()
    audit = FakeAudit()
    catalog = ToolCatalog(
        engine=ToolEngine(settings, audit), audit=audit,
        plugin_dir=None, mcp_provider=None,
    )

    @tool
    def boom_tool(keyword: str) -> dict:
        """坏工具。

        Args:
            keyword: 关键词
        """
        raise RuntimeError("boom")

    catalog.register_builtin(boom_tool)
    _deps(ScriptedLLM([]), catalog)
    out = await tool_node(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "boom_tool", "args": {"keyword": "x"}, "id": "c9", "type": "tool_call"}
                    ],
                )
            ]
        }
    )
    assert out["tool_trace"][0]["status"] == "error"
    assert isinstance(out["messages"][0], ToolMessage)
