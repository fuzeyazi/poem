"""两个 MCP Server 的 mock 工具可直接调用并返回约定结构。"""
from mcp_servers.judgement_server import (
    correction_progress_lookup,
    judgement_status_lookup,
)
from mcp_servers.poetry_archive_server import poem_archive_lookup, poet_archive_lookup


def test_poetry_archive_lookup_returns_archive():
    result = poem_archive_lookup(title="静夜思")
    assert result["ok"] is True and result["found"] is True
    assert result["archive"]["title"] == "静夜思"
    assert result["archive"]["writer"] == "李白"
    assert result["archive"]["archive_status"] in ("在库", "整理中")


def test_poet_archive_lookup_returns_poet():
    result = poet_archive_lookup(name="李白")
    assert result["ok"] is True
    assert result["poet"]["name"] == "李白"
    assert result["poet"]["dynasty"] == "唐"


def test_judgement_status_lookup_returns_record():
    result = judgement_status_lookup(title="春望")
    assert result["ok"] is True
    assert result["judgement"]["title"] == "春望"
    assert result["judgement"]["kind"] in ("meter", "verify")
    assert result["judgement"]["result"] in ("pass", "fail")


def test_correction_progress_lookup_returns_progress():
    result = correction_progress_lookup(ticket_no="TK000001")
    assert result["ok"] is True
    assert result["progress"]["ticket_no"] == "TK000001"
    assert result["progress"]["status"] in ("received", "reviewing", "done")
