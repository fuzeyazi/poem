"""调模型的上下文拼装(spec §5):固定顺序,梗概绝不单独占 system。"""
from dataclasses import dataclass

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from context_budget import (
    estimate_messages_tokens,
    estimate_rows_tokens,
    estimate_tokens,
)
from context_layers import split_layers, truncate_layer2, turn_groups
from prompts import RULING_JUDGE_INSTRUCTION, SYSTEM_PROMPT_TEMPLATE


@dataclass
class HistoryContext:
    summary: str
    layer2: list[dict]
    layer1: list[dict]
    tokens: int

    def for_llm(self) -> list[dict]:
        rows = []
        if self.summary:
            rows.append({"role": "summary", "content": self.summary})
        rows += [{"role": r["role"], "content": r["content"]} for r in self.layer2 + self.layer1]
        return rows


@dataclass
class AgentContext:
    messages: list
    summary: str
    layer2: list[dict]
    layer1: list[dict]
    current: str
    evidence: str
    combined: str
    system: str
    tokens: int
    turn: int


def empty_snapshot() -> dict:
    return {"conversationId": None, "summaryUpto": 0, "layer1From": 0, "rows": [], "summaries": []}


def load_snapshot(deps, session_id: str) -> dict:
    if deps.chat_storage is None or not session_id:
        return empty_snapshot()
    try:
        return deps.chat_storage.load_context(session_id)
    except Exception as exc:  # noqa: BLE001 - 读历史失败按首轮处理,不阻断对话
        print(f"[ctx] load_context fail: {str(exc)[:200]}")
        return empty_snapshot()


def compose_summary_text(snapshot: dict, max_tokens: int) -> str:
    """总预算内全量拼接;超预算则保留最早一段 + 从最新段向前装到预算,最后按 seq 排序。"""
    texts = [
        (s.get("content") or "").strip()
        for s in sorted(snapshot.get("summaries") or [], key=lambda s: s.get("seq") or 0)
        if (s.get("content") or "").strip()
    ]
    if not texts:
        return ""
    joined = "\n".join(texts)
    if estimate_tokens(joined) <= max_tokens:
        return joined
    kept = [0]  # 第 1 段是最早事实,验收要靠它回忆,始终保留
    for idx in range(len(texts) - 1, 0, -1):
        candidate = "\n".join(texts[i] for i in sorted(kept + [idx]))
        if estimate_tokens(candidate) > max_tokens:
            break
        kept.append(idx)
    ordered = [texts[i] for i in sorted(kept)]
    if len(kept) < len(texts):
        ordered = [ordered[0], "…(中间梗概已省略)…", *ordered[1:]]
    return "\n".join(ordered)


def turn_number(snapshot: dict, state: dict) -> int:
    users = sum(1 for row in snapshot.get("rows") or [] if row.get("role") == "user")
    return users + (1 if (state.get("user_input") or "").strip() else 0)


def _trim_window(rows: list[dict], max_tokens: int) -> list[dict]:
    """从最旧处按完整轮次裁;至少保留最新一轮。"""
    if estimate_rows_tokens(rows) <= max_tokens:
        return rows
    kept_groups: list[list[dict]] = []
    total = 0
    for group in reversed(turn_groups(rows)):
        group_tokens = estimate_rows_tokens(group)
        if kept_groups and total + group_tokens > max_tokens:
            break
        kept_groups.insert(0, group)
        total += group_tokens
    return [row for group in kept_groups for row in group]


def build_history_context(snapshot: dict, settings) -> HistoryContext:
    """消解/意图共用:摘要一行 + 按 HISTORY_CTX_MAX_TOKENS 裁过的滑窗。"""
    layers = split_layers(snapshot.get("rows") or [], snapshot.get("summaryUpto", 0), snapshot.get("layer1From", 0))
    layer2 = truncate_layer2(
        layers.layer2, settings.layer2_assistant_prefix_chars, settings.layer2_blob_chars
    )
    summary = compose_summary_text(snapshot, settings.summary_reserve_tokens)
    window = _trim_window(layer2 + layers.layer1, settings.history_ctx_max_tokens)
    layer2_ids = {row.get("id") for row in layer2}
    return HistoryContext(
        summary=summary,
        layer2=[row for row in window if row.get("id") in layer2_ids],
        layer1=[row for row in window if row.get("id") not in layer2_ids],
        tokens=estimate_rows_tokens(window) + estimate_tokens(summary),
    )


def _as_message(row: dict):
    if row.get("role") == "assistant":
        return AIMessage(content=row.get("content") or "")
    return HumanMessage(content=row.get("content") or "")


def _ruling_evidence(state: dict) -> str:
    target = state.get("slot_target") or {}
    lines = [
        "【待判定的诗作(权威数据)】",
        f"标题:{target.get('title') or '-'}",
        f"作者:{target.get('writer') or '-'}",
        f"朝代:{target.get('dynasty') or '-'}",
        f"体裁:{target.get('type') or '-'}",
        f"原文:{(target.get('content') or '').strip()}",
        f"译文:{(target.get('translation') or '').strip()}",
        "",
        "【适用规则条款】",
    ]
    hits = state.get("policy_hits") or []
    for hit in hits:
        clause = (hit.get("raw_text") or hit.get("chunk_text") or "").strip()
        if clause:
            lines.append(f"- {clause}")
    if not hits:
        lines.append("(未检索到相关规则条款:依据不足时请如实说明不确定)")
    lines += ["", RULING_JUDGE_INSTRUCTION]
    return "\n".join(lines)


def evidence_text(state: dict) -> str:
    """判定子流程 = 权威数据 + 条款;知识类 = 检索片段;其余为空。"""
    if state.get("subflow_kind"):
        return _ruling_evidence(state)
    retrieved = state.get("retrieved") or []
    if not retrieved:
        return ""
    lines = ["【检索资料】"]
    for hit in retrieved:
        lines.append(
            f"[{hit.get('source_type', '')}|{hit.get('title') or ''}] {hit.get('text') or ''}".strip()
        )
    return "\n".join(lines)


def _cap_layer2(layer2: list[dict], layer1: list[dict], history_budget: int) -> list[dict]:
    """摘要尚未完成时层 2 可能仍超预算:拼装时从最旧处临时不喂,数据仍留在库里等梗概。"""
    total = estimate_rows_tokens(layer2) + estimate_rows_tokens(layer1)
    capped = list(layer2)
    while capped and total > history_budget:
        groups = turn_groups(capped)
        if not groups:
            break
        dropped = groups[0]
        capped = capped[len(dropped):]
        total -= estimate_rows_tokens(dropped)
    return capped


_RECALL_HINTS = ("最开始", "最早", "一开始", "最初")


def first_summary_sentence(snapshot: dict) -> str:
    """取第 1 段梗概的首句:回忆类问题用它把“最早”这件事顶到最前面。"""
    for segment in sorted(snapshot.get("summaries") or [], key=lambda s: s.get("seq") or 0):
        content = (segment.get("content") or "").strip()
        if not content:
            continue
        end = content.find("。")
        return content[: end + 1] if end >= 0 else content[:80]
    return ""


def build_agent_context(state: dict, deps) -> AgentContext:
    """固定顺序:system → 层 2 → 层 1 → 当前句 → 梗概+证据 → 本轮 ReAct 消息。"""
    snapshot = load_snapshot(deps, state.get("session_id") or "")
    layers = split_layers(snapshot.get("rows") or [], snapshot.get("summaryUpto", 0), snapshot.get("layer1From", 0))
    layer2 = truncate_layer2(
        layers.layer2, deps.settings.layer2_assistant_prefix_chars, deps.settings.layer2_blob_chars
    )
    layer2 = _cap_layer2(layer2, layers.layer1, deps.budget.history)
    layer1 = layers.layer1
    summary = compose_summary_text(snapshot, deps.settings.summary_reserve_tokens)
    evidence = evidence_text(state)
    current = (state.get("user_input") or "").strip()
    combined_parts = []
    if summary:
        if any(hint in current for hint in _RECALL_HINTS):
            earliest = first_summary_sentence(snapshot)
            if earliest:
                combined_parts.append(f"【最早事实(摘自第1段梗概)】{earliest}")
        combined_parts.append(
            "【早期梗概(按时间顺序,第1段最早;回答“最开始/最早”这类问题时以第1段为准,"
            "层1只是最近窗口,不是会话开头)】\n" + summary
        )
    if evidence:
        combined_parts.append(evidence)
    combined = "\n\n".join(combined_parts)
    system = SYSTEM_PROMPT_TEMPLATE.format()

    messages = [SystemMessage(content=system)]
    messages += [_as_message(row) for row in layer2]
    messages += [_as_message(row) for row in layer1]
    if current:
        messages.append(HumanMessage(content=current))
    if combined:
        messages.append(HumanMessage(content=combined))
    start = state.get("turn_message_start")
    turn_messages = list(state.get("messages") or [])
    has_current_user = (
        isinstance(start, int) and 0 <= start < len(turn_messages)
        and isinstance(turn_messages[start], HumanMessage)
    )
    if isinstance(start, int):
        messages += turn_messages[start + (1 if has_current_user else 0):]
    return AgentContext(
        messages=messages, summary=summary, layer2=layer2, layer1=layer1,
        current=current, evidence=evidence, combined=combined, system=system,
        tokens=estimate_messages_tokens(messages), turn=turn_number(snapshot, state),
    )
