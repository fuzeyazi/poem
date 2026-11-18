"""Ch04–Ch06 编排状态:贯穿图全流程的 WorkflowState(TypedDict)。

`messages` 用 LangGraph 官方 `add_messages` reducer:节点只吐新增消息,框架按 id 并入;
完整历史(含 tool_calls / ToolMessage)由 checkpointer 落盘。调模型前另由
`context_builder` 现算精简版,两条路径互不影响。
"""
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages

# 每轮开始时必须归零的"本轮字段":State 经 checkpointer 跨轮持久化
PER_TURN_RESET = {
    "intent": "",
    "confidence": 0.0,
    "route": "",
    "retrieved": [],
    "evidence_score": None,
    "evidence_confidence": 0.0,
    "gate_signals": {},
    "gate_status": "skip",
    "answer": "",
    "actions": [],
    "tool_trace": [],
    "iterations": 0,
    "tokens_used": 0,
    "fallback_reason": "",
    # ---------- Ch05 ----------
    "query_changed": False,
    "slot_target": None,
    "expanded_queries": [],
    "policy_hits": [],
    "correction_categories": [],
    # ---------- Ch07 ----------
    "ticket_confirmed": None,
    "ticket_preview": None,
    # ---------- Ch09 ----------
    "forum_draft": None,
}


class WorkflowState(TypedDict, total=False):
    session_id: str
    userid: str | None            # Ch06:匿名用户标识(侧栏过滤)
    user_input: str
    selected_poem_id: int | None
    resolved_input: str
    intent: str
    confidence: float
    route: str
    retrieved: list[dict]
    evidence_score: float | None
    evidence_confidence: float
    gate_signals: dict
    gate_status: str
    messages: Annotated[list, add_messages]   # 完整历史(累积)
    turn_message_start: int       # Ch06:本轮用户消息在 messages 中的下标
    tool_trace: list
    answer: str
    actions: list[str]
    iterations: int
    tokens_used: int
    fallback_reason: str
    started_at: float
    # ---------- Ch05 ----------
    query_changed: bool
    subflow_kind: str
    slot_target: dict | None
    candidates: list[dict]
    pending_subflow: bool
    expanded_queries: list[str]
    policy_hits: list[dict]
    correction_categories: list[str]
    # ---------- Ch07 ----------
    ticket_confirmed: bool | None
    ticket_preview: dict | None
    # ---------- Ch09 ----------
    forum_draft: dict | None       # 文坛草稿(tool_node 提升,SSE action 帧下发;发布走前端)
