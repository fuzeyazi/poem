"""建单 interrupt 流:确认落票、取消权限拒绝、确认态不跨轮、should_continue 路由。"""
import asyncio

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app_storage import AppBase, Ticket
from config import Settings
from tool_system.catalog import ToolCatalog
from tool_system.engine import ToolEngine
from workflow.agent_react import should_continue, tool_node
from workflow.deps import WorkflowDeps, configure
from workflow.nodes import ticket_confirm_node
from workflow.state import PER_TURN_RESET, WorkflowState


class FakeAudit:
    def __init__(self):
        self.rows = []

    async def record(self, **fields):
        self.rows.append(fields)


def make_settings(**over):
    base = dict(
        llm_base_url="http://fake", llm_api_key="sk-fake", llm_model="fake",
        history_max_tokens=2000, llm_temperature=0.7,
        mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
        tool_timeout_seconds=1.0, tool_max_retries=0,
    )
    base.update(over)
    return Settings(**base)


def _ticket_call(call_id="tc1", description="《静夜思》原文有错字"):
    return {
        "name": "create_ticket",
        "args": {"ticket_type": "内容纠错", "description": description},
        "id": call_id, "type": "tool_call",
    }


async def _setup(monkeypatch, tmp_path):
    import tools.ticket_tool as ticket_module

    engine = create_engine(f"sqlite:///{tmp_path / 'flow.db'}")
    AppBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(ticket_module, "_storage_factory", lambda: factory)

    audit = FakeAudit()
    settings = make_settings()
    catalog = ToolCatalog(
        engine=ToolEngine(settings, audit), audit=audit,
        plugin_dir=None, mcp_provider=None,
    )
    catalog.register_builtin(ticket_module.create_ticket, permission="write")
    deps = WorkflowDeps(settings, None, catalog, None, None)
    configure(deps)
    await catalog.get_tools()          # 独立小图不经过 agent_node,这里先填充 _merged
    return catalog, audit, factory


def _graph():
    builder = StateGraph(WorkflowState)
    builder.add_node("ticket_confirm", ticket_confirm_node)
    builder.add_node("tool_node", tool_node)
    builder.add_edge(START, "ticket_confirm")
    builder.add_edge("ticket_confirm", "tool_node")
    builder.add_edge("tool_node", END)
    return builder.compile(checkpointer=InMemorySaver())


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    configure(None)


def test_per_turn_reset_clears_ticket_state():
    assert PER_TURN_RESET["ticket_confirmed"] is None
    assert PER_TURN_RESET["ticket_preview"] is None


def _setup_dummy():
    audit = FakeAudit()
    settings = make_settings()
    catalog = ToolCatalog(
        engine=ToolEngine(settings, audit), audit=audit,
        plugin_dir=None, mcp_provider=None,
    )

    from tools.ticket_tool import create_ticket
    catalog.register_builtin(create_ticket, permission="write")
    configure(WorkflowDeps(settings, None, catalog, None, None))
    asyncio.run(catalog.get_tools())
    return catalog, audit, None


def test_should_continue_routes_valid_ticket_to_confirm():
    catalog, _, _ = _setup_dummy()
    state = {"messages": [AIMessage(content="", tool_calls=[_ticket_call()])],
             "iterations": 1, "tokens_used": 10}
    assert should_continue(state) == "ticket_confirm"
    bad = {"messages": [AIMessage(content="", tool_calls=[_ticket_call(description="短")])],
           "iterations": 1, "tokens_used": 10}
    assert should_continue(bad) == "tool_node"


@pytest.mark.asyncio
async def test_confirm_flow_writes_ticket_and_audits_success(monkeypatch, tmp_path):
    catalog, audit, factory = await _setup(monkeypatch, tmp_path)
    graph = _graph()
    config = {"configurable": {"thread_id": "confirm-1"}}
    first = await graph.ainvoke(
        {"session_id": "s1", "userid": "u1",
         "messages": [AIMessage(content="", tool_calls=[_ticket_call()])]},
        config=config,
    )
    assert "__interrupt__" in first
    assert first["__interrupt__"][0].value["action"] == "confirm_ticket"
    assert first["__interrupt__"][0].value["preview"]["ticketType"] == "内容纠错"
    with factory() as session:
        assert session.execute(select(Ticket)).scalars().all() == []

    final = await graph.ainvoke(Command(resume={"confirmed": True}), config=config)
    assert final["ticket_confirmed"] is None
    assert audit.rows[-1]["status"] == "success"
    assert audit.rows[-1]["tool_name"] == "create_ticket"
    with factory() as session:
        tickets = session.execute(select(Ticket)).scalars().all()
    assert len(tickets) == 1
    assert tickets[0].ticket_no == "TK000001"


@pytest.mark.asyncio
async def test_cancel_flow_writes_no_ticket_and_audits_denied(monkeypatch, tmp_path):
    catalog, audit, factory = await _setup(monkeypatch, tmp_path)
    graph = _graph()
    config = {"configurable": {"thread_id": "cancel-1"}}
    await graph.ainvoke(
        {"session_id": "s2", "messages": [AIMessage(content="", tool_calls=[_ticket_call()])]},
        config=config,
    )
    final = await graph.ainvoke(Command(resume={"confirmed": False}), config=config)
    assert final["messages"][-1].content
    assert audit.rows[-1]["status"] == "permission_denied"
    assert audit.rows[-1]["retry_count"] == 0
    with factory() as session:
        assert session.execute(select(Ticket)).scalars().all() == []


@pytest.mark.asyncio
async def test_engine_denies_write_when_confirmation_bypassed():
    audit = FakeAudit()
    settings = make_settings()
    catalog = ToolCatalog(
        engine=ToolEngine(settings, audit), audit=audit,
        plugin_dir=None, mcp_provider=None,
    )
    from tools.ticket_tool import create_ticket
    catalog.register_builtin(create_ticket, permission="write")
    await catalog.get_tools()
    result = await catalog.execute(
        "create_ticket",
        {"ticket_type": "其他", "description": "绕过确认直接执行"},
        session_id="s3", tool_call_id="tc9", approved=False,
    )
    assert result["error_type"] == "permission_denied"
    assert audit.rows[-1]["status"] == "permission_denied"
