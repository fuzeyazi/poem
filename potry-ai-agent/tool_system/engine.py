"""统一执行引擎:JSON Schema 校验 → 权限门 → 超时/重试 → 格式化 → 审计。"""
import asyncio
import time

from langchain_core.runnables.config import RunnableConfig

from tool_system.formatter import dump, normalize, summary
from tool_system.spec import (
    PERMISSION_WRITE,
    ToolInvocation,
    ToolSpec,
    bind_invocation,
    reset_invocation,
    validate_args,
)

RETRY_INTERVAL = 0.2
_TRANSIENT_HINTS = (
    "timeout", "timed out", "connection", "temporarily",
    "unavailable", "reset by peer",
)


def _error(error_type: str, message: str, details: list[str] | None = None) -> dict:
    out = {"ok": False, "error_type": error_type, "message": message}
    if details:
        out["details"] = details[:5]
    return out


def _transient(exc: Exception | None) -> bool:
    if exc is None:
        return False
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True
    text = str(exc).lower()
    return any(hint in text for hint in _TRANSIENT_HINTS)


class ToolEngine:
    def __init__(self, settings, audit) -> None:
        self._settings = settings
        self._audit = audit

    async def execute(self, spec: ToolSpec, args: dict, invocation: ToolInvocation,
                      config: RunnableConfig | None = None) -> dict:
        """执行一次工具调用;永远返回结构化 dict,不向 Agent 抛异常。"""
        started = time.monotonic()
        retry_count = 0

        errors = validate_args(spec.input_schema, args)
        if errors:
            result = _error("invalid_arguments", f"参数校验失败: {errors[0]}", errors)
            await self._record(spec, args, result, "validation_error", invocation, retry_count, started)
            return result

        if spec.permission == PERMISSION_WRITE and invocation.approved is not True:
            result = _error("permission_denied", "用户未确认,本次操作已取消,未执行")
            await self._record(spec, args, result, "permission_denied", invocation, retry_count, started)
            return result

        timeout = spec.timeout if spec.timeout is not None else self._settings.tool_timeout_seconds
        retries = 0 if spec.permission == PERMISSION_WRITE else max(
            0,
            spec.max_retries if spec.max_retries is not None else self._settings.tool_max_retries,
        )
        attempts = retries + 1
        result: dict = {}
        status = "success"
        last_error: Exception | None = None
        timed_out = False
        token = bind_invocation(invocation)
        try:
            for attempt in range(attempts):
                try:
                    raw = await asyncio.wait_for(spec.tool.ainvoke(dict(args), config=config), timeout=timeout)
                    result = normalize(raw, spec)
                    status = "success" if result.get("ok") else "error"
                    break
                except (asyncio.TimeoutError, TimeoutError) as exc:
                    last_error, timed_out = exc, True
                except Exception as exc:  # noqa: BLE001 - 工具异常统一分诊
                    last_error, timed_out = exc, False
                can_retry = (
                    attempt < attempts - 1
                    and spec.permission != PERMISSION_WRITE
                    and _transient(last_error)
                )
                if not can_retry:
                    break
                retry_count += 1
                await asyncio.sleep(RETRY_INTERVAL)
        finally:
            reset_invocation(token)

        if last_error is not None:
            status = "timeout" if timed_out else "error"
            message = (
                "工具调用超时,暂时查不了"
                if timed_out
                else f"工具执行出错: {str(last_error)[:200]}"
            )
            result = _error("timeout" if timed_out else "fault", message)
        elif not result:
            status = "error"
            result = _error("fault", "工具未返回结果")

        await self._record(spec, args, result, status, invocation, retry_count, started)
        return result

    async def _record(
        self, spec: ToolSpec, args: dict, result: dict, status: str,
        invocation: ToolInvocation, retry_count: int, started: float,
    ) -> None:
        try:
            await self._audit.record(
                session_id=invocation.session_id or None,
                tool_call_id=invocation.tool_call_id or None,
                tool_name=spec.name,
                source=spec.source,
                arguments=dump(args),
                result_summary=summary(result),
                status=status,
                error=None if result.get("ok") else result.get("message"),
                retry_count=retry_count,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        except Exception as exc:  # noqa: BLE001 - 审计失败不得反向拦截工具
            print(f"[audit] fail: {str(exc)[:200]}")
