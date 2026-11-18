"""指代消解 + Query 改写(合成一个 LLM 环节,spec §1.1)。

设计要点:
- **已完整、指代明确的问题原样透传**:历史为空时直接返回原问、不调模型(也省一次调用);
- 有历史才请模型消解;模型说 `changed=false` 时按原问返回,避免无谓改写;
- 任何失败(模型异常 / JSON 解析失败 / 空 query)一律透传原文 + 告警,不阻断(spec §10)。
"""
import json

from prompts import RESOLVE_PROMPT

_ROLE_NAMES = {"user": "用户", "assistant": "青莲"}


def format_history(history: list[dict]) -> str:
    """把历史渲染成「用户:/青莲:/【早期梗概】」纯文本,供 prompt 注入。"""
    lines = []
    for row in history or []:
        role = row.get("role")
        if role == "summary":
            lines.append(f"【早期梗概】{row.get('content') or ''}")
            continue
        lines.append(f"{_ROLE_NAMES.get(role, role or '-')}:{row.get('content') or ''}")
    return "\n".join(lines) if lines else "(无)"


def parse_resolve_result(text: str) -> tuple[str, bool]:
    """解析模型输出 `{"query": ..., "changed": ...}`。

    失败、query 为空 → `("", False)`,由调用方按"透传原文"处理。
    """
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError, AttributeError):
        return "", False
    query = str(data.get("query") or "").strip()
    if not query:
        return "", False
    return query, bool(data.get("changed", False))


async def resolve_input(llm, question: str, history: list[dict] | None) -> tuple[str, bool]:
    """返回 `(消解/改写后的问题, 是否真的改动过)`;失败一律回落到原问。"""
    question = (question or "").strip()
    if not history:
        return question, False       # 无上文可依 → 原样透传
    try:
        message = await llm.ainvoke(
            RESOLVE_PROMPT.invoke({"history": format_history(history), "question": question})
        )
        resolved, changed = parse_resolve_result(message.content or "")
    except Exception as exc:  # noqa: BLE001 - 消解失败不阻断,透传原文
        print(f"[wf] resolve fail, pass through: {str(exc)[:200]}")
        return question, False
    if not resolved:
        return question, False
    return resolved, changed
