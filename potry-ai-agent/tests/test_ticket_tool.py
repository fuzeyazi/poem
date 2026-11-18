"""建单工具:JSON Schema(枚举/必填/最小长度)、上下文落库、返回工单号。"""
import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app_storage import AppBase, Ticket
from tool_system.spec import ToolInvocation, bind_invocation, reset_invocation


def test_ticket_tool_schema_has_enum_and_min_length():
    from tools.ticket_tool import create_ticket
    from tool_system.spec import schema_of

    schema = schema_of(create_ticket)
    props = schema["properties"]
    assert props["ticket_type"]["enum"] == ["内容纠错", "功能异常", "其他"]
    assert props["description"]["minLength"] == 4
    assert set(schema["required"]) == {"ticket_type", "description"}


def test_create_ticket_writes_row_with_invocation_context(monkeypatch, tmp_path):
    import tools.ticket_tool as ticket_module

    engine = create_engine(f"sqlite:///{tmp_path / 'ticket.db'}")
    AppBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(ticket_module, "_storage_factory", lambda: factory)

    token = bind_invocation(ToolInvocation(
        session_id="s-ticket", tool_call_id="c1", userid="u-1",
    ))
    try:
        result = asyncio.run(ticket_module.create_ticket.ainvoke({
            "ticket_type": "内容纠错",
            "description": "《静夜思》原文有错字",
        }))
    finally:
        reset_invocation(token)

    assert result["ok"] is True
    assert result["ticket_no"] == "TK000001"
    with factory() as session:
        row = session.get(Ticket, result["ticket_id"])
    assert row.session_id == "s-ticket"
    assert row.userid == "u-1"
    assert row.ticket_type == "内容纠错"
    assert row.description == "《静夜思》原文有错字"
