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


def test_normalize_unwraps_mcp_text_content_blocks():
    raw = [{
        "type": "text",
        "text": '{"ok": true, "found": true, "archive": {"title": "静夜思"}}',
        "id": "lc_x",
    }]
    result = normalize(raw)
    assert result == {"ok": True, "found": True, "archive": {"title": "静夜思"}}


def test_normalize_unwraps_plain_mcp_text_block():
    raw = [{"type": "text", "text": "纯文本结果", "id": "lc_x"}]
    result = normalize(raw)
    assert result == {"ok": True, "found": True, "data": "纯文本结果"}
