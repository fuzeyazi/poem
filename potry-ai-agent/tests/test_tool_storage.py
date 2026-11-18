"""Ch07 新表:tickets 与 tool_audit_logs 的列、落行、无外键。"""
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app_storage import AppBase, AppStorage, Ticket, ToolAuditLog


def _storage():
    engine = create_engine("sqlite:///:memory:")
    AppBase.metadata.create_all(engine)
    return AppStorage(sessionmaker(bind=engine)), engine


def test_ticket_columns_match_spec():
    assert {c.name for c in Ticket.__table__.columns} == {
        "id", "ticket_no", "userid", "session_id",
        "ticket_type", "description", "status", "created_at",
    }


def test_add_ticket_returns_auto_number():
    storage, engine = _storage()
    ticket_id, ticket_no = storage.add_ticket(
        "内容纠错", "《静夜思》原文有错字", session_id="s1", userid="u-1"
    )
    assert ticket_no == f"TK{ticket_id:06d}"
    with sessionmaker(bind=engine)() as session:
        row = session.get(Ticket, ticket_id)
    assert row.ticket_no == ticket_no
    assert row.ticket_type == "内容纠错"
    assert row.description == "《静夜思》原文有错字"
    assert row.status == "submitted"
    assert row.session_id == "s1"
    assert row.userid == "u-1"
    assert row.created_at is not None


def test_tool_audit_columns_match_spec():
    assert {c.name for c in ToolAuditLog.__table__.columns} == {
        "id", "session_id", "tool_call_id", "tool_name", "source",
        "arguments", "result_summary", "status", "error",
        "retry_count", "duration_ms", "created_at",
    }


def test_add_tool_audit_appends_row_without_foreign_keys():
    storage, engine = _storage()
    audit_id = storage.add_tool_audit(
        session_id="s1", tool_call_id="c1", tool_name="query_poet",
        source="builtin", arguments='{"name": "李白"}',
        result_summary='{"ok": true}', status="success",
        error=None, retry_count=0, duration_ms=12,
    )
    with sessionmaker(bind=engine)() as session:
        row = session.get(ToolAuditLog, audit_id)
    assert row.tool_name == "query_poet"
    assert row.source == "builtin"
    assert row.arguments == '{"name": "李白"}'
    assert row.status == "success"
    assert row.retry_count == 0
    assert row.duration_ms == 12
    assert row.created_at is not None
    assert inspect(engine).get_foreign_keys("tool_audit_logs") == []
