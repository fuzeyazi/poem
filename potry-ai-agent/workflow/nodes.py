"""Ch04 七个节点中的其余六个 + 条件边判定。

指代消解 / 意图识别 / 意图分流 / 知识检索 / 置信度闸 / 日志记录 在此;
主力 Agent 与工具节点在 `agent_react.py`(ReAct 子循环)。

日志记录节点输出**一行结构化日志**(spec §9),格式固定为验收观测点:
`[wf] intent=<意图> route=<出口> gate=<pass|insufficient|skip> score=<相似度或-> confidence=<证据置信度或-> iters=<迭代数> tokens=<token数> elapsed=<毫秒>`
"""
import time
from langfuse import observe as _lf_observe  # Ch08:节点 span,无凭据自动 no-op

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import interrupt

from context_builder import build_history_context, load_snapshot, turn_number
from context_budget import estimate_rows_tokens
from context_layers import downgrade_anchor, split_layers, truncate_layer2
from context_log import log_history_ctx, log_line
from flywheel import snapshot_hits
from prompts import CHITCHAT_REPLY, COMPLAINT_REPLY, FALLBACK_REPLY, INTENT_PROMPT
from summarizer import schedule_summary
from workflow import expand, ruling
from workflow.confidence import (
    evidence_signals, is_confidence_sufficient, retrieve_evidence,
)
from workflow.deps import get_deps
from workflow.intent import (
    DEFAULT_INTENT,
    INTENT_POEM_METER,
    INTENT_TO_ROUTE,
    ROUTE_BUSINESS,
    ROUTE_CHITCHAT,
    ROUTE_COMPLAINT,
    ROUTE_KNOWLEDGE,
    ROUTE_OTHER,
    ROUTE_RULING,
    parse_intent_response,
)
from workflow.resolve import resolve_input
from workflow.state import PER_TURN_RESET


@_lf_observe()
async def resolve_node(state: dict) -> dict:
    """指代消解 + Query 改写:历史由 context_builder 现算;同时记录本轮 user 消息下标。"""
    deps = get_deps()
    session_id = state.get("session_id") or ""
    snapshot = load_snapshot(deps, session_id)
    history_ctx = build_history_context(snapshot, deps.settings)
    log_history_ctx(session_id, turn_number(snapshot, state), history_ctx)

    selected = state.get("selected_poem_id")
    resume = bool(selected) and bool(state.get("pending_subflow"))
    out: dict = {
        **PER_TURN_RESET,
        "resolved_input": state.get("resolved_input", ""),
        "selected_poem_id": selected if resume else None,
        "candidates": [],
        "pending_subflow": resume,
        "turn_message_start": len(state.get("messages") or []),
    }
    user_text = (state.get("user_input") or "").strip()
    if user_text:
        out["messages"] = [HumanMessage(content=user_text)]
    if resume:
        print("[wf] resolve resume=续跑(沿用上一轮消解结果)")
        return out
    resolved, changed = await resolve_input(deps.llm, user_text, history_ctx.for_llm())
    out["resolved_input"] = resolved
    out["query_changed"] = changed
    print(f"[wf] resolve changed={str(changed).lower()} query={resolved}")
    return out


@_lf_observe()
async def classify_node(state: dict) -> dict:
    """意图识别:四件套 prompt 输出 {intent, confidence};解析失败/模型失败 → 降级 other 并告警。"""
    deps = get_deps()
    try:
        message = await deps.llm.ainvoke(INTENT_PROMPT.invoke({"question": state["resolved_input"]}))
        label, confidence = parse_intent_response(message.content or "")
    except Exception as exc:  # noqa: BLE001 - 分类失败不阻断流程
        print(f"[wf] classify fail, degrade to {DEFAULT_INTENT}: {str(exc)[:200]}")
        label, confidence = DEFAULT_INTENT, 0.0
    print(f"[wf] classify intent={label} conf={confidence:.2f}")
    return {"intent": label, "confidence": confidence}


@_lf_observe()
def route_node(state: dict) -> dict:
    """意图分流:硬编码查表得出口;投诉/闲聊直接落预设话术(不调模型、不调工具)。

    判定子流程在此确定 `subflow_kind`(meter / verify)—— 续跑段不经过本节点,
    故该字段依赖 state 持久化保留;新轮一律重新赋值(非判定类为空串)。
    """
    label = state.get("intent", DEFAULT_INTENT)
    route = INTENT_TO_ROUTE.get(label, ROUTE_OTHER)
    out: dict = {"route": route, "subflow_kind": ""}
    if route == ROUTE_RULING:
        out["subflow_kind"] = "meter" if label == INTENT_POEM_METER else "verify"
    elif route == ROUTE_COMPLAINT:
        out["answer"] = COMPLAINT_REPLY
        out["actions"] = ["handoff", "feedback"]
    elif route == ROUTE_CHITCHAT:
        out["answer"] = CHITCHAT_REPLY
    return out


@_lf_observe()
async def slot_check_node(state: dict) -> dict:
    """判定子流程第一步:拿到诗作对象 → 继续;拿不到 → 下发诗词卡片等用户点选。"""
    return await ruling.resolve_slot(state, get_deps())


def after_slot_check(state: dict) -> str:
    """槽位检查后条件边。"""
    return ruling.after_slot_check(state)


@_lf_observe()
async def expand_query_node(state: dict) -> dict:
    """判定子流程第二步:把问题扩写成多条检索查询(失败降级单条原 query)。"""
    queries = await expand.expand_queries(get_deps().llm, state.get("resolved_input", ""))
    return {"expanded_queries": queries}


@_lf_observe()
def retrieve_policy_node(state: dict) -> dict:
    """判定子流程第三步:多查询检索 `policy` 条款并合并;同时挂上纠错单类目。"""
    out = ruling.collect_policy(state, get_deps())
    target = (state.get("slot_target") or {}).get("title") or "-"
    print(
        f"[wf] subflow kind={state.get('subflow_kind', '-')} target={target} "
        f"policy={len(out['policy_hits'])}"
    )
    return out


@_lf_observe()
def retrieve_node(state: dict) -> dict:
    """知识检索:三源各取 top-k 合并,并回查权威原文片段一并带给 Agent。"""
    deps = get_deps()
    hits, score = retrieve_evidence(state["resolved_input"], deps.settings)
    enriched = []
    for hit in hits:
        text = ""
        try:
            chunk = deps.knowledge_storage.get_chunk(hit["id"]) if deps.knowledge_storage else None
            if chunk:
                text = chunk.get("raw_text") or chunk.get("chunk_text") or ""
        except Exception as exc:  # noqa: BLE001 - 回查原文失败按"无原文"处理,不冒泡(spec §10 降级)
            print(f"[wf] get_chunk fail id={hit.get('id')}: {str(exc)[:200]}")
        enriched.append({**hit, "text": text})
    print(f"[wf] retrieve n={len(hits)} top={score:.4f}")
    return {"retrieved": enriched, "evidence_score": score}


@_lf_observe()
def gate_node(state: dict) -> dict:
    """置信度闸:检索后、Agent 前;不足则兜底 + 入池(带 Top5 快照)。"""
    deps = get_deps()
    hits = state.get("retrieved") or []
    signals = evidence_signals(hits, deps.settings.evidence_min_score)
    confidence = signals["evidence_confidence"]
    if is_confidence_sufficient(confidence, deps.settings.evidence_confidence_threshold):
        return {
            "gate_status": "pass",
            "evidence_confidence": confidence,
            "gate_signals": signals,
        }
    try:
        if deps.knowledge_storage is not None:
            pending_id = deps.knowledge_storage.add_pending_question(
                state.get("user_input", ""), state.get("session_id"),
                source_entry="retrieval_gate",
                retrieved_snapshot=snapshot_hits(hits),
            )
            if deps.flywheel is not None:
                deps.flywheel.schedule(pending_id)
    except Exception as exc:  # noqa: BLE001 - 记录失败只告警,不阻断兜底
        print(f"[wf] pending write fail: {str(exc)[:200]}")
    return {
        "gate_status": "insufficient",
        "evidence_confidence": confidence,
        "gate_signals": signals,
        "answer": FALLBACK_REPLY,
        "fallback_reason": "insufficient_evidence",
    }


@_lf_observe()
async def log_node(state: dict) -> dict:
    """日志记录:补 AI 消息、两段式落库、层 1 降级、层 2 超预算投递摘要。"""
    elapsed = int((time.monotonic() - state.get("started_at", time.monotonic())) * 1000)
    print(
        f"[wf] intent={state.get('intent', '-')} conf={_fmt(state.get('confidence'), 2)} "
        f"route={state.get('route', '-')} gate={state.get('gate_status', 'skip')} "
        f"score={_fmt(state.get('evidence_score'), 4)} "
        f"confidence={_fmt(state.get('evidence_confidence'), 4)} "
        f"iters={state.get('iterations', 0)} tokens={state.get('tokens_used', 0)} elapsed={elapsed}"
    )
    out: dict = {}
    answer = state.get("answer", "")
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if not (
        isinstance(last, AIMessage)
        and not getattr(last, "tool_calls", None)
        and (last.content or "") == answer
    ):
        out["messages"] = [AIMessage(content=answer)]
    ids = _persist_turn(state)
    if ids is not None:
        try:
            _after_persist(state, ids)
        except Exception as exc:  # noqa: BLE001 - 副作用失败不影响已产出的回答
            print(f"[wf] after persist fail: {str(exc)[:200]}")
    return out


def _after_persist(state: dict, ids: tuple[int, int | None, int]) -> None:
    """锚点推进只在落库后做:层 1 超预算只挪 layer1_from;层 2 超预算投递后台摘要。"""
    deps = get_deps()
    storage = deps.chat_storage
    session_id = state.get("session_id") or ""
    conversation_id = ids[0]
    snapshot = storage.load_context(session_id)
    layers = split_layers(snapshot["rows"], snapshot["summaryUpto"], snapshot["layer1From"])
    if estimate_rows_tokens(layers.layer1) > deps.budget.layer1:
        new_anchor = downgrade_anchor(layers.layer1, deps.budget.layer1)
        if new_anchor:
            old_anchor = snapshot["layer1From"]
            storage.advance_layer1_anchor(conversation_id, new_anchor)
            log_line(f"[ctx] layer1 降级 {old_anchor}→{new_anchor}")
            snapshot = storage.load_context(session_id)
            layers = split_layers(snapshot["rows"], snapshot["summaryUpto"], snapshot["layer1From"])
    layer2 = truncate_layer2(
        layers.layer2, deps.settings.layer2_assistant_prefix_chars, deps.settings.layer2_blob_chars
    )
    layer2_tokens = estimate_rows_tokens(layer2)
    if layer2_tokens > deps.budget.layer2:
        schedule_summary(
            deps, session_id, conversation_id,
            from_id=snapshot["summaryUpto"], to_id=snapshot["layer1From"],
            layer2_tokens=layer2_tokens,
        )


def _fmt(value, digits: int) -> str:
    return f"{value:.{digits}f}" if isinstance(value, (int, float)) else "-"


def _persist_turn(state: dict):
    """把本轮 user(非空时)+ 最终 assistant 落库,返回 (conversation_id, user_msg_id, assistant_msg_id)。"""
    deps = get_deps()
    if deps.chat_storage is None:
        return None
    try:
        return deps.chat_storage.persist_turn(
            state.get("session_id", ""),
            state.get("user_input", ""),
            state.get("answer", ""),
            state.get("userid"),
        )
    except Exception as exc:  # noqa: BLE001 - 落库失败不打断对话
        print(f"[wf] storage fail: {str(exc)[:200]}")
        return None


def after_resolve(state: dict) -> str:
    """消解后条件边:处于等待回填的续跑 → 直接进判定子流程(跳过分类);否则正常分类。"""
    return "slot_check" if state.get("pending_subflow") else "classify"


def after_route(state: dict) -> str:
    """分流条件边:知识类→检索;判定类→槽位检查;业务类/其他→Agent;投诉/闲聊→直接日志收尾。"""
    route = state.get("route", ROUTE_OTHER)
    if route == ROUTE_KNOWLEDGE:
        return "retrieve"
    if route == ROUTE_RULING:
        return "slot_check"
    if route in (ROUTE_BUSINESS, ROUTE_OTHER):
        return "agent"
    return "log"


def after_gate(state: dict) -> str:
    """闸后条件边:证据足→Agent;不足→日志收尾(答案已是兜底话术)。"""
    return "agent" if state.get("gate_status") == "pass" else "log"


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
