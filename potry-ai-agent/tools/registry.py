"""工具注册表:登记 @tool 工具,统一执行入口(Schema 校验 → 超时 → 重试 → 错误包装)。"""
import asyncio
import json
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool

RETRY_INTERVAL = 0.2  # 固定间隔秒数,不搞指数退避(YAGNI);测试置 0 免等待


def make_tool_message(tool_call_id: str, name: str, result: dict) -> ToolMessage:
    """工具结果 JSON 包进 ToolMessage,tool_call_id 对齐(spec §4 结果回灌)。"""
    return ToolMessage(
        content=json.dumps(result, ensure_ascii=False),
        tool_call_id=tool_call_id,
        name=name,
    )


class ToolRegistry:
    def __init__(self, timeout: float = 5.0, max_retries: int = 1) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        # 时间上限打在工具上,库当前不读取该属性,仅登记备用(未来版本可能
        # 消费);真实超时由 execute 的 asyncio.wait_for 保证。langchain-core
        # 1.6.10 的 Pydantic 模型拒收未知字段,setattr 抛 ValueError 时
        # 绕过校验直挂实例属性。
        for attr, value in (("time_limit", True), ("max_execution_time", self._timeout)):
            try:
                setattr(tool, attr, value)
            except (ValueError, AttributeError):
                object.__setattr__(tool, attr, value)
        self._tools[tool.name] = tool

    def get_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    async def execute(self, name: str, args: dict) -> dict:
        """执行一个工具调用。返回结构化 dict;永不抛异常。

        结果约定:成功 `{"ok":true,"found":true,"data":...}`;业务查不到
        `{"ok":true,"found":false}`(由工具函数给出);执行失败 `{"ok":false,"error":...}`。
        """
        tool = self._tools.get(name)
        if tool is None:
            return {"ok": False, "error": f"unknown tool: {name}"}

        try:
            if tool.args_schema is not None:
                tool.args_schema.model_validate(args)  # 失败抛 ValidationError
        except Exception as exc:  # noqa: BLE001 - Pydantic ValidationError
            return {"ok": False, "error": f"invalid arguments: {str(exc)[:200]}"}

        result: dict[str, Any]
        # max_retries < 0 时也至少跑一次,保证 execute 永远返回结构化 dict
        attempts = max(1, self._max_retries + 1)
        for attempt in range(attempts):
            try:
                raw = await asyncio.wait_for(tool.ainvoke(dict(args)), timeout=self._timeout)
                result = (
                    raw
                    if isinstance(raw, dict)
                    else {"ok": True, "found": True, "data": raw}
                )
                break
            except (asyncio.TimeoutError, TimeoutError):
                result = {"ok": False, "error": "timeout"}
            except Exception as exc:  # noqa: BLE001 - 工具异常统一包装
                result = {"ok": False, "error": str(exc)[:200]}
            if attempt < attempts - 1:
                await asyncio.sleep(RETRY_INTERVAL)
        return result
