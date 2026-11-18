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
