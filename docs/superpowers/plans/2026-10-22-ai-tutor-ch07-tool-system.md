# Ch07 工具系统即插即用 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Ch02 以来写死的工具层升级为统一注册、JSON Schema 校验、读写权限门、统一执行引擎、全量审计、双 MCP Server 接入、`create_ticket` 人工确认流的即插即用工具系统。

**Architecture:** 新增 `tool_system/` 包承载 `ToolSpec / ToolCatalog / ToolEngine / AuditWriter / PluginLoader / McpProvider`；`tools/extensions/*.py` 由目录扫描热加载；两个 FastMCP Server 独立进程提供诗词档案与判定/纠错工具；主力 Agent 通过 `ToolCatalog` 异步取工具、经引擎执行；`create_ticket` 由专用 `ticket_confirm` 节点调用 LangGraph `interrupt()`，HTTP `resume` 放行后落 `tickets` 表。

**Tech Stack:** Python 3.11、FastAPI 0.143、LangGraph 1.2.16、LangChain 1.6.10、`mcp==1.30.0`、`langchain-mcp-adapters==0.3.2`、`jsonschema==4.26.0`、MySQL/SQLAlchemy 2.0、原生 HTML/JS。

**Spec:** `docs/superpowers/specs/2026-10-22-ai-tutor-ch07-tool-system-design.md`

---

## 0. 执行约定

- 工作目录：`e:\javatexts\poetry-spring2\potry-ai-agent`。
- 每个任务结束必须提交，且 **只 add 本任务涉及的文件**。工作区当前有与本任务无关的未提交改动（`frontend/`、`pom.xml`、`potry-service/` 等），一律不得带入提交。
- 所有 pytest 命令均用项目虚拟环境：`.\.venv\Scripts\python.exe -m pytest ...`。
- 每个任务完成后，按用户要求把「用户关键原话、关键产出、拒绝/纠偏、翻车与返工」追记到 `dev-notes/ch07.md`，不得收尾时一次性补记。
- 纯 Prompt/数据类任务（Task 11）不写 TDD，用标注样例跑真实模型；前端（Task 12）按 Vibe Coding 例外，不套 brainstorm/TDD/code review。

---

### Task 1: 依赖安装与基线上浮验证

**Files:**
- Modify: `potry-ai-agent/requirements.txt`

- [ ] **Step 1: 更新依赖版本**

把 `requirements.txt` 中 `pydantic==2.9.2` 改为 `pydantic==2.14.1`（`mcp 1.30.0` 要求 `pydantic>=2.11`，dry-run 解析结果就是 2.14.1），并在 Ch04 依赖段之后追加：

```text
# Ch07 工具系统:MCP Server/Client 与 JSON Schema 校验
mcp==1.30.0
langchain-mcp-adapters==0.3.2
jsonschema==4.26.0
```

- [ ] **Step 2: 安装依赖**

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Expected: 成功安装 `mcp-1.30.0`、`langchain-mcp-adapters-0.3.2`、`jsonschema-4.26.0`、`pydantic-2.14.1`，无 `ResolutionImpossible`。

- [ ] **Step 3: 全量回归**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: 所有既有用例通过（Ch06 收口时为 325 passed，pydantic 升级后数量不变、无 failed）。若出现 pydantic 相关失败，**停下报告，不自行换栈**。

- [ ] **Step 4: 提交**

```powershell
git add potry-ai-agent/requirements.txt
git commit -m "build(ch07): add mcp sdk, mcp adapters and jsonschema"
```

---

### Task 2: 存储层新增 `tickets` / `tool_audit_logs`

**Files:**
- Modify: `potry-ai-agent/app_storage.py`
- Test: `potry-ai-agent/tests/test_tool_storage.py`

- [ ] **Step 1: 写失败测试**

新建 `potry-ai-agent/tests/test_tool_storage.py`：

```python
"""Ch07 新表:tickets 与 tool_audit_logs 的列、落行、无外键。"""
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app_storage import AppBase, AppStorage, Ticket, ToolAuditLog


def _storage():
    engine = create_engine("sqlite:///:memory:")
    AppBase.metadata.create_all(engine)
    return AppStorage(sessionmaker(bind=engine)), engine


def test_ticket_columns_match_spec():
    assert {c.name for c in Ticket.__table__.columns} == {
        "id", "ticket_no", "userid", "session_id",
        "ticket_type", "description", "status", "created_at",
    }


def test_add_ticket_returns_auto_number():
    storage, engine = _storage()
    ticket_id, ticket_no = storage.add_ticket(
        "内容纠错", "《静夜思》原文有错字", session_id="s1", userid="u-1"
    )
    assert ticket_no == f"TK{ticket_id:06d}"
    with sessionmaker(bind=engine)() as session:
        row = session.get(Ticket, ticket_id)
    assert row.ticket_no == ticket_no
    assert row.ticket_type == "内容纠错"
    assert row.description == "《静夜思》原文有错字"
    assert row.status == "submitted"
    assert row.session_id == "s1"
    assert row.userid == "u-1"
    assert row.created_at is not None


def test_tool_audit_columns_match_spec():
    assert {c.name for c in ToolAuditLog.__table__.columns} == {
        "id", "session_id", "tool_call_id", "tool_name", "source",
        "arguments", "result_summary", "status", "error",
        "retry_count", "duration_ms", "created_at",
    }


def test_add_tool_audit_appends_row_without_foreign_keys():
    storage, engine = _storage()
    audit_id = storage.add_tool_audit(
        session_id="s1", tool_call_id="c1", tool_name="query_poet",
        source="builtin", arguments='{"name": "李白"}',
        result_summary='{"ok": true}', status="success",
        error=None, retry_count=0, duration_ms=12,
    )
    with sessionmaker(bind=engine)() as session:
        row = session.get(ToolAuditLog, audit_id)
    assert row.tool_name == "query_poet"
    assert row.source == "builtin"
    assert row.arguments == '{"name": "李白"}'
    assert row.status == "success"
    assert row.retry_count == 0
    assert row.duration_ms == 12
    assert row.created_at is not None
    assert inspect(engine).get_foreign_keys("tool_audit_logs") == []
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_storage.py -v
```

Expected: FAIL，`ImportError: cannot import name 'Ticket'`。

- [ ] **Step 3: 实现模型与写入**

在 `app_storage.py` 的 `Correction` 之后追加：

```python
class Ticket(AppBase):
    """建单确认流落库表(Ch07 spec §9.1);不挂外键。"""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_no: Mapped[str] = mapped_column(String(32), default="")
    userid: Mapped[str | None] = mapped_column(String(64))
    session_id: Mapped[str | None] = mapped_column(String(64))
    ticket_type: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="submitted")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.now)


class ToolAuditLog(AppBase):
    """工具调用审计(Ch07 spec §7);不挂外键,写失败不得阻断工具。"""

    __tablename__ = "tool_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(String(64))
    tool_call_id: Mapped[str | None] = mapped_column(String(64))
    tool_name: Mapped[str] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[str] = mapped_column(Text)
    result_summary: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.now)
```

在 `AppStorage` 类末尾追加：

```python
    def add_ticket(
        self, ticket_type: str, description: str,
        session_id: str | None = None, userid: str | None = None,
    ) -> tuple[int, str]:
        """写工单并回填 `TK%06d` 编号,返回 (id, ticket_no)。"""
        with self._factory() as session:
            row = Ticket(
                userid=userid, session_id=session_id,
                ticket_type=ticket_type, description=description,
            )
            session.add(row)
            session.flush()
            row.ticket_no = f"TK{row.id:06d}"
            session.commit()
            return row.id, row.ticket_no

    def add_tool_audit(
        self, *, session_id: str | None, tool_call_id: str | None,
        tool_name: str, source: str, arguments: str, result_summary: str,
        status: str, error: str | None = None,
        retry_count: int = 0, duration_ms: int = 0,
    ) -> int:
        """每次工具调用落一条审计;调用方负责 try/except,本方法不吞异常。"""
        with self._factory() as session:
            row = ToolAuditLog(
                session_id=session_id, tool_call_id=tool_call_id,
                tool_name=tool_name, source=source, arguments=arguments,
                result_summary=result_summary, status=status, error=error,
                retry_count=retry_count, duration_ms=duration_ms,
            )
            session.add(row)
            session.commit()
            return row.id
```

- [ ] **Step 4: 跑测试确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_storage.py -v
```

Expected: 4 passed。

- [ ] **Step 5: 提交**

```powershell
git add potry-ai-agent/app_storage.py potry-ai-agent/tests/test_tool_storage.py
git commit -m "feat(ch07): add tickets and tool audit log tables"
```

---

### Task 3: 工具规格、JSON Schema 与结果格式化

**Files:**
- Create: `potry-ai-agent/tool_system/__init__.py`
- Create: `potry-ai-agent/tool_system/spec.py`
- Create: `potry-ai-agent/tool_system/formatter.py`
- Test: `potry-ai-agent/tests/test_tool_spec.py`

- [ ] **Step 1: 写失败测试**

新建 `potry-ai-agent/tests/test_tool_spec.py`：

```python
"""ToolSpec / Schema 提取 / Schema 校验 / 结果归一与枚举翻译。"""
from langchain_core.tools import tool

from tool_system.formatter import dump, normalize
from tool_system.spec import ToolSpec, schema_of, validate_args


@tool
def sample(count: int, label: str = "x") -> dict:
    """示例工具。

    Args:
        count: 数量
        label: 标签
    """
    return {"ok": True, "found": True, "count": count, "label": label}


def test_schema_of_builtin_tool_is_object_schema():
    schema = schema_of(sample)
    assert schema["type"] == "object"
    assert "count" in schema["properties"]
    assert schema["required"] == ["count"]


def test_validate_args_reports_missing_required_and_enum():
    schema = {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["a", "b"]},
            "n": {"type": "integer", "minimum": 1},
        },
        "required": ["kind"],
    }
    assert validate_args(schema, {})
    assert validate_args(schema, {"kind": "c"})
    assert validate_args(schema, {"kind": "a", "n": 0})
    assert validate_args(schema, {"kind": "a", "n": 1}) == []


def test_validate_args_limits_details_to_five():
    schema = {
        "type": "object",
        "properties": {f"f{i}": {"type": "string"} for i in range(8)},
        "required": [f"f{i}" for i in range(8)],
    }
    assert len(validate_args(schema, {})) == 5


def test_normalize_keeps_ok_found_and_translates_enum():
    spec = ToolSpec(
        name="probe", description="", input_schema={},
        enum_labels={"received": "已受理"},
    )
    result = normalize(
        {"ok": True, "found": True, "progress": "received",
         "items": ["done"], "nested": {"status": "received"}},
        spec,
    )
    assert result["progress"] == "已受理"
    assert result["nested"]["status"] == "已受理"
    assert result["items"] == ["done"]
    assert "\\u" not in dump(result)


def test_normalize_filters_result_fields_but_keeps_contract_keys():
    spec = ToolSpec(
        name="probe", description="", input_schema={},
        result_fields=("poem",),
    )
    result = normalize(
        {"ok": True, "found": True, "poem": {"title": "静夜思"}, "debug": "x"},
        spec,
    )
    assert result == {"ok": True, "found": True, "poem": {"title": "静夜思"}}


def test_normalize_converts_error_key_to_message():
    result = normalize({"ok": False, "error": "db down"})
    assert result["ok"] is False
    assert result["error_type"] == "fault"
    assert result["message"] == "db down"
    assert "error" not in result


def test_normalize_wraps_non_dict_value():
    result = normalize("纯文本结果")
    assert result == {"ok": True, "found": True, "data": "纯文本结果"}
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_spec.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'tool_system'`。

- [ ] **Step 3: 实现 spec 与 formatter**

新建 `potry-ai-agent/tool_system/__init__.py`（空文件）。

新建 `potry-ai-agent/tool_system/spec.py`：

```python
"""工具系统统一规格:名称、用途、JSON Schema、来源、权限与调用上下文。"""
import json
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

import jsonschema
from langchain_core.tools import BaseTool

PERMISSION_READ = "read"
PERMISSION_WRITE = "write"
SOURCE_BUILTIN = "builtin"

# 外部 MCP Server 的声明不可信:权限只认本侧策略表;未知 Server 默认写+需确认
MCP_SERVER_POLICIES = {
    "poetry_archive": PERMISSION_READ,
    "judgement": PERMISSION_READ,
}


@dataclass
class ToolInvocation:
    session_id: str = ""
    tool_call_id: str = ""
    userid: str | None = None
    approved: bool = False


_invocation: ContextVar[ToolInvocation | None] = ContextVar("tool_invocation", default=None)


def current_invocation() -> ToolInvocation:
    """工具函数内取当前调用上下文(建单工具据此拿 session/user)。"""
    return _invocation.get() or ToolInvocation()


def bind_invocation(invocation: ToolInvocation):
    return _invocation.set(invocation)


def reset_invocation(token) -> None:
    _invocation.reset(token)


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    source: str = SOURCE_BUILTIN
    permission: str = PERMISSION_READ
    requires_confirmation: bool = False
    tool: BaseTool | None = None
    timeout: float | None = None
    max_retries: int | None = None
    result_fields: tuple[str, ...] | None = None
    enum_labels: dict[str, str] | None = None
    plugin: str | None = None


def schema_of(tool: BaseTool) -> dict:
    """从 LangChain 工具提取 JSON Schema;MCP 适配器可能直接给 dict。"""
    schema = getattr(tool, "args_schema", None)
    if isinstance(schema, dict):
        return schema
    if schema is not None and hasattr(schema, "model_json_schema"):
        return schema.model_json_schema()
    return {"type": "object", "properties": {}}


def validate_args(schema: dict | None, args: dict) -> list[str]:
    """按 JSON Schema 校验参数,返回人类可读错误列表(最多 5 条)。"""
    target = schema or {"type": "object"}
    validator_cls = jsonschema.validators.validator_for(target)
    validator = validator_cls(target)
    errors = sorted(validator.iter_errors(args or {}), key=lambda e: list(e.path))
    out: list[str] = []
    for error in errors:
        path = "/".join(str(p) for p in error.path)
        out.append(f"{path}: {error.message}" if path else error.message)
    return out[:5]


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
```

新建 `potry-ai-agent/tool_system/formatter.py`：

```python
"""工具结果归一化:统一结构、字段裁剪、枚举翻译、中文不转义。"""
import json
from typing import Any

from tool_system.spec import ToolSpec


def _translate(value: Any, labels: dict[str, str]) -> Any:
    if isinstance(value, str):
        return labels.get(value, value)
    if isinstance(value, dict):
        return {k: _translate(v, labels) for k, v in value.items()}
    if isinstance(value, list):
        return [_translate(v, labels) for v in value]
    return value


def _unwrap_content(raw: Any) -> Any:
    """MCP 适配器返回内容块列表或 (content, artifact),统一解成业务 dict/文本。"""
    if isinstance(raw, tuple) and len(raw) == 2:
        return _unwrap_content(raw[0])
    if isinstance(raw, list):
        texts = [
            block.get("text") for block in raw
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
        ]
        for text in texts:
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError):
                continue
            if isinstance(parsed, dict):
                return parsed
        if texts:
            return "\n".join(texts)
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return raw
        return parsed if isinstance(parsed, dict) else raw
    content = getattr(raw, "content", None)
    if content is not None and not isinstance(raw, (dict, str, bytes)):
        return _unwrap_content(content)
    return raw


def normalize(raw: Any, spec: ToolSpec | None = None) -> dict:
    """把工具返回值归一成统一 dict;永不抛异常。"""
    raw = _unwrap_content(raw)
    if isinstance(raw, dict):
        result = dict(raw)
    else:
        result = {"ok": True, "found": True, "data": raw}

    result.setdefault("ok", True)
    if result.get("ok") is False:
        message = result.get("message") or result.get("error") or "工具执行失败"
        result.pop("error", None)
        result["message"] = message
        result.setdefault("error_type", "fault")

    if spec is not None and spec.result_fields:
        keep = set(spec.result_fields) | {
            "ok", "found", "error_type", "message", "details",
        }
        result = {k: v for k, v in result.items() if k in keep}

    if spec is not None and spec.enum_labels:
        result = _translate(result, spec.enum_labels)
    return result


def dump(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, default=str)


def summary(result: dict, limit: int = 300) -> str:
    return dump(result)[:limit]
```

- [ ] **Step 4: 跑测试确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_spec.py -v
```

Expected: 9 passed(执行时补了 2 个 MCP 内容块解包用例)。

- [ ] **Step 5: 提交**

```powershell
git add potry-ai-agent/tool_system/__init__.py potry-ai-agent/tool_system/spec.py potry-ai-agent/tool_system/formatter.py potry-ai-agent/tests/test_tool_spec.py
git commit -m "feat(ch07): add tool spec, schema validation and result formatter"
```

---

### Task 4: 插件热加载与统一工具目录

**Files:**
- Create: `potry-ai-agent/tool_system/plugins.py`
- Create: `potry-ai-agent/tool_system/catalog.py`
- Create: `potry-ai-agent/tools/extensions/poem_length.py`
- Test: `potry-ai-agent/tests/test_tool_catalog.py`

- [ ] **Step 1: 写失败测试**

新建 `potry-ai-agent/tests/test_tool_catalog.py`：

```python
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
        llm_base_url="http://fake", llm_api_key="CONFIGURE_LOCALLY", llm_model="fake",
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
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_catalog.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'tool_system.catalog'`。

- [ ] **Step 3: 实现插件加载器**

新建 `potry-ai-agent/tool_system/plugins.py`：

```python
"""内置工具插件热加载:扫描目录、按 mtime 载入/重载/卸载。"""
import importlib.util
import sys
from pathlib import Path


class PluginLoader:
    def __init__(self, plugin_dir: str | Path) -> None:
        self._dir = Path(plugin_dir)
        self._loaded: dict[str, tuple[int, str, list[str]]] = {}

    async def refresh(self, catalog) -> None:
        current: dict[str, int] = {}
        if self._dir.is_dir():
            for path in sorted(self._dir.glob("*.py")):
                if path.name.startswith("_"):
                    continue
                current[str(path.resolve())] = path.stat().st_mtime_ns

        for key in list(self._loaded):
            if key not in current:
                catalog.unregister_plugin(key)
                self._loaded.pop(key, None)
                print(f"[tools] plugin unload {Path(key).name}")

        for key, mtime in current.items():
            old = self._loaded.get(key)
            if old is not None and old[0] == mtime:
                continue
            if old is not None:
                catalog.unregister_plugin(key)
            module_name, names = self._load(key, mtime, catalog)
            # 失败也记 mtime,避免每次 get_tools 重复刷同样的错误
            self._loaded[key] = (mtime, module_name, names)

    def _load(self, key: str, mtime: int, catalog) -> tuple[str, list[str]]:
        path = Path(key)
        module_name = f"plugin_{path.stem}_{mtime}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                raise ImportError("无法创建模块规格")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            register = getattr(module, "register", None)
            if not callable(register):
                raise AttributeError("缺少 register(catalog) 函数")
            catalog.begin_plugin(key)
            try:
                register(catalog)
            finally:
                catalog.end_plugin()
            names = sorted(catalog.plugin_tool_names(key))
            print(f"[tools] plugin load {path.name}: {', '.join(names) or '(none)'}")
            return module_name, names
        except Exception as exc:  # noqa: BLE001 - 单个插件失败不影响其它工具
            catalog.unregister_plugin(key)
            sys.modules.pop(module_name, None)
            print(f"[tools] plugin fail {path.name}: {str(exc)[:200]}")
            return "", []
```

- [ ] **Step 4: 实现统一目录**

新建 `potry-ai-agent/tool_system/catalog.py`：

```python
"""统一工具表:内置 + 插件 + MCP,负责刷新、查询、执行与权限判定。"""
import asyncio
from pathlib import Path

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
        )
```

- [ ] **Step 5: 实现样例插件**

新建 `potry-ai-agent/tools/extensions/poem_length.py`：

```python
"""样例只读插件:统计诗文正文字数。新增此文件无需改核心代码即可被 Agent 使用。"""
from langchain_core.tools import tool

_PUNCT = set("，。！？；：、“”‘’《》（）.,!?;:\"'()[]{}—…· \t\n\r")


@tool
def poem_length(text: str) -> dict:
    """统计一段诗文的字数(不计空白与常用标点)。

    Args:
        text: 诗文原文
    """
    count = len([ch for ch in text if ch.strip() and ch not in _PUNCT])
    return {"ok": True, "found": True, "count": count, "text": text}


def register(catalog) -> None:
    catalog.register_builtin(poem_length)
```

- [ ] **Step 6: 跑测试确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_catalog.py -v
```

Expected: 8 passed。

- [ ] **Step 7: 提交**

```powershell
git add potry-ai-agent/tool_system/plugins.py potry-ai-agent/tool_system/catalog.py potry-ai-agent/tools/extensions/poem_length.py potry-ai-agent/tests/test_tool_catalog.py
git commit -m "feat(ch07): add hot-load plugin loader and unified tool catalog"
```

---

### Task 5: 执行引擎(校验 / 权限 / 超时重试 / 审计)

**Files:**
- Create: `potry-ai-agent/tool_system/audit.py`
- Create: `potry-ai-agent/tool_system/engine.py`
- Test: `potry-ai-agent/tests/test_tool_engine.py`

- [ ] **Step 1: 写失败测试**

新建 `potry-ai-agent/tests/test_tool_engine.py`：

```python
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
        llm_base_url="http://fake", llm_api_key="CONFIGURE_LOCALLY", llm_model="fake",
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
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_engine.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'tool_system.engine'`。

- [ ] **Step 3: 实现审计写入**

新建 `potry-ai-agent/tool_system/audit.py`：

```python
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
```

- [ ] **Step 4: 实现执行引擎**

新建 `potry-ai-agent/tool_system/engine.py`：

```python
"""统一执行引擎:JSON Schema 校验 → 权限门 → 超时/重试 → 格式化 → 审计。"""
import asyncio
import time

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

    async def execute(self, spec: ToolSpec, args: dict, invocation: ToolInvocation) -> dict:
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
                    raw = await asyncio.wait_for(spec.tool.ainvoke(dict(args)), timeout=timeout)
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
```

- [ ] **Step 5: 跑测试确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_engine.py -v
```

Expected: 11 passed(执行时补了 `test_tool_returned_business_error_message_is_preserved` 回归用例)。

- [ ] **Step 6: 提交**

```powershell
git add potry-ai-agent/tool_system/audit.py potry-ai-agent/tool_system/engine.py potry-ai-agent/tests/test_tool_engine.py
git commit -m "feat(ch07): add tool execution engine with validation, permission, retry and audit"
```

---

### Task 6: MCP Provider 与两个业务 MCP Server

**Files:**
- Create: `potry-ai-agent/tool_system/mcp_provider.py`
- Create: `potry-ai-agent/mcp_servers/__init__.py`
- Create: `potry-ai-agent/mcp_servers/poetry_archive_server.py`
- Create: `potry-ai-agent/mcp_servers/judgement_server.py`
- Test: `potry-ai-agent/tests/test_mcp_provider.py`
- Test: `potry-ai-agent/tests/test_mcp_servers.py`

- [ ] **Step 1: 写失败测试**

新建 `potry-ai-agent/tests/test_mcp_provider.py`：

```python
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
```

新建 `potry-ai-agent/tests/test_mcp_servers.py`：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_provider.py tests/test_mcp_servers.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'tool_system.mcp_provider'`。

- [ ] **Step 3: 实现 MCP Provider**

新建 `potry-ai-agent/tool_system/mcp_provider.py`：

```python
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
```

- [ ] **Step 4: 实现两个 MCP Server**

新建 `potry-ai-agent/mcp_servers/__init__.py`（空文件）。

新建 `potry-ai-agent/mcp_servers/poetry_archive_server.py`：

```python
"""诗词档案 MCP Server(9101):独立进程 + mock 数据,不接 MySQL、不建表。

启动:
    .\.venv\Scripts\python.exe mcp_servers\poetry_archive_server.py
"""
import random

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "poetry-archive", host="127.0.0.1", port=9101,
    stateless_http=True, json_response=True,
)

POEMS = {
    "静夜思": {
        "title": "静夜思", "writer": "李白", "dynasty": "唐",
        "content": "床前明月光,疑是地上霜。举头望明月,低头思故乡。",
        "translation": "明亮的月光洒在床前,好像地上泛起了一层白霜;抬头望月,低头思乡。",
    },
    "春望": {
        "title": "春望", "writer": "杜甫", "dynasty": "唐",
        "content": "国破山河在,城春草木深。感时花溅泪,恨别鸟惊心。",
        "translation": "国都沦陷而山河依旧,春日的长安城草木丛生;感伤时局,见花落泪。",
    },
    "登鹳雀楼": {
        "title": "登鹳雀楼", "writer": "王之涣", "dynasty": "唐",
        "content": "白日依山尽,黄河入海流。欲穷千里目,更上一层楼。",
        "translation": "夕阳依山而落,黄河奔流入海;想看得更远,就要再登高一层。",
    },
    "江雪": {
        "title": "江雪", "writer": "柳宗元", "dynasty": "唐",
        "content": "千山鸟飞绝,万径人踪灭。孤舟蓑笠翁,独钓寒江雪。",
        "translation": "群山不见飞鸟,万径没有人迹;孤舟上一位蓑笠老翁,独钓寒江雪。",
    },
    "山居秋暝": {
        "title": "山居秋暝", "writer": "王维", "dynasty": "唐",
        "content": "空山新雨后,天气晚来秋。明月松间照,清泉石上流。",
        "translation": "空山新雨过后,傍晚秋意渐浓;明月照松林,清泉流石上。",
    },
}

POETS = {
    "李白": {"name": "李白", "dynasty": "唐", "courtesy": "太白", "intro": "唐代浪漫主义诗人,号青莲居士。"},
    "杜甫": {"name": "杜甫", "dynasty": "唐", "courtesy": "子美", "intro": "唐代现实主义诗人,被尊为诗圣。"},
    "王维": {"name": "王维", "dynasty": "唐", "courtesy": "摩诘", "intro": "唐代山水田园诗人,诗中有画。"},
    "柳宗元": {"name": "柳宗元", "dynasty": "唐", "courtesy": "子厚", "intro": "唐代文学家,唐宋八大家之一。"},
    "王之涣": {"name": "王之涣", "dynasty": "唐", "courtesy": "季凌", "intro": "唐代边塞诗人,存诗不多而名篇极盛。"},
}


@mcp.tool()
def poem_archive_lookup(title: str = "", poet: str = "") -> dict:
    """查询诗词档案:按诗题或诗人匹配,返回原文、译文与档案状态。"""
    matched = [
        p for p in POEMS.values()
        if (title and title in p["title"]) or (poet and poet in p["writer"])
    ]
    item = dict(random.choice(matched or list(POEMS.values())))
    item["archive_status"] = random.choice(["在库", "整理中"])
    return {"ok": True, "found": True, "archive": item}


@mcp.tool()
def poet_archive_lookup(name: str) -> dict:
    """查询诗人档案:按姓名匹配,返回朝代、字号与简介。"""
    item = POETS.get(name) or random.choice(list(POETS.values()))
    return {"ok": True, "found": True, "poet": dict(item)}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

新建 `potry-ai-agent/mcp_servers/judgement_server.py`：

```python
"""判定与纠错 MCP Server(9102):独立进程 + mock 数据,不落库。

启动:
    .\.venv\Scripts\python.exe mcp_servers\judgement_server.py
"""
import random

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "judgement", host="127.0.0.1", port=9102,
    stateless_http=True, json_response=True,
)

_CONCLUSIONS = {
    ("meter", "pass"): "句式与平仄合规,符合近体诗要求。",
    ("meter", "fail"): "句数或平仄不合,建议按近体诗规则调整。",
    ("verify", "pass"): "作者、原文与权威数据一致。",
    ("verify", "fail"): "发现作者或原文与权威数据不一致,需复核。",
}


@mcp.tool()
def judgement_status_lookup(title: str) -> dict:
    """查询某首诗最近一次格律/校勘判定记录(类型、结果、结论、日期)。"""
    kind = random.choice(["meter", "verify"])
    result = random.choice(["pass", "fail"])
    return {
        "ok": True,
        "found": True,
        "judgement": {
            "title": title,
            "kind": kind,
            "result": result,
            "conclusion": _CONCLUSIONS[(kind, result)],
            "date": f"2026-10-{random.randint(10, 22)}",
        },
    }


@mcp.tool()
def correction_progress_lookup(ticket_no: str) -> dict:
    """查询纠错单处理进度(received/reviewing/done)。"""
    status = random.choice(["received", "reviewing", "done"])
    note = {
        "received": "已受理,等待编辑复核。",
        "reviewing": "编辑正在复核原文与译文。",
        "done": "复核完成,已更新词条。",
    }[status]
    return {
        "ok": True,
        "found": True,
        "progress": {
            "ticket_no": ticket_no,
            "status": status,
            "updated_at": f"2026-10-{random.randint(10, 22)}",
            "note": note,
        },
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

- [ ] **Step 5: 跑测试确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_provider.py tests/test_mcp_servers.py -v
```

Expected: 8 passed。

- [ ] **Step 6: 提交**

```powershell
git add potry-ai-agent/tool_system/mcp_provider.py potry-ai-agent/mcp_servers potry-ai-agent/tests/test_mcp_provider.py potry-ai-agent/tests/test_mcp_servers.py
git commit -m "feat(ch07): add mcp provider and two mock business mcp servers"
```

---

### Task 7: `create_ticket` 内置写工具

**Files:**
- Create: `potry-ai-agent/tools/ticket_tool.py`
- Test: `potry-ai-agent/tests/test_ticket_tool.py`

- [ ] **Step 1: 写失败测试**

新建 `potry-ai-agent/tests/test_ticket_tool.py`：

```python
"""建单工具:JSON Schema(枚举/必填/最小长度)、上下文落库、返回工单号。"""
import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app_storage import AppBase, Ticket
from tool_system.spec import ToolInvocation, bind_invocation, reset_invocation


def test_ticket_tool_schema_has_enum_and_min_length():
    from tools.ticket_tool import create_ticket
    from tool_system.spec import schema_of

    schema = schema_of(create_ticket)
    props = schema["properties"]
    assert props["ticket_type"]["enum"] == ["内容纠错", "功能异常", "其他"]
    assert props["description"]["minLength"] == 4
    assert set(schema["required"]) == {"ticket_type", "description"}


def test_create_ticket_writes_row_with_invocation_context(monkeypatch, tmp_path):
    import tools.ticket_tool as ticket_module

    engine = create_engine(f"sqlite:///{tmp_path / 'ticket.db'}")
    AppBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(ticket_module, "_storage_factory", lambda: factory)

    token = bind_invocation(ToolInvocation(
        session_id="s-ticket", tool_call_id="c1", userid="u-1",
    ))
    try:
        result = asyncio.run(ticket_module.create_ticket.ainvoke({
            "ticket_type": "内容纠错",
            "description": "《静夜思》原文有错字",
        }))
    finally:
        reset_invocation(token)

    assert result["ok"] is True
    assert result["ticket_no"] == "TK000001"
    with factory() as session:
        row = session.get(Ticket, result["ticket_id"])
    assert row.session_id == "s-ticket"
    assert row.userid == "u-1"
    assert row.ticket_type == "内容纠错"
    assert row.description == "《静夜思》原文有错字"
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ticket_tool.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'tools.ticket_tool'`。

- [ ] **Step 3: 实现工具**

新建 `potry-ai-agent/tools/ticket_tool.py`：

```python
"""建工单工具:本系统唯一的写操作;必须经前端确认后由执行引擎放行。"""
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy.orm import sessionmaker

from app_storage import AppStorage
from config import load_settings
from db import get_engine
from tool_system.spec import current_invocation


class CreateTicketInput(BaseModel):
    ticket_type: Literal["内容纠错", "功能异常", "其他"] = Field(
        description="工单类型:内容纠错 / 功能异常 / 其他"
    )
    description: str = Field(
        min_length=4,
        description="用户的问题描述,尽量保留用户原话,至少 4 个字",
    )


def _storage_factory() -> sessionmaker:
    """单一入口:测试可 monkeypatch 注入内存/文件库。"""
    return sessionmaker(bind=get_engine(load_settings().mysql_url))


@tool("create_ticket", args_schema=CreateTicketInput)
async def create_ticket(ticket_type: str, description: str) -> dict:
    """创建工单。**仅在用户明确要求建工单/提交纠错单/反馈问题时调用**。

    用户只是抱怨、或问题描述还不清楚时,先追问补齐,不得编造描述。
    创建成功后返回 ticket_no,回复用户时必须把工单号原样告知。

    Args:
        ticket_type: 工单类型:内容纠错 / 功能异常 / 其他
        description: 用户的问题描述(至少 4 个字,尽量保留用户原话)
    """
    invocation = current_invocation()
    try:
        ticket_id, ticket_no = AppStorage(_storage_factory()).add_ticket(
            ticket_type=ticket_type,
            description=description,
            session_id=invocation.session_id or None,
            userid=invocation.userid,
        )
    except Exception as exc:  # noqa: BLE001 - 统一走契约失败分支
        return {"ok": False, "error": str(exc)[:200]}
    return {"ok": True, "ticket_id": ticket_id, "ticket_no": ticket_no}
```

- [ ] **Step 4: 跑测试确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ticket_tool.py -v
```

Expected: 2 passed。

- [ ] **Step 5: 提交**

```powershell
git add potry-ai-agent/tools/ticket_tool.py potry-ai-agent/tests/test_ticket_tool.py
git commit -m "feat(ch07): add create_ticket write tool"
```

---

### Task 8: 配置、状态、依赖与 Agent 接入

**Files:**
- Modify: `potry-ai-agent/config.py`
- Modify: `potry-ai-agent/workflow/state.py`
- Modify: `potry-ai-agent/workflow/deps.py`
- Modify: `potry-ai-agent/workflow/agent_react.py`
- Modify: `potry-ai-agent/main.py`
- Modify: `potry-ai-agent/tests/test_workflow_agent_react.py`
- Modify: `potry-ai-agent/tests/test_workflow_graph.py`
- Modify: `potry-ai-agent/tests/test_context_cascade.py`

- [ ] **Step 1: 更新依赖装配测试**

先改 `tests/test_workflow_agent_react.py`：

1. 导入改为：

```python
from config import Settings
from tool_system.catalog import ToolCatalog
from tool_system.engine import ToolEngine
from workflow.agent_react import agent_node, should_continue, tool_node
from workflow.deps import WorkflowDeps, configure
```

2. 把 `make_registry()` 替换为：

```python
class FakeAudit:
    def __init__(self):
        self.rows = []

    async def record(self, **fields):
        self.rows.append(fields)


def make_catalog():
    calls = []

    @tool
    def query_poem(keyword: str) -> dict:
        """查诗词。

        Args:
            keyword: 关键词
        """
        calls.append(keyword)
        return {"ok": True, "found": True, "poem": {"title": "静夜思"}}

    settings = make_settings()
    audit = FakeAudit()
    catalog = ToolCatalog(
        engine=ToolEngine(settings, audit), audit=audit,
        plugin_dir=None, mcp_provider=None,
    )
    catalog.register_builtin(query_poem)
    return catalog, calls
```

3. 把 `_deps(llm, registry, **over)` 改为：

```python
def _deps(llm, catalog, **over):
    deps = WorkflowDeps(make_settings(**over), llm, catalog, None, None)
    configure(deps)
    return deps
```

4. 全文把 `registry, calls = make_registry()` 替换为 `catalog, calls = make_catalog()`，把 `_deps(..., registry, ...)` 替换为 `_deps(..., catalog, ...)`。

5. `test_tool_node_marks_error_status_on_tool_failure` 内改为：

```python
    settings = make_settings()
    audit = FakeAudit()
    catalog = ToolCatalog(
        engine=ToolEngine(settings, audit), audit=audit,
        plugin_dir=None, mcp_provider=None,
    )
    catalog.register_builtin(boom_tool)
    _deps(ScriptedLLM([]), catalog)
```

再改 `tests/test_workflow_graph.py`：

1. 导入改为：

```python
from config import Settings
from tool_system.catalog import ToolCatalog
from tool_system.engine import ToolEngine
from workflow.deps import WorkflowDeps, configure
from workflow.graph import build_graph, open_checkpointer
```

2. 把 `make_registry()` 替换为：

```python
class FakeAudit:
    def __init__(self):
        self.rows = []

    async def record(self, **fields):
        self.rows.append(fields)


def make_catalog():
    calls = []

    @tool
    def query_poet(name: str) -> dict:
        """查诗人。

        Args:
            name: 诗人名
        """
        calls.append(name)
        return {"ok": True, "found": True, "poet": {"name": "李白"}}

    settings = make_settings()
    audit = FakeAudit()
    catalog = ToolCatalog(
        engine=ToolEngine(settings, audit), audit=audit,
        plugin_dir=None, mcp_provider=None,
    )
    catalog.register_builtin(query_poet)
    return catalog, calls
```

3. `_wire` 改为：

```python
def _wire(llm, catalog, knowledge=None, chat=None, **over):
    deps = WorkflowDeps(make_settings(**over), llm, catalog, knowledge, chat)
    configure(deps)
    return deps
```

4. 全文 `registry, calls = make_registry()` → `catalog, calls = make_catalog()`；`_wire(..., registry, ...)` → `_wire(..., catalog, ...)`。

再改 `tests/test_context_cascade.py`：删除 `from tools.registry import ToolRegistry`，并替换导入与装配：

```python
from tool_system.audit import AuditWriter
from tool_system.catalog import ToolCatalog
from tool_system.engine import ToolEngine
```

```python
    settings = make_settings()
    audit = AuditWriter(None)
    catalog = ToolCatalog(
        engine=ToolEngine(settings, audit), audit=audit,
        plugin_dir=None, mcp_provider=None,
    )
    configure(WorkflowDeps(settings, llm, catalog, None, storage))
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_agent_react.py tests/test_workflow_graph.py tests/test_context_cascade.py -q
```

Expected: FAIL，`TypeError: WorkflowDeps.__init__() got an unexpected keyword argument` 或 `AttributeError: 'ToolRegistry' object has no attribute ...`。

- [ ] **Step 3: 更新配置**

在 `config.py` 默认值区追加：

```python
# Ch07:MCP 接入默认值(与 Settings 共用,单一来源)
_DEFAULT_MCP_POETRY_ARCHIVE_URL = "http://127.0.0.1:9101/mcp"
_DEFAULT_MCP_JUDGEMENT_URL = "http://127.0.0.1:9102/mcp"
_DEFAULT_MCP_TOOL_REFRESH_SECONDS = 5.0
_DEFAULT_MCP_CONNECT_TIMEOUT_SECONDS = 2.0
```

在 `Settings` 字段区追加：

```python
    mcp_poetry_archive_url: str = _DEFAULT_MCP_POETRY_ARCHIVE_URL
    mcp_judgement_url: str = _DEFAULT_MCP_JUDGEMENT_URL
    mcp_tool_refresh_seconds: float = _DEFAULT_MCP_TOOL_REFRESH_SECONDS
    mcp_connect_timeout_seconds: float = _DEFAULT_MCP_CONNECT_TIMEOUT_SECONDS
```

在 `load_settings` 的 `try` 区追加：

```python
        mcp_tool_refresh_seconds = float(
            os.getenv("MCP_TOOL_REFRESH_SECONDS") or str(_DEFAULT_MCP_TOOL_REFRESH_SECONDS)
        )
        mcp_connect_timeout_seconds = float(
            os.getenv("MCP_CONNECT_TIMEOUT_SECONDS") or str(_DEFAULT_MCP_CONNECT_TIMEOUT_SECONDS)
        )
```

在 `return Settings(...)` 参数区追加：

```python
        mcp_poetry_archive_url=(
            os.getenv("MCP_POETRY_ARCHIVE_URL") or _DEFAULT_MCP_POETRY_ARCHIVE_URL
        ),
        mcp_judgement_url=(
            os.getenv("MCP_JUDGEMENT_URL") or _DEFAULT_MCP_JUDGEMENT_URL
        ),
        mcp_tool_refresh_seconds=mcp_tool_refresh_seconds,
        mcp_connect_timeout_seconds=mcp_connect_timeout_seconds,
```

在数值校验区追加：

```python
    if mcp_tool_refresh_seconds <= 0:
        raise RuntimeError(f"MCP_TOOL_REFRESH_SECONDS 必须为正数(当前: {mcp_tool_refresh_seconds})")
    if mcp_connect_timeout_seconds <= 0:
        raise RuntimeError(f"MCP_CONNECT_TIMEOUT_SECONDS 必须为正数(当前: {mcp_connect_timeout_seconds})")
```

- [ ] **Step 4: 更新状态与依赖**

`workflow/state.py` 的 `PER_TURN_RESET` 追加：

```python
    # ---------- Ch07 ----------
    "ticket_confirmed": None,
    "ticket_preview": None,
```

`WorkflowState` 追加：

```python
    # ---------- Ch07 ----------
    ticket_confirmed: bool | None
    ticket_preview: dict | None
```

`workflow/deps.py` 改为：

```python
class WorkflowDeps:
    def __init__(self, settings, llm, tools, knowledge_storage, chat_storage) -> None:
        self.settings = settings
        self.llm = llm
        self.tools = tools
        self.knowledge_storage = knowledge_storage
        self.chat_storage = chat_storage
        self.budget = derive_budget(settings)
        self.max_iter = settings.max_agent_steps
        self.max_tokens = settings.workflow_max_tokens
```

- [ ] **Step 5: 更新 Agent 与工具节点**

`workflow/agent_react.py` 顶部模块 docstring 的「工具集 = Ch02 三个诗词工具 + submit_feedback」改为：

```text
工具集 = ToolCatalog(内置 + 热加载插件 + MCP);`submit_feedback` 已从 Agent 清单移除。
```

`agent_node` 的绑定改为：

```python
        ai = await deps.llm.bind_tools(await deps.tools.get_tools()).ainvoke(msgs)
```

`tool_node` 整个函数替换为：

```python
async def tool_node(state: dict) -> dict:
    """工具节点:统一走 ToolCatalog 执行,回灌 ToolMessage 并记录轨迹。"""
    deps = get_deps()
    last = (state.get("messages") or [])[-1]
    tool_messages, traces = [], []
    preview_call_id = (state.get("ticket_preview") or {}).get("toolCallId")
    for tc in getattr(last, "tool_calls", None) or []:
        started = time.monotonic()
        approved = bool(state.get("ticket_confirmed")) and tc["id"] == preview_call_id
        result = await deps.tools.execute(
            tc["name"], tc["args"],
            session_id=state.get("session_id") or "",
            userid=state.get("userid"),
            tool_call_id=tc["id"],
            approved=approved,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        tool_messages.append(make_tool_message(tc["id"], tc["name"], result))
        traces.append(
            {
                "tool": tc["name"],
                "args": tc["args"],
                "tool_call_id": tc["id"],
                "content": tool_messages[-1].content,
                "durationMs": duration_ms,
                "status": "done" if result.get("ok") else "error",
            }
        )
    out: dict = {
        "messages": tool_messages,
        "tool_trace": (state.get("tool_trace") or []) + traces,
    }
    if state.get("ticket_confirmed") is not None:
        out["ticket_confirmed"] = None      # 确认态只放行一次,不跨工具/跨轮复用
        out["ticket_preview"] = None
    return out
```

`should_continue` 替换为：

```python
def should_continue(state: dict) -> str:
    """ReAct 条件边:需确认的写工具先走 ticket_confirm,其余进工具节点。"""
    deps = get_deps()
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if not getattr(last, "tool_calls", None):
        return "log"
    if state.get("iterations", 0) >= deps.max_iter or state.get("tokens_used", 0) >= deps.max_tokens:
        return "log"
    for tc in last.tool_calls:
        if deps.tools.requires_confirmation(tc["name"]) and deps.tools.validate_args(tc["name"], tc["args"]):
            return "ticket_confirm"
    return "tool_node"
```

- [ ] **Step 6: 更新 main.py 装配**

把 `main.py` 的导入区：

```python
from tools.feedback_tool import submit_feedback
from tools.poetry_tools import query_dynasty_poems, query_poem, query_poet
from tools.registry import ToolRegistry
```

改为：

```python
from tools.poetry_tools import query_dynasty_poems, query_poem, query_poet
from tools.registry import ToolRegistry
from tools.ticket_tool import create_ticket
from tool_system.audit import AuditWriter
from tool_system.catalog import ToolCatalog
from tool_system.engine import ToolEngine
from tool_system.mcp_provider import McpProvider
```

把原 `workflow_registry` 装配段：

```python
workflow_registry = ToolRegistry(
    timeout=settings.tool_timeout_seconds,
    max_retries=settings.tool_max_retries,
)
for _t in (query_poem, query_poet, query_dynasty_poems, submit_feedback):
    workflow_registry.register(_t)
app_storage = AppStorage(session_factory)
knowledge_storage = KnowledgeStorage(session_factory)
workflow_llm = build_llm(settings)
workflow_deps = WorkflowDeps(settings, workflow_llm, workflow_registry, knowledge_storage, storage)
configure_workflow(workflow_deps)
```

替换为：

```python
app_storage = AppStorage(session_factory)
knowledge_storage = KnowledgeStorage(session_factory)
workflow_llm = build_llm(settings)

# Ch07 工具系统:内置登记在启动时完成;插件与 MCP 在每次 get_tools 时动态刷新。
tool_audit = AuditWriter(app_storage)
tool_engine = ToolEngine(settings, tool_audit)
mcp_provider = McpProvider(
    {
        "poetry_archive": settings.mcp_poetry_archive_url,
        "judgement": settings.mcp_judgement_url,
    },
    ttl=settings.mcp_tool_refresh_seconds,
    connect_timeout=settings.mcp_connect_timeout_seconds,
)
workflow_tools = ToolCatalog(
    engine=tool_engine,
    audit=tool_audit,
    plugin_dir=Path(__file__).parent / "tools" / "extensions",
    mcp_provider=mcp_provider,
)
workflow_tools.register_builtin(
    query_poet, permission="read", result_fields=("ok", "found", "poet", "works"),
)
workflow_tools.register_builtin(
    query_dynasty_poems, permission="read", result_fields=("ok", "found", "count", "titles"),
)
workflow_tools.register_builtin(
    create_ticket, permission="write", result_fields=("ok", "ticket_id", "ticket_no"),
)
workflow_deps = WorkflowDeps(settings, workflow_llm, workflow_tools, knowledge_storage, storage)
configure_workflow(workflow_deps)
```

- [ ] **Step 7: 更新接口测试中的工具清单断言**

把 `tests/test_workflow_endpoint.py` 的 `test_workflow_registry_isolated_from_chat_registry` 替换为：

```python
@pytest.mark.asyncio
async def test_workflow_tools_isolated_from_chat_registry(monkeypatch):
    monkeypatch.setattr(main.workflow_tools, "_mcp_provider", None)
    wf = {t.name for t in await main.workflow_tools.get_tools()}
    chat = {t.name for t in main.registry.get_tools()}
    assert {"query_poet", "query_dynasty_poems", "create_ticket", "poem_length"} <= wf
    assert "query_poem" not in wf
    assert "submit_feedback" not in wf
    assert chat == {"query_poem", "query_poet", "query_dynasty_poems"}
```

并在文件顶部补 `import pytest`。

- [ ] **Step 8: 跑测试确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_agent_react.py tests/test_workflow_graph.py tests/test_context_cascade.py tests/test_workflow_endpoint.py -q
```

Expected: 全部通过。

- [ ] **Step 9: 提交**

```powershell
git add potry-ai-agent/config.py potry-ai-agent/workflow/state.py potry-ai-agent/workflow/deps.py potry-ai-agent/workflow/agent_react.py potry-ai-agent/main.py potry-ai-agent/tests/test_workflow_agent_react.py potry-ai-agent/tests/test_workflow_graph.py potry-ai-agent/tests/test_context_cascade.py potry-ai-agent/tests/test_workflow_endpoint.py
git commit -m "feat(ch07): wire tool catalog into workflow agent and config"
```

---

### Task 9: `ticket_confirm` 节点与图条件边

**Files:**
- Modify: `potry-ai-agent/workflow/nodes.py`
- Modify: `potry-ai-agent/workflow/graph.py`
- Test: `potry-ai-agent/tests/test_ticket_flow.py`

- [ ] **Step 1: 写失败测试**

新建 `potry-ai-agent/tests/test_ticket_flow.py`：

```python
"""建单 interrupt 流:确认落票、取消权限拒绝、确认态不跨轮、should_continue 路由。"""
import asyncio

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app_storage import AppBase, Ticket
from config import Settings
from tool_system.catalog import ToolCatalog
from tool_system.engine import ToolEngine
from tool_system.spec import PERMISSION_READ, ToolSpec
from workflow.agent_react import should_continue, tool_node
from workflow.deps import WorkflowDeps, configure
from workflow.nodes import ticket_confirm_node
from workflow.state import PER_TURN_RESET, WorkflowState


class FakeAudit:
    def __init__(self):
        self.rows = []

    async def record(self, **fields):
        self.rows.append(fields)


def make_settings(**over):
    base = dict(
        llm_base_url="http://fake", llm_api_key="CONFIGURE_LOCALLY", llm_model="fake",
        history_max_tokens=2000, llm_temperature=0.7,
        mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
        tool_timeout_seconds=1.0, tool_max_retries=0,
    )
    base.update(over)
    return Settings(**base)


def _ticket_call(call_id="tc1", description="《静夜思》原文有错字"):
    return {
        "name": "create_ticket",
        "args": {"ticket_type": "内容纠错", "description": description},
        "id": call_id, "type": "tool_call",
    }


async def _setup(monkeypatch, tmp_path):
    import tools.ticket_tool as ticket_module

    engine = create_engine(f"sqlite:///{tmp_path / 'flow.db'}")
    AppBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(ticket_module, "_storage_factory", lambda: factory)

    audit = FakeAudit()
    settings = make_settings()
    catalog = ToolCatalog(
        engine=ToolEngine(settings, audit), audit=audit,
        plugin_dir=None, mcp_provider=None,
    )
    catalog.register_builtin(ticket_module.create_ticket, permission="write")
    deps = WorkflowDeps(settings, None, catalog, None, None)
    configure(deps)
    await catalog.get_tools()          # 独立小图不经过 agent_node,这里先填充 _merged
    return catalog, audit, factory


def _graph():
    builder = StateGraph(WorkflowState)
    builder.add_node("ticket_confirm", ticket_confirm_node)
    builder.add_node("tool_node", tool_node)
    builder.add_edge(START, "ticket_confirm")
    builder.add_edge("ticket_confirm", "tool_node")
    builder.add_edge("tool_node", END)
    return builder.compile(checkpointer=InMemorySaver())


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    configure(None)


def test_per_turn_reset_clears_ticket_state():
    assert PER_TURN_RESET["ticket_confirmed"] is None
    assert PER_TURN_RESET["ticket_preview"] is None


def test_should_continue_routes_valid_ticket_to_confirm():
    catalog, _, _ = _setup_dummy()
    state = {"messages": [AIMessage(content="", tool_calls=[_ticket_call()])],
             "iterations": 1, "tokens_used": 10}
    assert should_continue(state) == "ticket_confirm"
    bad = {"messages": [AIMessage(content="", tool_calls=[_ticket_call(description="短")])],
           "iterations": 1, "tokens_used": 10}
    assert should_continue(bad) == "tool_node"


def _setup_dummy():
    audit = FakeAudit()
    settings = make_settings()
    catalog = ToolCatalog(
        engine=ToolEngine(settings, audit), audit=audit,
        plugin_dir=None, mcp_provider=None,
    )

    from tools.ticket_tool import create_ticket
    catalog.register_builtin(create_ticket, permission="write")
    configure(WorkflowDeps(settings, None, catalog, None, None))
    asyncio.run(catalog.get_tools())
    return catalog, audit, None


@pytest.mark.asyncio
async def test_confirm_flow_writes_ticket_and_audits_success(monkeypatch, tmp_path):
    catalog, audit, factory = await _setup(monkeypatch, tmp_path)
    graph = _graph()
    config = {"configurable": {"thread_id": "confirm-1"}}
    first = await graph.ainvoke(
        {"session_id": "s1", "userid": "u1",
         "messages": [AIMessage(content="", tool_calls=[_ticket_call()])]},
        config=config,
    )
    assert "__interrupt__" in first
    assert first["__interrupt__"][0].value["action"] == "confirm_ticket"
    assert first["__interrupt__"][0].value["preview"]["ticketType"] == "内容纠错"
    with factory() as session:
        assert session.execute(select(Ticket)).scalars().all() == []

    final = await graph.ainvoke(Command(resume={"confirmed": True}), config=config)
    assert final["ticket_confirmed"] is None
    assert audit.rows[-1]["status"] == "success"
    assert audit.rows[-1]["tool_name"] == "create_ticket"
    with factory() as session:
        tickets = session.execute(select(Ticket)).scalars().all()
    assert len(tickets) == 1
    assert tickets[0].ticket_no == "TK000001"


@pytest.mark.asyncio
async def test_cancel_flow_writes_no_ticket_and_audits_denied(monkeypatch, tmp_path):
    catalog, audit, factory = await _setup(monkeypatch, tmp_path)
    graph = _graph()
    config = {"configurable": {"thread_id": "cancel-1"}}
    await graph.ainvoke(
        {"session_id": "s2", "messages": [AIMessage(content="", tool_calls=[_ticket_call()])]},
        config=config,
    )
    final = await graph.ainvoke(Command(resume={"confirmed": False}), config=config)
    assert final["messages"][-1].content
    assert audit.rows[-1]["status"] == "permission_denied"
    assert audit.rows[-1]["retry_count"] == 0
    with factory() as session:
        assert session.execute(select(Ticket)).scalars().all() == []


@pytest.mark.asyncio
async def test_engine_denies_write_when_confirmation_bypassed():
    audit = FakeAudit()
    settings = make_settings()
    catalog = ToolCatalog(
        engine=ToolEngine(settings, audit), audit=audit,
        plugin_dir=None, mcp_provider=None,
    )
    from tools.ticket_tool import create_ticket
    catalog.register_builtin(create_ticket, permission="write")
    await catalog.get_tools()
    result = await catalog.execute(
        "create_ticket",
        {"ticket_type": "其他", "description": "绕过确认直接执行"},
        session_id="s3", tool_call_id="tc9", approved=False,
    )
    assert result["error_type"] == "permission_denied"
    assert audit.rows[-1]["status"] == "permission_denied"
```

注意：`test_should_continue_routes_valid_ticket_to_confirm` 使用 `_setup_dummy`，它不碰数据库；`should_continue` 只查 `_merged`，先 `asyncio.run(catalog.get_tools())` 填充。

- [ ] **Step 2: 跑测试确认失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ticket_flow.py -v
```

Expected: FAIL，`ImportError: cannot import name 'ticket_confirm_node'`。

- [ ] **Step 3: 实现确认节点**

在 `workflow/nodes.py` 顶部导入区追加：

```python
from langgraph.types import interrupt
```

在文件末尾（`_fmt` 之前或之后均可）追加：

```python
def ticket_confirm_node(state: dict) -> dict:
    """建单人工确认:interrupt 前无副作用;恢复时从节点开头重算预览。"""
    deps = get_deps()
    last = (state.get("messages") or [])[-1]
    call = next(
        tc for tc in (getattr(last, "tool_calls", None) or [])
        if deps.tools.requires_confirmation(tc["name"])
    )
    preview = {
        "ticketType": call["args"].get("ticket_type", ""),
        "description": call["args"].get("description", ""),
        "toolCallId": call["id"],
    }
    decision = interrupt({
        "action": "confirm_ticket",
        "preview": preview,
        "toolCallId": call["id"],
    })
    confirmed = decision.get("confirmed") if isinstance(decision, dict) else bool(decision)
    return {"ticket_confirmed": bool(confirmed), "ticket_preview": preview}
```

- [ ] **Step 4: 更新图**

`workflow/graph.py`：

1. 导入 `ticket_confirm_node`：

```python
from workflow.nodes import (
    after_gate,
    after_resolve,
    after_route,
    after_slot_check,
    classify_node,
    expand_query_node,
    gate_node,
    log_node,
    resolve_node,
    retrieve_node,
    retrieve_policy_node,
    route_node,
    slot_check_node,
    ticket_confirm_node,
)
```

2. 注册节点：

```python
    builder.add_node("ticket_confirm", ticket_confirm_node)
```

3. 条件边映射：

```python
    builder.add_conditional_edges(
        "agent", should_continue,
        {"tool_node": "tool_node", "ticket_confirm": "ticket_confirm", "log": "log"},
    )
```

4. 节点边：

```python
    builder.add_edge("ticket_confirm", "tool_node")
```

- [ ] **Step 5: 跑测试确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ticket_flow.py -v
```

Expected: 5 passed。

- [ ] **Step 6: 跑相关图测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_graph.py tests/test_workflow_agent_react.py -q
```

Expected: 全部通过。

- [ ] **Step 7: 提交**

```powershell
git add potry-ai-agent/workflow/nodes.py potry-ai-agent/workflow/graph.py potry-ai-agent/tests/test_ticket_flow.py
git commit -m "feat(ch07): add ticket confirmation node with langgraph interrupt"
```

---

### Task 10: HTTP interrupt 帧与 `/agent/workflow/resume`

**Files:**
- Modify: `potry-ai-agent/main.py`
- Modify: `potry-ai-agent/tests/test_workflow_endpoint.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_workflow_endpoint.py` 的 `FakeWorkflow` 上方补：

```python
class FakeInterrupt:
    def __init__(self, value):
        self.value = value


class FakeTask:
    def __init__(self, interrupts=()):
        self.interrupts = interrupts


class FakeState:
    def __init__(self, tasks=()):
        self.tasks = tasks
```

把 `FakeWorkflow` 改为：

```python
class FakeWorkflow:
    def __init__(self, final, tasks=()):
        self.final = final
        self.tasks = tasks
        self.records = []

    async def ainvoke(self, payload, config):
        self.records.append((payload, config))
        return self.final

    async def aget_state(self, config):
        return FakeState(self.tasks)
```

在文件末尾追加：

```python
def test_interrupt_emits_confirm_ticket_action_and_awaiting_status(monkeypatch):
    final = {
        "route": "other", "answer": "", "actions": [], "tool_trace": [],
        "__interrupt__": [FakeInterrupt({
            "action": "confirm_ticket",
            "preview": {"ticketType": "内容纠错", "description": "《静夜思》原文有错字"},
            "toolCallId": "tc1",
        })],
    }
    client, _ = _client(monkeypatch, final)
    body = _stream(client, {"sessionId": "s40", "message": "帮我建个工单"})
    assert '"action": "confirm_ticket"' in body
    assert '"ticketType": "内容纠错"' in body
    assert '"status": "awaiting_confirmation"' in body
    assert "event: token" not in body


def test_workflow_rejects_new_message_while_awaiting_confirmation(monkeypatch):
    fake = FakeWorkflow(
        {"answer": ""},
        tasks=(FakeTask(interrupts=(FakeInterrupt({"action": "confirm_ticket"}),)),),
    )
    monkeypatch.setattr(main, "_workflow", fake)
    client = TestClient(main.app)
    resp = client.post("/agent/workflow", json={"sessionId": "s41", "message": "再问一句"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["message"] == "请先确认或取消当前工单"


def test_resume_returns_409_without_pending_interrupt(monkeypatch):
    fake = FakeWorkflow({"answer": "ok"}, tasks=())
    monkeypatch.setattr(main, "_workflow", fake)
    client = TestClient(main.app)
    resp = client.post("/agent/workflow/resume", json={"sessionId": "s42", "confirmed": True})
    assert resp.status_code == 409


def test_resume_confirmed_streams_answer_and_resumes_graph(monkeypatch):
    fake = FakeWorkflow(
        {"route": "other", "answer": "工单已提交,单号 TK000001。",
         "actions": [], "tool_trace": []},
        tasks=(FakeTask(interrupts=(FakeInterrupt({"action": "confirm_ticket"}),)),),
    )
    monkeypatch.setattr(main, "_workflow", fake)
    client = TestClient(main.app)
    with client.stream(
        "POST", "/agent/workflow/resume",
        json={"sessionId": "s43", "confirmed": True},
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    order = [body.index(f"event: {e}") for e in ("meta", "trace", "token", "done")]
    assert order == sorted(order)
    assert "TK000001" in body
    assert '"status": "ok"' in body
    payload, config = fake.records[0]
    assert getattr(payload, "resume", None) == {"confirmed": True}
    assert config == {"configurable": {"thread_id": "s43"}}


def _stream_resume(client, payload):
    with client.stream("POST", "/agent/workflow/resume", json=payload) as resp:
        assert resp.status_code == 200
        return "".join(resp.iter_text())


def test_resume_cancel_streams_cancel_answer(monkeypatch):
    fake = FakeWorkflow(
        {"route": "other", "answer": "好,这次建单已取消。", "actions": [], "tool_trace": []},
        tasks=(FakeTask(interrupts=(FakeInterrupt({"action": "confirm_ticket"}),)),),
    )
    monkeypatch.setattr(main, "_workflow", fake)
    client = TestClient(main.app)
    body = _stream_resume(client, {"sessionId": "s44", "confirmed": False})
    assert "已取消" in body
    assert getattr(fake.records[0][0], "resume", None) == {"confirmed": False}
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_endpoint.py -v
```

Expected: FAIL，`404 Not Found`（resume 路由不存在）或 interrupt 用例失败。

- [ ] **Step 3: 实现 SSE 帧与 resume**

`main.py` 顶部导入区追加：

```python
from langgraph.types import Command
```

在 `/agent/workflow` 路由前插入：

```python
async def _has_pending_interrupt(config: dict) -> bool:
    """该 thread 是否有未 resume 的 interrupt;测试替身无 aget_state 时视为无。"""
    aget_state = getattr(_workflow, "aget_state", None)
    if aget_state is None:
        return False
    try:
        snapshot = await aget_state(config)
    except Exception as exc:  # noqa: BLE001 - 状态查询失败不阻断主流程
        print(f"[wf] aget_state fail: {str(exc)[:160]}")
        return False
    tasks = getattr(snapshot, "tasks", None) or ()
    return any(getattr(task, "interrupts", None) for task in tasks)


def _done_status(final: dict) -> str:
    if final.get("__interrupt__"):
        return "awaiting_confirmation"
    if final.get("pending_subflow"):
        return "awaiting_slot"
    return "ok"


async def _final_frames(final: dict, session_id: str) -> AsyncIterator[bytes]:
    """图跑完后的统一帧序:trace → tool_status* → token* → action?。"""
    yield _sse("trace", _trace_payload(final))
    for trace in final.get("tool_trace") or []:
        yield _sse(
            "tool_status",
            {
                "tool": trace["tool"],
                "status": trace["status"],
                "args": trace["args"],
                "durationMs": trace["durationMs"],
            },
        )
    for piece in _answer_chunks(final.get("answer") or ""):
        yield _sse("token", {"content": piece})
    actions = final.get("actions") or []
    if actions:
        yield _sse("action", {"actions": actions})
    if final.get("pending_subflow"):
        yield _sse("action", {"action": "pick_poem", "candidates": final.get("candidates") or []})
    if final.get("correction_categories"):
        yield _sse("action", {"action": "open_correction_form",
                              "categories": final.get("correction_categories")})
    for item in final.get("__interrupt__") or []:
        value = getattr(item, "value", item)
        if isinstance(value, dict) and value.get("action") == "confirm_ticket":
            yield _sse("action", {
                "action": "confirm_ticket",
                "preview": value.get("preview") or {},
                "toolCallId": value.get("toolCallId"),
            })
```

把 `/agent/workflow` 路由的函数体替换为：

```python
@app.post("/agent/workflow")
async def workflow_chat(req: ChatRequest) -> EventSourceResponse:
    """Ch04 确定性编排入口;Ch07 增补建单确认帧。"""
    if _workflow is None:
        raise HTTPException(status_code=503, detail={"message": "workflow 未就绪(装配失败)"})
    session_id = req.sessionId or uuid4().hex
    config = {"configurable": {"thread_id": session_id}}
    if await _has_pending_interrupt(config):
        raise HTTPException(status_code=409, detail={"message": "请先确认或取消当前工单"})

    async def gen() -> AsyncIterator[bytes]:
        yield _sse("meta", {"sessionId": session_id})
        final: dict = {}
        try:
            final = await _workflow.ainvoke(
                {
                    "session_id": session_id,
                    "userid": req.userId,
                    "user_input": req.message,
                    "selected_poem_id": req.selectedPoemId,
                    "started_at": time.monotonic(),
                    "messages": [],
                    "tool_trace": [],
                },
                config=config,
            )
            async for frame in _final_frames(final, session_id):
                yield frame
        except Exception as exc:  # noqa: BLE001 - 单请求失败不崩服务,补 error 帧
            yield _sse("error", {"message": str(exc)[:200]})
        yield _sse("done", {"sessionId": session_id, "source": _answer_source(final),
                            "status": _done_status(final)})

    return EventSourceResponse(gen())
```

在 `/agent/workflow` 之后追加：

```python
class ResumeRequest(BaseModel):
    sessionId: str
    confirmed: bool


@app.post("/agent/workflow/resume")
async def workflow_resume(req: ResumeRequest) -> EventSourceResponse:
    """前端确认/取消建单:以 Command(resume=...) 放行同一 thread 的 interrupt。"""
    if _workflow is None:
        raise HTTPException(status_code=503, detail={"message": "workflow 未就绪(装配失败)"})
    config = {"configurable": {"thread_id": req.sessionId}}
    if not await _has_pending_interrupt(config):
        raise HTTPException(status_code=409, detail={"message": "当前没有待确认的工单"})

    async def gen() -> AsyncIterator[bytes]:
        yield _sse("meta", {"sessionId": req.sessionId})
        final: dict = {}
        try:
            final = await _workflow.ainvoke(
                Command(resume={"confirmed": req.confirmed}), config=config
            )
            async for frame in _final_frames(final, req.sessionId):
                yield frame
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {"message": str(exc)[:200]})
        yield _sse("done", {"sessionId": req.sessionId, "source": _answer_source(final),
                            "status": _done_status(final)})

    return EventSourceResponse(gen())
```

- [ ] **Step 4: 跑测试确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_endpoint.py -v
```

Expected: 全部通过。

- [ ] **Step 5: 提交**

```powershell
git add potry-ai-agent/main.py potry-ai-agent/tests/test_workflow_endpoint.py
git commit -m "feat(ch07): add interrupt frames and workflow resume endpoint"
```

---

### Task 11: 意图 Prompt 增补与真实模型评估集

**Files:**
- Modify: `potry-ai-agent/prompts.py`
- Modify: `potry-ai-agent/tests/test_prompts.py`
- Create: `potry-ai-agent/evals/ch07_intent_cases.md`
- Create: `potry-ai-agent/evals/run_ch07_intent_eval.py`
- Create: `potry-ai-agent/evals/ch07_ticket_cases.md`
- Create: `potry-ai-agent/evals/run_ch07_ticket_eval.py`

- [ ] **Step 1: 改 Prompt**

在 `prompts.py` 的 `SYSTEM_PROMPT_TEMPLATE` 行为约束末尾追加：

```text
- 只有用户明确说"帮我建工单 / 提交纠错单 / 我要反馈问题"时才可调用 create_ticket;信息不全(缺问题描述)先追问,不得编造;用户只是抱怨或表达不满时不要主动建单。
- 用户明确要求建单且已给出问题描述时,直接调用 create_ticket;描述按用户原话记录,不要替用户核实事实、不要反复追问已验证的信息。
```

在 `INTENT_PROMPT` 的易混边界样例末尾追加：

```text
"帮我建个工单" → other(明确要求建单,进 Agent 由建单工具处理,不是 complaint)
"我要提交一个纠错单" → other(建单请求,不是 complaint)
"我的纠错单进度怎么样了" → other(查记录,进 Agent)
"查一下《静夜思》的诗库档案" → find_poem(查诗词档案)
"查一下诗人在诗库里的资料" → find_poet(查诗人档案)
"查一下《春望》的判定记录" → other(查判定记录,进 Agent)
```

- [ ] **Step 2: 补 Prompt 断言测试**

在 `tests/test_prompts.py` 末尾追加：

```python
def test_system_prompt_has_ticket_guidance():
    text = SYSTEM_PROMPT_TEMPLATE.format()
    assert "create_ticket" in text
    assert "追问" in text


def test_intent_prompt_has_ticket_routing_few_shot():
    from prompts import INTENT_PROMPT
    text = INTENT_PROMPT.invoke({"question": "x"}).to_messages()[0].content
    assert "帮我建个工单" in text
    assert "不是 complaint" in text
```

- [ ] **Step 3: 跑 Prompt 测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_prompts.py -v
```

Expected: 5 passed。

- [ ] **Step 4: 建意图评估集与脚本**

新建 `potry-ai-agent/evals/ch07_intent_cases.md`：

```markdown
# Ch07 意图路由标注样例(用于 INTENT_PROMPT 真实模型评估)

| 用户问句 | 允许标签 | 说明 |
|---|---|---|
| 查一下《静夜思》的诗库档案 | find_poem | 档案 MCP 接管查诗 |
| 查一下诗人在诗库里的资料 | find_poet | 诗人档案 MCP |
| 帮我建个工单 | other | 建单请求进 Agent,不得归 complaint |
| 我要提交一个纠错单 | other | 建单请求,不得归 complaint |
| 我的纠错单进度怎么样了 | other | 查记录进 Agent |
| 查一下《春望》的判定记录 | other / find_poem | 查判定记录 |
| 答得不对,我不满意 | complaint | 纯抱怨才归投诉 |
| 《静夜思》表达了什么感情 | poem_explain | 赏析走 RAG |
| 唐代有哪些名篇 | find_poem | 按朝代找诗 |
| 这句合不合律 | poem_meter | 格律判定 |
```

新建 `potry-ai-agent/evals/run_ch07_intent_eval.py`：

```python
"""Ch07 意图评估:真实模型跑标注样例,打印准确率;任一错例即退出码 1。"""
import asyncio
import sys

from chat_service import build_llm
from config import load_settings
from prompts import INTENT_PROMPT
from workflow.intent import parse_intent_response

CASES = [
    ("查一下《静夜思》的诗库档案", {"find_poem"}),
    ("查一下诗人在诗库里的资料", {"find_poet"}),
    ("帮我建个工单", {"other"}),
    ("我要提交一个纠错单", {"other"}),
    ("我的纠错单进度怎么样了", {"other"}),
    ("查一下《春望》的判定记录", {"other", "find_poem"}),
    ("答得不对,我不满意", {"complaint"}),
    ("《静夜思》表达了什么感情", {"poem_explain"}),
    ("唐代有哪些名篇", {"find_poem"}),
    ("这句合不合律", {"poem_meter"}),
]


async def main() -> int:
    llm = build_llm(load_settings())
    correct = 0
    for question, allowed in CASES:
        message = await llm.ainvoke(INTENT_PROMPT.invoke({"question": question}))
        label, confidence = parse_intent_response(message.content or "")
        ok = label in allowed
        correct += int(ok)
        print(f"{'PASS' if ok else 'FAIL'} allowed={sorted(allowed)} got={label} "
              f"conf={confidence:.2f} | {question}")
    total = len(CASES)
    print(f"[eval] intent {correct}/{total} = {correct / total:.0%}")
    return 0 if correct == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 5: 建建单 Prompt 评估集与脚本**

新建 `potry-ai-agent/evals/ch07_ticket_cases.md`：

```markdown
# Ch07 create_ticket 行为标注样例(真实模型评估)

| 用户输入 | 期望 | 说明 |
|---|---|---|
| 帮我建个工单 | 不调工具,先追问 | 缺问题描述 |
| 我要提交一个纠错单 | 不调工具,先追问 | 缺问题描述 |
| 你们答错了,我不满意 | 不调工具 | 纯抱怨不建单 |
| 《静夜思》是谁写的 | 不调工具 | 普通问答 |
| 查一下我的纠错单进度 | 不调工具 | 查进度不是建单 |
| 帮我建个工单:原文有错字,《静夜思》第二句应为床前明月光 | 调 create_ticket | 信息完整 |
```

新建 `potry-ai-agent/evals/run_ch07_ticket_eval.py`：

```python
"""Ch07 create_ticket 行为评估:真实模型判断"该不该建单";错例退出码 1。"""
import asyncio
import sys

from langchain_core.messages import HumanMessage, SystemMessage

from chat_service import build_llm
from config import load_settings
from prompts import SYSTEM_PROMPT_TEMPLATE
from tools.ticket_tool import create_ticket

CASES = [
    ("帮我建个工单", False),
    ("我要提交一个纠错单", False),
    ("你们答错了,我不满意", False),
    ("《静夜思》是谁写的", False),
    ("查一下我的纠错单进度", False),
    ("帮我建个工单:原文有错字,《静夜思》第二句应为床前明月光", True),
]


def valid_ticket_call(ai) -> bool:
    for call in getattr(ai, "tool_calls", None) or []:
        if call["name"] != "create_ticket":
            continue
        args = call.get("args") or {}
        if args.get("ticket_type") in {"内容纠错", "功能异常", "其他"} and len(
            str(args.get("description") or "") 
        ) >= 4:
            return True
    return False


async def main() -> int:
    llm = build_llm(load_settings())
    bound = llm.bind_tools([create_ticket])
    correct = 0
    for text, should_call in CASES:
        ai = await bound.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT_TEMPLATE.format()),
            HumanMessage(content=text),
        ])
        called = valid_ticket_call(ai)
        ok = called == should_call
        correct += int(ok)
        print(f"{'PASS' if ok else 'FAIL'} should_call={should_call} called={called} | {text}")
    total = len(CASES)
    print(f"[eval] create_ticket {correct}/{total} = {correct / total:.0%}")
    return 0 if correct == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 6: 真跑两条评估(需上游余额)**

Run:

```powershell
.\.venv\Scripts\python.exe evals\run_ch07_intent_eval.py
.\.venv\Scripts\python.exe evals\run_ch07_ticket_eval.py
```

Expected: 两条 `[eval]` 均为 100%;若上游 402/超时,把原始输出记入 `dev-notes/ch07.md` 的「翻车与返工」，不得伪造通过。

- [ ] **Step 7: 提交**

```powershell
git add potry-ai-agent/prompts.py potry-ai-agent/tests/test_prompts.py potry-ai-agent/evals/ch07_intent_cases.md potry-ai-agent/evals/run_ch07_intent_eval.py potry-ai-agent/evals/ch07_ticket_cases.md potry-ai-agent/evals/run_ch07_ticket_eval.py
git commit -m "feat(ch07): add ticket-aware intent few-shots and real-model eval cases"
```

---

### Task 12: 前端工单预览卡(Vibe Coding 例外,不写 TDD/不 code review)

**Files:**
- Modify: `potry-ai-agent/static/chat.html`

- [ ] **Step 1: 加样式**

在 `.action-btn:disabled` 规则之后追加：

```css
  .ticket-card {
    margin-top: 10px;
    border: 1px solid var(--gold);
    background: #fffdf8;
    border-radius: 10px;
    padding: 12px 14px;
  }
  .ticket-card .ticket-title {
    font-size: 14px;
    color: var(--gold);
    letter-spacing: 2px;
    margin-bottom: 8px;
  }
  .ticket-card .ticket-row {
    display: flex;
    gap: 8px;
    font-size: 13px;
    color: var(--ink);
    margin-top: 4px;
  }
  .ticket-card .ticket-label { color: var(--ink-soft); min-width: 64px; }
  .ticket-card .row-btns { display: flex; gap: 8px; margin-top: 12px; }
```

- [ ] **Step 2: 加确认态与卡片函数**

在 `let sending = false;` 后追加：

```javascript
  let pendingConfirm = false;   // 建单预览等待确认:期间锁输入
```

在 `handleActionFrame` 中追加分支：

```javascript
    if (payload.action === "confirm_ticket") {
      renderTicketPreview(bubble, payload.preview || {}, payload.toolCallId);
      return;
    }
```

在 `renderActions` 之前追加：

```javascript
  // 建单预览卡:确认/取消都走 resume 接口,回复进新助手气泡
  function renderTicketPreview(bubble, preview, toolCallId) {
    const card = document.createElement("div");
    card.className = "ticket-card";
    card.dataset.toolCallId = toolCallId || "";
    const title = document.createElement("div");
    title.className = "ticket-title";
    title.textContent = "工单预览";
    const typeRow = document.createElement("div");
    typeRow.className = "ticket-row";
    typeRow.innerHTML = '<span class="ticket-label">工单类型</span><span>' +
      escapeHtml(preview.ticketType || "-") + "</span>";
    const descRow = document.createElement("div");
    descRow.className = "ticket-row";
    descRow.innerHTML = '<span class="ticket-label">问题描述</span><span>' +
      escapeHtml(preview.description || "-") + "</span>";
    const btns = document.createElement("div");
    btns.className = "row-btns";
    const ok = document.createElement("button");
    ok.className = "action-btn";
    ok.textContent = "确认提交";
    ok.addEventListener("click", () => resumeTicket(true, card));
    const cancel = document.createElement("button");
    cancel.className = "action-btn";
    cancel.textContent = "取消";
    cancel.addEventListener("click", () => resumeTicket(false, card));
    btns.append(ok, cancel);
    card.append(title, typeRow, descRow, btns);
    bubble.parentElement.appendChild(card);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  async function resumeTicket(confirmed, card) {
    if (sending || switching) return;
    sending = true;
    pendingConfirm = false;
    card.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    card.replaceWith(document.createTextNode(confirmed ? "已确认,正在提交…" : "已取消,正在处理…"));
    inputEl.disabled = true;
    sendBtn.disabled = true;
    lastTrace = null;
    try {
      await streamReply("", null, confirmed);
    } finally {
      sending = false;
      if (!pendingConfirm) {
        inputEl.disabled = false;
        sendBtn.disabled = false;
        inputEl.focus();
      }
      loadConversations();
    }
  }
```

- [ ] **Step 3: 改造 `streamReply` 支持 resume 与等待态**

把 `streamReply` 的签名与请求体部分改为：

```javascript
  // 流式请求 + SSE 解析(main / 续跑 / 建单 resume 共用)
  async function streamReply(userText, extra, resumeConfirmed) {
    const bubble = addRow("assistant", "");
    bubble.classList.add("typing");
    const isResume = resumeConfirmed !== undefined;
    const body = isResume
      ? { sessionId: sessionId, confirmed: resumeConfirmed }
      : Object.assign({ sessionId: sessionId, userId: userId, message: userText }, extra || {});
    const url = isResume ? "/agent/workflow/resume" : "/agent/workflow";
```

把 `fetch` 调用改为：

```javascript
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
```

把 done 分支改为：

```javascript
          } else if (event === "done") {
            finalSource = payload.source || null;
            if (payload.status === "awaiting_confirmation") {
              pendingConfirm = true;
              inputEl.disabled = true;
              sendBtn.disabled = true;
              bubble.textContent = acc || "请确认下面的工单信息:";
            }
            refreshSource(bubble, finalSource, toolCalls);
```

把流结束后的兜底文本改为：

```javascript
      if (!pendingConfirm) bubble.textContent = acc || "(空回复)";
      refreshSource(bubble, finalSource, toolCalls);
```

- [ ] **Step 4: 锁输入与恢复**

把 `pickPoem` 的开头 guard 改为：

```javascript
    if (sending || switching || pendingConfirm) return;
```

把 `pickPoem` 的 finally 改为：

```javascript
    } finally {
      sending = false;
      if (!pendingConfirm) {
        sendBtn.disabled = false;
        inputEl.focus();
      }
      loadConversations();
    }
```

把 `send()` 的开头 guard 改为：

```javascript
    if (!text || sending || switching || pendingConfirm) return;
```

把 `send()` 的 finally 改为：

```javascript
    } finally {
      sending = false;
      if (!pendingConfirm) {
        sendBtn.disabled = false;
        inputEl.focus();
      }
      loadConversations();
    }
```

- [ ] **Step 5: 手工验证**

1. 重启 API：停掉旧 `uvicorn`，重新 `uvicorn main:app --host 127.0.0.1 --port 8000`。
2. 打开 `http://127.0.0.1:8000/chat`（带 `?v=ch07` 防缓存）。
3. 输入「帮我建个工单」→ 青莲先追问问题描述。
4. 输入「原文有错字,《静夜思》第二句应为床前明月光」→ 出现工单预览卡,输入框锁住。
5. 点「确认提交」→ 新助手气泡回复含 `TK` 单号;输入框恢复。
6. 重走一次,点「取消」→ 回复已取消;输入框恢复。
7. 旧「转人工」「提交反馈」、诗词卡、纠错单表单仍可用。

- [ ] **Step 6: 提交**

```powershell
git add potry-ai-agent/static/chat.html
git commit -m "feat(ch07): add ticket preview card and resume flow to chat page"
```

---

### Task 13: 验收探针、六条验收与完结留痕

**Files:**
- Create: `potry-ai-agent/evals/slow_read_plugin.py`
- Create: `potry-ai-agent/evals/tool_audit_probe.py`
- Create: `potry-ai-agent/evals/accept_ch07.py`（真实 HTTP/SSE + MySQL 审计的验收入口，支持 `--phase main|ticket|cancel|mcp-new|timeout`）
- Create: `potry-ai-agent/tools/extensions/poem_reverse.py`（验收 1 的即插即用插件，保留）
- Modify: `potry-ai-agent/mcp_servers/poetry_archive_server.py`（验收 3 新增 `poem_line_count`，保留）
- Modify: `dev-notes/ch07.md`

- [ ] **Step 1: 准备超时探针**

新建 `potry-ai-agent/evals/slow_read_plugin.py`（**不要**直接放进 `tools/extensions`，验收时临时复制）：

```python
"""超时验收用插件:访问期间复制到 tools/extensions/ 即可热加载。"""
import asyncio

from langchain_core.tools import tool


@tool
async def slow_read_probe(keyword: str) -> dict:
    """故意很慢的只读工具,用于验证超时重试与错误兜底。

    Args:
        keyword: 查询词
    """
    await asyncio.sleep(3)
    return {"ok": True, "found": True, "keyword": keyword}


def register(catalog) -> None:
    catalog.register_builtin(slow_read_probe, timeout=0.3)
```

新建 `potry-ai-agent/evals/tool_audit_probe.py`：

```python
"""验收 6:直接用执行引擎制造读超时与写超时,核对审计的 retry_count/status/耗时。"""
import asyncio

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app_storage import AppStorage, ToolAuditLog
from config import load_settings
from db import get_engine
from tool_system.audit import AuditWriter
from tool_system.engine import ToolEngine
from tool_system.spec import ToolInvocation, ToolSpec, schema_of


@tool
async def slow_read(keyword: str) -> dict:
    """慢读探针。"""
    await asyncio.sleep(1.5)
    return {"ok": True, "found": True, "keyword": keyword}


@tool
async def slow_write(description: str) -> dict:
    """慢写探针。"""
    await asyncio.sleep(1.5)
    return {"ok": True, "ticket_no": "TK999999"}


async def main() -> None:
    settings = load_settings()
    factory = sessionmaker(bind=get_engine(settings.mysql_url))
    storage = AppStorage(factory)
    engine = ToolEngine(settings, AuditWriter(storage))

    read_spec = ToolSpec(
        name="probe_slow_read", description="", input_schema=schema_of(slow_read),
        tool=slow_read, timeout=0.2, max_retries=settings.tool_max_retries,
    )
    write_spec = ToolSpec(
        name="probe_slow_write", description="", input_schema=schema_of(slow_write),
        tool=slow_write, permission="write", requires_confirmation=True, timeout=0.2,
    )

    read_result = await engine.execute(
        read_spec, {"keyword": "静夜思"},
        ToolInvocation(session_id="probe-ch07", tool_call_id="probe-read"),
    )
    write_result = await engine.execute(
        write_spec, {"description": "超时探针"},
        ToolInvocation(session_id="probe-ch07", tool_call_id="probe-write", approved=True),
    )
    print("[probe] read:", read_result)
    print("[probe] write:", write_result)

    with factory() as session:
        rows = session.execute(
            select(ToolAuditLog)
            .where(ToolAuditLog.session_id == "probe-ch07")
            .order_by(ToolAuditLog.id)
        ).scalars().all()
    for row in rows:
        print(f"[audit] {row.tool_name} status={row.status} "
              f"retry={row.retry_count} duration_ms={row.duration_ms}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 验收 1(插件即插即用)**

先确认 API 已运行。用编辑器新建 `potry-ai-agent/tools/extensions/poem_reverse.py`：

```python
"""即插即用验收插件:把文字倒序返回。新增文件后不重启 API 即可被 Agent 使用。"""
from langchain_core.tools import tool


@tool
def poem_reverse(text: str) -> dict:
    """把一段文字倒序返回(验收即插即用插件)。

    Args:
        text: 要倒序的文字
    """
    return {"ok": True, "found": True, "reversed": text[::-1]}


def register(catalog) -> None:
    catalog.register_builtin(poem_reverse)
```

在 `/chat` 问「把《静夜思》前两句倒过来读」；Expected: Agent 调用 `poem_reverse`，回答含倒序文本；API 日志出现 `[tools] plugin load poem_reverse.py: poem_reverse`；`tool_audit_logs` 有 `source=builtin` 的记录。

- [ ] **Step 3: 验收 2(两个 MCP Server 真实调用)**

分别启动两个 Server（两个独立终端）：

```powershell
.\.venv\Scripts\python.exe mcp_servers\poetry_archive_server.py
.\.venv\Scripts\python.exe mcp_servers\judgement_server.py
```

Expected: 9101/9102 监听;API 日志无 `[mcp] ... unreachable`。

在 `/chat` 依次问：

1. 「查一下《静夜思》的诗库档案」→ 回答含档案原文/译文,审计 `source=mcp:poetry_archive`；
2. 「查一下《春望》的判定记录」→ 回答含判定结论,审计 `source=mcp:judgement`。

校验 SQL：

```sql
SELECT tool_name, source, status, retry_count FROM tool_audit_logs ORDER BY id DESC LIMIT 5;
```

- [ ] **Step 4: 验收 3(MCP 侧新增工具只重启该 Server)**

`poem_line_count` 在 Step 1 的文件准备阶段已加入 `mcp_servers/poetry_archive_server.py`；为了证明“运行中新增”，验收时再追加一个 `poem_first_line`（放在 `if __name__ == "__main__":` **之前**，放在其后会在 `mcp.run()` 阻塞后永远执行不到）：

```python
@mcp.tool()
def poem_first_line(title: str) -> dict:
    """返回指定诗题在档案中的首句。"""
    poem = POEMS.get(title)
    if poem is None:
        return {"ok": True, "found": False, "message": "档案中没有这首诗"}
    first = poem["content"].split("。")[0]
    return {"ok": True, "found": True, "title": title, "line": first}
```

只重启 9101，客服 API **不重启**：

```powershell
Get-CimInstance Win32_Process -Filter "name='python.exe'" |
  Where-Object { $_.CommandLine -like '*poetry_archive_server.py*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
.\.venv\Scripts\python.exe mcp_servers\poetry_archive_server.py
```

等 ≥5 秒后在 `/chat` 问「《静夜思》档案里有几句」；Expected: Agent 调用 `poem_line_count`，回答句数；API 日志出现该工具的 MCP 发现结果。

- [ ] **Step 5: 验收 4(建单确认落库)**

在 `/chat`：

1. 输入「帮我建个工单」→ Agent 追问问题描述；
2. 输入「原文有错字,《静夜思》第二句应为床前明月光」→ 出现预览卡；
3. 点「确认提交」→ 回复含 `TK` 单号。

校验：

```sql
SELECT id, ticket_no, ticket_type, description, status FROM tickets ORDER BY id DESC LIMIT 1;
SELECT tool_name, status, error FROM tool_audit_logs WHERE tool_name='create_ticket' ORDER BY id DESC LIMIT 1;
```

Expected: tickets 新增一行、`ticket_no` 与回复一致；审计 `status=success`。

- [ ] **Step 6: 验收 5(取消记权限拒绝)**

再走一次预览，点「取消」。

校验：

```sql
SELECT COUNT(*) FROM tickets;
SELECT tool_name, status, error FROM tool_audit_logs WHERE tool_name='create_ticket' ORDER BY id DESC LIMIT 1;
```

Expected: tickets 行数不增；审计 `status=permission_denied`。

- [ ] **Step 7: 验收 6(读超时重试、写超时零重试)**

1. 把 `evals/slow_read_plugin.py` 复制为 `tools/extensions/slow_read_probe.py`（不重启 API）；
2. 在 `/chat` 问「用慢查询工具查一下静夜思」→ Agent 调 `slow_read_probe`，超时后回复兜底说明；
3. 校验审计：

```sql
SELECT tool_name, status, retry_count, duration_ms FROM tool_audit_logs
WHERE tool_name='slow_read_probe' ORDER BY id DESC LIMIT 1;
```

Expected: `status=timeout`，`retry_count=TOOL_MAX_RETRIES`（默认 1），`duration_ms>0`。

4. 删除 `tools/extensions/slow_read_probe.py`（热卸载）；
5. 跑写超时探针：

```powershell
.\.venv\Scripts\python.exe evals\tool_audit_probe.py
```

Expected 输出含：

```text
[audit] probe_slow_read status=timeout retry=1 duration_ms=...
[audit] probe_slow_write status=timeout retry=0 duration_ms=...
```

- [ ] **Step 8: 全量回归**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: 全部通过，无 failed。

- [ ] **Step 9: 完结留痕**

检查 `dev-notes/ch07.md`：确认阶段 3–13 已按每个任务完成时逐段记录（四样：用户关键原话、关键产出、拒绝/纠偏、翻车与返工）；本次只补「完结段」：功能演示命令、测试结果、验收 1–6 证据、`dev-notes` 路径。若前面某阶段漏记，按实际阶段逐一补齐并注明补记时间，不得合并成一次补记。

- [ ] **Step 10: 提交**

```powershell
git add potry-ai-agent/evals/slow_read_plugin.py potry-ai-agent/evals/tool_audit_probe.py potry-ai-agent/tools/extensions/poem_reverse.py potry-ai-agent/mcp_servers/poetry_archive_server.py dev-notes/ch07.md
git commit -m "chore(ch07): add acceptance probes and finish development notes"
```

---

## 自审清单(计划作者已完成)

- **Spec 覆盖**:注册中心(T3/T4/T8)、Schema 校验(T3/T5)、权限(T4/T5/T9)、执行引擎(T5)、审计(T2/T5)、MCP(T6)、建单流(T7/T9/T10/T12)、验收 1–6(T13)、Prompt 评估(T11)。
- **无占位符**:每个任务都给了可执行代码、命令与预期输出;没有 TBD / "类似 Task N"。
- **类型一致**:`ToolCatalog.get_tools()` 异步、`execute(..., session_id, userid, tool_call_id, approved)`、`ToolEngine.execute(spec, args, ToolInvocation)`、`WorkflowDeps(settings, llm, tools, ...)`、`ticket_confirmed/ticket_preview` 在各任务中同名同义。
- **依赖版本**:`pydantic==2.14.1`、`mcp==1.30.0`、`langchain-mcp-adapters==0.3.2`、`jsonschema==4.26.0`;安装后全量回归。
- **已知风险**:MCP Server 未启动时首轮工具刷新最多等待约 2 秒（并发探活 + timeout），失败后保留空清单并在 TTL 后重试；`FastMCP` 的 `host/port` 构造参数在安装后以实际签名复核，若 1.30.0 不接收则改用 `mcp.settings.host/port`（不更换传输方式）。
