"""MCP 工具发现:多 Server 各取各的、TTL 缓存、失败保留上次成功清单。"""
import asyncio
import time

from langchain_mcp_adapters.client import MultiServerMCPClient

from tool_system.spec import (
    MCP_SERVER_POLICIES,
    PERMISSION_WRITE,
    ToolSpec,
    schema_of,
)

# 内部枚举码 → 人话(执行引擎统一翻译,模型不接触内部码)
ENUM_LABELS = {
    "judgement_status_lookup": {
        "meter": "格律判定",
        "verify": "校核判定",
        "pass": "通过",
        "fail": "未通过",
    },
    "correction_progress_lookup": {
        "received": "已受理",
        "reviewing": "复核中",
        "done": "已完成",
    },
}


class McpProvider:
    def __init__(
        self, servers: dict[str, str], *, ttl: float = 5.0,
        connect_timeout: float = 2.0, policies: dict[str, str] | None = None,
        client=None,
    ) -> None:
        self._servers = dict(servers)
        self._ttl = ttl
        self._connect_timeout = connect_timeout
        self._policies = MCP_SERVER_POLICIES if policies is None else policies
        self._client = client or MultiServerMCPClient({
            name: {
                "transport": "streamable_http",
                "url": url,
                "timeout": connect_timeout,
                "sse_read_timeout": connect_timeout,
            }
            for name, url in self._servers.items()
        })
        self._cache: dict[str, list[ToolSpec]] = {}
        self._last_refresh = 0.0

    async def refresh(self, force: bool = False) -> list[ToolSpec]:
        now = time.monotonic()
        if not force and self._last_refresh and now - self._last_refresh < self._ttl:
            return self._flatten()
        await asyncio.gather(*(self._refresh_server(name) for name in self._servers))
        self._last_refresh = now
        return self._flatten()

    async def _refresh_server(self, server: str) -> None:
        try:
            tools = await asyncio.wait_for(
                self._client.get_tools(server_name=server),
                timeout=self._connect_timeout + 1.0,
            )
        except Exception as exc:  # noqa: BLE001 - 单 Server 失败不影响其它 Server
            print(f"[mcp] {server} unreachable: {str(exc)[:160]}")
            return
        permission = self._policies.get(server, PERMISSION_WRITE)
        self._cache[server] = [
            ToolSpec(
                name=tool.name,
                description=tool.description or "",
                input_schema=schema_of(tool),
                source=f"mcp:{server}",
                permission=permission,
                requires_confirmation=permission == PERMISSION_WRITE,
                tool=tool,
                enum_labels=ENUM_LABELS.get(tool.name),
            )
            for tool in tools
        ]

    def _flatten(self) -> list[ToolSpec]:
        out: list[ToolSpec] = []
        for server in self._servers:
            out.extend(self._cache.get(server, []))
        return out
