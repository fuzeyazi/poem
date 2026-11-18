"""三层切分与层 2 确定性截短(spec §4)。锚点只比对 messages.id,降级不搬数据。"""
from dataclasses import dataclass

from context_budget import estimate_rows_tokens


@dataclass
class Layers:
    layer2: list[dict]
    layer1: list[dict]


def split_layers(rows: list[dict], summary_upto_msg_id: int, layer1_from_msg_id: int) -> Layers:
    """层 3: id ≤ summaryUpto;层 2: summaryUpto < id ≤ layer1From;层 1: id > layer1From。"""
    up_to = summary_upto_msg_id or 0
    from_id = layer1_from_msg_id or 0
    layer2: list[dict] = []
    layer1: list[dict] = []
    for row in rows or []:
        msg_id = row.get("id") or 0
        if msg_id <= up_to:
            continue
        if msg_id <= from_id:
            layer2.append(row)
        else:
            layer1.append(row)
    return Layers(layer2=layer2, layer1=layer1)


def truncate_content(role: str, content: str, prefix_chars: int, blob_chars: int) -> str:
    text = content or ""
    if role == "user":
        return text                                    # 用户原话一个字不动
    if len(text) > blob_chars:
        return f"[工具结果:{len(text)}字]"              # 大块内容换一行标识(含遗留 tool 行)
    if role == "assistant" and len(text) > prefix_chars:
        return text[:prefix_chars] + "…"
    return text


def truncate_layer2(rows: list[dict], prefix_chars: int, blob_chars: int) -> list[dict]:
    return [
        {**row, "content": truncate_content(row.get("role", ""), row.get("content", ""), prefix_chars, blob_chars)}
        for row in rows or []
    ]


def turn_groups(rows: list[dict]) -> list[list[dict]]:
    """按 user 边界切完整轮;开头的 assistant(续跑轮)自成一组。"""
    groups: list[list[dict]] = []
    current: list[dict] = []
    for row in rows or []:
        if row.get("role") == "user" and current:
            groups.append(current)
            current = [row]
        else:
            current.append(row)
    if current:
        groups.append(current)
    return groups


def downgrade_anchor(layer1_rows: list[dict], budget_tokens: int) -> int | None:
    """层 1 超预算 → 返回新锚点(被搬走批次的最末消息 id);无需降级返回 None。"""
    if estimate_rows_tokens(layer1_rows) <= budget_tokens:
        return None
    dropped: list[dict] = []
    for group in turn_groups(layer1_rows):
        dropped.extend(group)
        remaining = layer1_rows[len(dropped):]
        if estimate_rows_tokens(remaining) <= budget_tokens:
            break
    return dropped[-1]["id"] if dropped else None
