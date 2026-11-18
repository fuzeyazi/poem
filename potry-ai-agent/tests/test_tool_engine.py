"""执行引擎:校验拦截、权限门、读重试/写零重试、业务空不重试、格式化与审计。"""
import asyncio

import pytest
from langchain_core.tools import tool

from config import Settings
from tool_system.engine import ToolEngine
from tool_system.spec import ToolInvocation, ToolSpec, schema_of


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
        tool_timeout_seconds=0.05, tool_max_retries=1,
    )
    base.update(over)
    return Settings(**base)


def make_spec(tool_obj, **over):
    data = dict(
        name=tool_obj.name, description=tool_obj.description or "",
        input_schema=schema_of(tool_obj), tool=tool_obj, timeout=0.05,
    )
    data.update(over)
    return ToolSpec(**data)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    import tool_system.engine as engine_module
    monkeypatch.setattr(engine_module, "RETRY_INTERVAL", 0)


@pytest.mark.asyncio
async def test_validation_error_does_not_execute_handler():
    calls = []

    @tool
    async def needs_text(text: str) -> dict:
        """需要文本。"""
        calls.append(text)
        return {"ok": True}

    audit = FakeAudit()
    engine = ToolEngine(make_settings(), audit)
    spec = make_spec(needs_text)
    result = await engine.execute(spec, {}, ToolInvocation(session_id="s1", tool_call_id="c1"))
    assert result["ok"] is False
    assert result["error_type"] == "invalid_arguments"
    assert result["details"]
    assert calls == []
    assert audit.rows[-1]["status"] == "validation_error"
    assert audit.rows[-1]["retry_count"] == 0


@pytest.mark.asyncio
async def test_write_without_approval_is_denied():
    calls = []

    @tool
    async def write_tool(description: str) -> dict:
        """写工具。"""
        calls.append(description)
        return {"ok": True}

    audit = FakeAudit()
    engine = ToolEngine(make_settings(), audit)
    spec = make_spec(write_tool, permission="write", requires_confirmation=True)
    result = await engine.execute(
        spec, {"description": "写一条"}, ToolInvocation(session_id="s1", tool_call_id="c1")
    )
    assert result["error_type"] == "permission_denied"
    assert "取消" in result["message"]
    assert calls == []
    assert audit.rows[-1]["status"] == "permission_denied"


@pytest.mark.asyncio
async def test_write_with_approval_executes_once():
    calls = []

    @tool
    async def write_tool(description: str) -> dict:
        """写工具。"""
        calls.append(description)
        return {"ok": True, "ticket_no": "TK000001"}

    audit = FakeAudit()
    engine = ToolEngine(make_settings(), audit)
    spec = make_spec(write_tool, permission="write")
    result = await engine.execute(
        spec, {"description": "写一条"},
        ToolInvocation(session_id="s1", tool_call_id="c1", approved=True),
    )
    assert result["ok"] is True and result["ticket_no"] == "TK000001"
    assert calls == ["写一条"]


@pytest.mark.asyncio
async def test_read_timeout_retries_and_records_retry_count():
    calls = []

    @tool
    async def slow_read(text: str) -> dict:
        """慢读。"""
        calls.append(text)
        await asyncio.sleep(0.3)
        return {"ok": True}

    audit = FakeAudit()
    engine = ToolEngine(make_settings(), audit)
    spec = make_spec(slow_read)
    result = await engine.execute(spec, {"text": "x"}, ToolInvocation(session_id="s1", tool_call_id="c1"))
    assert result["ok"] is False and result["error_type"] == "timeout"
    assert len(calls) == 2                          # 首次 + 1 次重试
    assert audit.rows[-1]["status"] == "timeout"
    assert audit.rows[-1]["retry_count"] == 1
    assert audit.rows[-1]["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_write_timeout_never_retries():
    calls = []

    @tool
    async def slow_write(description: str) -> dict:
        """慢写。"""
        calls.append(description)
        await asyncio.sleep(0.3)
        return {"ok": True}

    audit = FakeAudit()
    engine = ToolEngine(make_settings(), audit)
    spec = make_spec(slow_write, permission="write")
    result = await engine.execute(
        spec, {"description": "x"},
        ToolInvocation(session_id="s1", tool_call_id="c1", approved=True),
    )
    assert result["error_type"] == "timeout"
    assert len(calls) == 1
    assert audit.rows[-1]["retry_count"] == 0
    assert audit.rows[-1]["status"] == "timeout"


@pytest.mark.asyncio
async def test_business_empty_result_is_not_retried():
    calls = []

    @tool
    async def empty_tool(text: str) -> dict:
        """查不到。"""
        calls.append(text)
        return {"ok": True, "found": False, "message": "未查到"}

    audit = FakeAudit()
    engine = ToolEngine(make_settings(), audit)
    spec = make_spec(empty_tool)
    result = await engine.execute(spec, {"text": "x"}, ToolInvocation(session_id="s1", tool_call_id="c1"))
    assert result == {"ok": True, "found": False, "message": "未查到"}
    assert len(calls) == 1
    assert audit.rows[-1]["status"] == "success"
    assert audit.rows[-1]["retry_count"] == 0


@pytest.mark.asyncio
async def test_non_transient_fault_is_not_retried():
    calls = []

    @tool
    async def boom(text: str) -> dict:
        """坏工具。"""
        calls.append(text)
        raise RuntimeError("boom")

    audit = FakeAudit()
    engine = ToolEngine(make_settings(), audit)
    spec = make_spec(boom)
    result = await engine.execute(spec, {"text": "x"}, ToolInvocation(session_id="s1", tool_call_id="c1"))
    assert result["error_type"] == "fault"
    assert len(calls) == 1
    assert audit.rows[-1]["status"] == "error"
    assert audit.rows[-1]["retry_count"] == 0


@pytest.mark.asyncio
async def test_transient_connection_error_is_retried():
    calls = []

    @tool
    async def flaky(text: str) -> dict:
        """网络抖动。"""
        calls.append(text)
        raise ConnectionError("connection reset by peer")

    audit = FakeAudit()
    engine = ToolEngine(make_settings(), audit)
    spec = make_spec(flaky)
    result = await engine.execute(spec, {"text": "x"}, ToolInvocation(session_id="s1", tool_call_id="c1"))
    assert result["error_type"] == "fault"
    assert len(calls) == 2
    assert audit.rows[-1]["retry_count"] == 1


@pytest.mark.asyncio
async def test_result_fields_and_enum_labels_applied():
    @tool
    async def status_tool(code: str) -> dict:
        """状态。"""
        return {"ok": True, "found": True, "status": "received", "debug": "x"}

    engine = ToolEngine(make_settings(), FakeAudit())
    spec = make_spec(
        status_tool, result_fields=("status",),
        enum_labels={"received": "已受理"},
    )
    result = await engine.execute(spec, {"code": "1"}, ToolInvocation(session_id="s1"))
    assert result == {"ok": True, "found": True, "status": "已受理"}


@pytest.mark.asyncio
async def test_tool_returned_business_error_message_is_preserved():
    @tool
    async def bad_tool(text: str) -> dict:
        """业务失败。"""
        return {"ok": False, "error": "db down"}

    audit = FakeAudit()
    engine = ToolEngine(make_settings(), audit)
    result = await engine.execute(
        make_spec(bad_tool), {"text": "x"}, ToolInvocation(session_id="s1", tool_call_id="c1")
    )
    assert result["ok"] is False
    assert result["message"] == "db down"
    assert result["error_type"] == "fault"
    assert audit.rows[-1]["status"] == "error"
    assert audit.rows[-1]["error"] == "db down"


@pytest.mark.asyncio
async def test_audit_failure_does_not_block_tool_result():
    class BoomAudit:
        async def record(self, **fields):
            raise RuntimeError("audit db down")

    @tool
    async def ok_tool(text: str) -> dict:
        """正常工具。"""
        return {"ok": True, "found": True, "text": text}

    engine = ToolEngine(make_settings(), BoomAudit())
    result = await engine.execute(make_spec(ok_tool), {"text": "x"}, ToolInvocation(session_id="s1"))
    assert result["ok"] is True and result["text"] == "x"
