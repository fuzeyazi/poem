"""生成阶段自评:回答后独立一次 LLM 判断知识不足,入池。"""
import json
import re

from flywheel import snapshot_hits
from prompts import SELF_EVAL_PROMPT

_SKIP_ROUTES = {"chitchat", "complaint"}


def _parse_json(text: str) -> dict | None:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


async def assess_answer(llm, question: str, answer: str, evidence: list[dict],
                        lf_trace_id: str | None = None, intent: str | None = None,
                        session_id: str | None = None) -> dict:
    """Ch09:lf_trace_id 非空时,自评 LLM 调用挂回主回合 trace(子 span + generation,
    成本按 intent 归因);无凭据环境自动 no-op。"""
    from observability import get_handler, linked_span

    handler = get_handler()
    cfg = {"callbacks": [handler]} if handler is not None else None
    try:
        prompt = SELF_EVAL_PROMPT.invoke({
            "question": question, "answer": answer,
            "evidence": snapshot_hits(evidence),
        })
        with linked_span(lf_trace_id, "self-eval", {"intent": intent, "self_eval": True},
                         session_id=session_id):
            # cfg=None(未启用链路/测试 FakeLLM 不收 config)时走原始调用形态
            message = await (llm.ainvoke(prompt, config=cfg) if cfg else llm.ainvoke(prompt))
        data = _parse_json(message.content or "")
        return {
            "insufficient": bool(data and data.get("insufficient")),
            "reason": str((data or {}).get("reason") or ""),
        }
    except Exception as exc:  # noqa: BLE001 - 自评失败不落池
        print(f"[self_eval] fail: {str(exc)[:160]}")
        return {"insufficient": False, "reason": "error"}


def _should_skip(state: dict) -> bool:
    if not state.get("answer"):
        return True
    if state.get("gate_status") == "insufficient":
        return True
    if state.get("pending_subflow"):
        return True
    if state.get("route") in _SKIP_ROUTES:
        return True
    if state.get("fallback_reason") == "agent_error":
        return True
    return False


async def self_eval_after_turn(state: dict, deps, session_id: str,
                               lf_trace_id: str | None = None) -> None:
    if _should_skip(state) or deps.knowledge_storage is None:
        return
    result = await assess_answer(
        deps.llm, state.get("resolved_input") or state.get("user_input", ""),
        state.get("answer", ""), state.get("retrieved") or [],
        lf_trace_id=lf_trace_id, intent=state.get("intent"), session_id=session_id,
    )
    if not result["insufficient"]:
        return
    try:
        pending_id = deps.knowledge_storage.add_pending_question(
            state.get("user_input", ""), session_id,
            source_entry="model_self_eval",
            retrieved_snapshot=snapshot_hits(state.get("retrieved") or []),
        )
        if deps.flywheel is not None:
            deps.flywheel.schedule(pending_id)
    except Exception as exc:  # noqa: BLE001
        print(f"[self_eval] pending write fail: {str(exc)[:160]}")
