"""MCP 发现:逐 Server 归属、TTL、失败保留上次清单、未知 Server 默认写。"""
import asyncio

import pytest

from tool_system.mcp_provider import McpProvider


class FakeTool:
    def __init__(self, name, description="", schema=None):
        self.name = name
        self.description = description
        self.args_schema = schema or {
            "type": "object",
            "properties": {"keyword": {"type": "string"}},
            "required": ["keyword"],
        }


class FakeClient:
    def __init__(self, mapping, fail_servers=()):
        self.mapping = mapping
        self.fail_servers = set(fail_servers)
        self.calls = []

    async def get_tools(self, *, server_name):
        self.calls.append(server_name)
        if server_name in self.fail_servers:
            raise ConnectionError("server down")
        return self.mapping.get(server_name, [])


@pytest.mark.asyncio
async def test_tools_are_attributed_per_server():
    client = FakeClient({
        "poetry_archive": [FakeTool("poem_archive_lookup")],
        "judgement": [FakeTool("judgement_status_lookup"),
                      FakeTool("correction_progress_lookup")],
    })
    provider = McpProvider(
        {"poetry_archive": "http://x/1/mcp", "judgement": "http://x/2/mcp"},
        client=client,
    )
    specs = await provider.refresh()
    by_name = {s.name: s for s in specs}
    assert by_name["poem_archive_lookup"].source == "mcp:poetry_archive"
    assert by_name["judgement_status_lookup"].source == "mcp:judgement"
    assert by_name["correction_progress_lookup"].permission == "read"
    assert by_name["judgement_status_lookup"].enum_labels["pass"] == "通过"


@pytest.mark.asyncio
async def test_ttl_caches_and_force_refreshes():
    client = FakeClient({"poetry_archive": [FakeTool("a")]})
    provider = McpProvider({"poetry_archive": "http://x/mcp"}, ttl=60, client=client)
    await provider.refresh()
    await provider.refresh()
    assert client.calls == ["poetry_archive"]
    await provider.refresh(force=True)
    assert client.calls == ["poetry_archive", "poetry_archive"]


@pytest.mark.asyncio
async def test_failed_server_keeps_last_successful_list():
    client = FakeClient({"poetry_archive": [FakeTool("a")]})
    provider = McpProvider({"poetry_archive": "http://x/mcp"}, ttl=0, client=client)
    first = await provider.refresh()
    assert [s.name for s in first] == ["a"]

    client.fail_servers.add("poetry_archive")
    second = await provider.refresh(force=True)
    assert [s.name for s in second] == ["a"]        # 保留上次成功清单


@pytest.mark.asyncio
async def test_unknown_server_defaults_to_write_with_confirmation():
    client = FakeClient({"unknown": [FakeTool("danger")]})
    provider = McpProvider(
        {"unknown": "http://x/mcp"},
        client=client, policies={},
    )
    specs = await provider.refresh()
    assert specs[0].permission == "write"
    assert specs[0].requires_confirmation is True
