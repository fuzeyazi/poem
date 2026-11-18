"""统一工具目录:内置登记、插件新增/修改/删除热加载、重名跳过、权限查询。"""
import asyncio
import os
from pathlib import Path

import pytest
from langchain_core.tools import tool

from config import Settings
from tool_system.catalog import ToolCatalog
from tool_system.spec import MCP_SERVER_POLICIES, ToolSpec


class FakeAudit:
    def __init__(self):
        self.rows = []

    async def record(self, **fields):
        self.rows.append(fields)


class FakeProvider:
    def __init__(self, specs):
        self.specs = specs

    async def refresh(self, force=False):
        return list(self.specs)


def make_settings(**over):
    base = dict(
        llm_base_url="http://fake", llm_api_key="sk-fake", llm_model="fake",
        history_max_tokens=2000, llm_temperature=0.7,
        mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
    )
    base.update(over)
    return Settings(**base)


@tool
def builtin_tool(text: str) -> dict:
    """内置示例。

    Args:
        text: 文本
    """
    return {"ok": True, "found": True, "text": text}


def make_catalog(plugin_dir=None, provider=None):
    return ToolCatalog(
        engine=object(), audit=FakeAudit(),
        plugin_dir=plugin_dir, mcp_provider=provider,
    )


PLUGIN_V1 = '''
from langchain_core.tools import tool

@tool
def extra_tool(text: str) -> dict:
    """插件示例。"""
    return {"ok": True, "found": True, "echo": text}

def register(catalog):
    catalog.register_builtin(extra_tool)
'''

PLUGIN_V2 = PLUGIN_V1.replace('echo": text', 'echo": text.upper()')


def test_builtin_registration_and_schema():
    catalog = make_catalog()
    catalog.register_builtin(builtin_tool)
    names = asyncio.run(catalog.get_tools())
    assert [t.name for t in names] == ["builtin_tool"]
    spec = catalog.get_spec("builtin_tool")
    assert spec.source == "builtin"
    assert spec.permission == "read"
    assert spec.requires_confirmation is False


def test_write_tool_requires_confirmation_by_default():
    catalog = make_catalog()
    catalog.register_builtin(builtin_tool, permission="write")
    asyncio.run(catalog.get_tools())
    assert catalog.requires_confirmation("builtin_tool") is True


def test_plugin_add_reload_and_remove(tmp_path):
    plugin = tmp_path / "extra_plugin.py"
    plugin.write_text(PLUGIN_V1, encoding="utf-8")
    catalog = make_catalog(plugin_dir=tmp_path)

    asyncio.run(catalog.get_tools())
    assert catalog.get_spec("extra_tool") is not None

    plugin.write_text(PLUGIN_V2, encoding="utf-8")
    stat = plugin.stat()
    os.utime(plugin, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    asyncio.run(catalog.get_tools())
    spec = catalog.get_spec("extra_tool")
    assert spec is not None and spec.plugin

    plugin.unlink()
    asyncio.run(catalog.get_tools())
    assert catalog.get_spec("extra_tool") is None


def test_plugin_import_error_does_not_break_other_tools(tmp_path):
    (tmp_path / "bad_plugin.py").write_text("raise RuntimeError('bad')\n", encoding="utf-8")
    catalog = make_catalog(plugin_dir=tmp_path)
    catalog.register_builtin(builtin_tool)
    tools = asyncio.run(catalog.get_tools())
    assert [t.name for t in tools] == ["builtin_tool"]


def test_mcp_duplicate_name_is_skipped_builtin_wins():
    provider = FakeProvider([
        ToolSpec(name="builtin_tool", description="mcp 重名", input_schema={}, source="mcp:x", tool=builtin_tool),
        ToolSpec(name="mcp_only", description="只有 MCP", input_schema={}, source="mcp:x", tool=builtin_tool),
    ])
    catalog = make_catalog(provider=provider)
    catalog.register_builtin(builtin_tool)
    asyncio.run(catalog.get_tools())
    assert catalog.get_spec("builtin_tool").source == "builtin"
    assert catalog.get_spec("mcp_only").source == "mcp:x"


def test_validate_args_uses_registered_schema():
    catalog = make_catalog()
    catalog.register_builtin(builtin_tool)
    asyncio.run(catalog.get_tools())
    assert catalog.validate_args("builtin_tool", {"text": "x"}) is True
    assert catalog.validate_args("builtin_tool", {}) is False
    assert catalog.validate_args("missing", {}) is False


def test_default_mcp_policies_are_read_only():
    assert MCP_SERVER_POLICIES == {"poetry_archive": "read", "judgement": "read"}
