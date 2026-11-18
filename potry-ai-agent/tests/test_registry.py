import asyncio

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool

from tools import registry as reg_mod
from tools.registry import ToolRegistry


def make_registry():
    return ToolRegistry(timeout=5.0, max_retries=1)


def test_register_and_get_tools():
    reg = make_registry()

    @tool
    def demo(x: int) -> str:
        """演示工具。

        Args:
            x: 数字
        """
        return str(x)

    reg.register(demo)
    assert reg.get_tools() == [demo]


@pytest.mark.asyncio
async def test_unknown_tool_returns_structured_error():
    reg = make_registry()
    assert await reg.execute("nope", {}) == {"ok": False, "error": "unknown tool: nope"}


@pytest.mark.asyncio
async def test_invalid_args_returned_as_structured_error():
    reg = make_registry()

    @tool
    def need_int(x: int) -> str:
        """需要整数。

        Args:
            x: 数字
        """
        return str(x)

    reg.register(need_int)
    result = await reg.execute("need_int", {"x": "not-a-number"})
    assert result["ok"] is False
    assert "invalid arguments" in result["error"]
    # 成功路径不受影响
    assert await reg.execute("need_int", {"x": 3}) == {"ok": True, "found": True, "data": "3"}


@pytest.mark.asyncio
async def test_exception_wrapped_and_retried(monkeypatch):
    monkeypatch.setattr(reg_mod, "RETRY_INTERVAL", 0)  # 免等待
    reg = make_registry()
    calls = {"n": 0}

    @tool
    def flaky() -> str:
        """总会抛异常的工具。"""
        calls["n"] += 1
        raise ValueError("boom")

    reg.register(flaky)
    result = await reg.execute("flaky", {})
    assert result["ok"] is False
    assert "boom" in result["error"]
    assert calls["n"] == 2  # 首次 + 重试 1 次


@pytest.mark.asyncio
async def test_timeout_retried_then_wrapped(monkeypatch):
    monkeypatch.setattr(reg_mod, "RETRY_INTERVAL", 0)
    reg = make_registry()
    calls = {"n": 0}

    @tool
    def slow() -> str:
        """慢工具(直接抛超时模拟)。"""
        calls["n"] += 1
        raise asyncio.TimeoutError()

    reg.register(slow)
    result = await reg.execute("slow", {})
    assert result == {"ok": False, "error": "timeout"}
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_register_stashes_time_limit_attrs():
    reg = make_registry()

    @tool
    def slow() -> str:
        """慢工具。"""
        return "done"

    reg.register(slow)
    assert await reg.execute("slow", {}) == {"ok": True, "found": True, "data": "done"}
    # 这两个属性库当前并不读取,仅登记备用;真实超时由 execute 的 asyncio.wait_for 保证
    assert slow.time_limit is True
    assert slow.max_execution_time == 5.0


@pytest.mark.asyncio
async def test_negative_max_retries_still_returns_dict():
    # max_retries < 0 时也必须至少跑一次并返回结构化 dict,不能返回 None
    reg = ToolRegistry(timeout=5.0, max_retries=-1)

    @tool
    def echo() -> str:
        """回显工具。"""
        return "x"

    reg.register(echo)
    result = await reg.execute("echo", {})
    assert result == {"ok": True, "found": True, "data": "x"}


@pytest.mark.asyncio
async def test_real_timeout_retried_then_wrapped(monkeypatch):
    # 真实超时:异步工具 sleep 超过 timeout,由 asyncio.wait_for 触发
    monkeypatch.setattr(reg_mod, "RETRY_INTERVAL", 0)
    reg = ToolRegistry(timeout=0.05, max_retries=1)
    calls = {"n": 0}

    @tool
    async def hanging() -> str:
        """真正会挂住的慢工具。"""
        calls["n"] += 1
        await asyncio.sleep(1.0)
        return "never"

    reg.register(hanging)
    result = await reg.execute("hanging", {})
    assert result == {"ok": False, "error": "timeout"}
    assert calls["n"] == 2  # 首次 + 重试 1 次


def test_make_tool_message_matches_call():
    msg = reg_mod.make_tool_message("call_1", "query_poem", {"ok": True})
    assert isinstance(msg, ToolMessage)
    assert msg.tool_call_id == "call_1"
    assert msg.name == "query_poem"
    assert msg.content == '{"ok": true}'
