"""统一工具表:内置 + 插件 + MCP,负责刷新、查询、执行与权限判定。"""
import asyncio
from pathlib import Path

from langchain_core.runnables.config import RunnableConfig

from tool_system.formatter import dump, summary
from tool_system.plugins import PluginLoader
from tool_system.spec import (
    PERMISSION_READ,
    PERMISSION_WRITE,
    SOURCE_BUILTIN,
    ToolInvocation,
    ToolSpec,
    schema_of,
    validate_args as schema_errors,
)


class ToolCatalog:
    def __init__(self, *, engine, audit, plugin_dir=None, mcp_provider=None) -> None:
        self._engine = engine
        self._audit = audit
        self._plugins = PluginLoader(plugin_dir) if plugin_dir else None
        self._mcp_provider = mcp_provider
        self._builtin: dict[str, ToolSpec] = {}
        self._merged: dict[str, ToolSpec] = {}
        self._current_plugin: str | None = None
        self._lock = asyncio.Lock()

    # ---------- 登记 ----------
    def register_builtin(
        self, tool, *, permission: str = PERMISSION_READ,
        requires_confirmation: bool | None = None,
        result_fields=None, enum_labels=None,
        timeout: float | None = None, max_retries: int | None = None,
        source: str = SOURCE_BUILTIN,
    ) -> ToolSpec:
        spec = ToolSpec(
            name=tool.name,
            description=tool.description or "",
            input_schema=schema_of(tool),
            source=source,
            permission=permission,
            requires_confirmation=(
                permission == PERMISSION_WRITE
                if requires_confirmation is None else requires_confirmation
            ),
            tool=tool,
            timeout=timeout,
            max_retries=max_retries,
            result_fields=tuple(result_fields) if result_fields else None,
            enum_labels=dict(enum_labels) if enum_labels else None,
            plugin=self._current_plugin,
        )
        self._builtin[spec.name] = spec
        return spec

    def begin_plugin(self, key: str) -> None:
        self._current_plugin = key

    def end_plugin(self) -> None:
        self._current_plugin = None

    def plugin_tool_names(self, key: str) -> list[str]:
        return [s.name for s in self._builtin.values() if s.plugin == key]

    def unregister_plugin(self, key: str) -> None:
        for name in self.plugin_tool_names(key):
            self._builtin.pop(name, None)
            self._merged.pop(name, None)

    # ---------- 刷新与查询 ----------
    async def _refresh(self) -> None:
        async with self._lock:
            if self._plugins is not None:
                await self._plugins.refresh(self)
            merged = dict(self._builtin)
            if self._mcp_provider is not None:
                for spec in await self._mcp_provider.refresh():
                    if spec.name in merged:
                        print(f"[mcp] skip duplicate {spec.name}")
                        continue
                    merged[spec.name] = spec
            self._merged = merged

    async def get_specs(self) -> list[ToolSpec]:
        await self._refresh()
        return list(self._merged.values())

    async def get_tools(self) -> list:
        return [s.tool for s in await self.get_specs() if s.tool is not None]

    def get_spec(self, name: str) -> ToolSpec | None:
        return self._merged.get(name)

    def requires_confirmation(self, name: str) -> bool:
        spec = self._merged.get(name)
        return bool(spec and spec.requires_confirmation)

    def validate_args(self, name: str, args: dict) -> bool:
        spec = self._merged.get(name)
        if spec is None:
            return False
        return not schema_errors(spec.input_schema, args)

    # ---------- 执行 ----------
    async def execute(
        self, name: str, args: dict, *,
        session_id: str = "", userid: str | None = None,
        tool_call_id: str = "", approved: bool = False,
        config: RunnableConfig | None = None,
    ) -> dict:
        await self._refresh()
        spec = self._merged.get(name)
        if spec is None:
            result = {"ok": False, "error_type": "unknown_tool", "message": f"未知工具: {name}"}
            try:
                await self._audit.record(
                    session_id=session_id or None, tool_call_id=tool_call_id or None,
                    tool_name=name, source="unknown", arguments=dump(args),
                    result_summary=summary(result), status="error",
                    error=result["message"], retry_count=0, duration_ms=0,
                )
            except Exception as exc:  # noqa: BLE001 - 审计失败不得反向拦截
                print(f"[audit] fail: {str(exc)[:200]}")
            return result
        return await self._engine.execute(
            spec, args,
            ToolInvocation(
                session_id=session_id, tool_call_id=tool_call_id,
                userid=userid, approved=approved,
            ),
            config=config,
        )
