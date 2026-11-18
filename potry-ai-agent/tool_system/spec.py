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
