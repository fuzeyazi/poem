"""审计写入:独立会话 + try/except;失败只告警,不影响工具执行。"""
import asyncio


class AuditWriter:
    def __init__(self, storage=None) -> None:
        self._storage = storage

    async def record(self, **fields) -> None:
        if self._storage is None:
            return
        try:
            await asyncio.to_thread(self._storage.add_tool_audit, **fields)
        except Exception as exc:  # noqa: BLE001 - 审计失败不得反向拦截工具
            print(f"[audit] fail: {str(exc)[:200]}")
