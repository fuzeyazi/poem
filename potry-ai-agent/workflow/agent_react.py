"""主力 Agent 的 ReAct 子循环(LangGraph 版):agent 节点 → tool_node → 回到 agent。

与 `naive_agent.py`(无框架手写版)互为对照,两者停止判定语义一致(spec §6):
1. 响应不含 tool_calls → 自然收敛;
2. iterations 达上限 / tokens 达上限 → 强制收敛(丢弃裸 tool_calls AI,改发纯文本请求)。

工具集 = ToolCatalog(内置 + 热加载插件 + MCP);`submit_feedback` 已从 Agent 清单移除。
"""
import json
import time
from langfuse import observe as _lf_observe  # Ch08:节点 span,无凭据自动 no-op

from langchain_core.messages import HumanMessage
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.runnables.config import RunnableConfig

from context_builder import build_agent_context
from context_log import log_model_ctx
from tools.registry import make_tool_message
from workflow.deps import get_deps

_FORCE_ANSWER_HINT = "请直接根据目前已有的信息作答,不要再调用任何工具。"
_FORCE_ANSWER_FALLBACK = "信息比较多,我先说到这儿;如果你能再补充一点线索,我可以答得更准。"
_AGENT_ERROR_REPLY = "抱歉,我这会儿组织回答时出了点状况,要不换个说法再问我一次?"


@_lf_observe()
async def agent_node(state: dict, config: RunnableConfig | None = None) -> dict:
    """主力 Agent:按固定顺序拼精简上下文后调 LLM,产出 tool_calls 或收敛答案。

    config 必须透传给 LLM 调用:①Langfuse generation 挂根 trace;②SSE 真流式依赖
    on_chat_model_stream 事件(不带 config 的调用不进事件流,token 帧就断了)。
    """
    deps = get_deps()
    ctx = build_agent_context(state, deps)
    if state.get("iterations", 0) == 0:
        log_model_ctx(state.get("session_id") or "", ctx.turn, ctx)
    msgs = list(ctx.messages)
    iterations = state.get("iterations", 0) + 1
    try:
        # Ch08 验收5:intent 由 finish_turn 写 trace 根元数据,成本报表按 trace_id 关联分组
        # (实测 v5 SDK 的 propagate_attributes(metadata=) 不及 CallbackHandler generation,故不在此挂)
        ai = await deps.llm.bind_tools(await deps.tools.get_tools()).ainvoke(msgs, config=config)
    except Exception as exc:  # noqa: BLE001 - 模型失败降级兜底,不阻断整图
        print(f"[wf] agent fail: {str(exc)[:200]}")
        return {"messages": [], "iterations": iterations,
                "answer": _AGENT_ERROR_REPLY, "fallback_reason": "agent_error"}
    msgs.append(ai)
    # WORKFLOW_MAX_TOKENS 只约束**本轮 ReAct 增量**(历史已由预算单独管),
    # 否则长历史一进上下文就超过 8000,任何工具轮都会被立刻强制收敛。
    start = state.get("turn_message_start")
    prev_msgs = list(state.get("messages") or [])
    has_current_user = (
        isinstance(start, int) and 0 <= start < len(prev_msgs)
        and isinstance(prev_msgs[start], HumanMessage)
    )
    if isinstance(start, int):
        turn_msgs = prev_msgs[start + (1 if has_current_user else 0):] + [ai]
    else:
        turn_msgs = msgs
    tokens_used = count_tokens_approximately(turn_msgs)
    if ai.tool_calls and (iterations >= deps.max_iter or tokens_used >= deps.max_tokens):
        reason = "max_iter" if iterations >= deps.max_iter else "max_tokens"
        return {
            "messages": [],
            "iterations": iterations,
            "tokens_used": tokens_used,
            "answer": await _force_answer(deps, msgs[:-1], config),
            "fallback_reason": reason,
        }
    out: dict = {"messages": [ai], "iterations": iterations, "tokens_used": tokens_used}
    if not ai.tool_calls:
        out["answer"] = ai.content or ""
    return out


@_lf_observe()
async def tool_node(state: dict, config: RunnableConfig | None = None) -> dict:
    """工具节点:统一走 ToolCatalog 执行,回灌 ToolMessage 并记录轨迹。

    config 透传到 BaseTool.ainvoke,让 on_tool_start/end 事件进入 SSE 事件流(实时工具进度)。
    """
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
            config=config,
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
    for tr in traces:  # Ch09:文坛草稿提升到 state,供 SSE action 帧下发(发布归前端)
        try:
            payload = json.loads(tr["content"])
        except (ValueError, TypeError):
            continue
        if isinstance(payload, dict) and payload.get("draft"):
            out["forum_draft"] = payload["draft"]
    if state.get("ticket_confirmed") is not None:
        out["ticket_confirmed"] = None      # 确认态只放行一次,不跨工具/跨轮复用
        out["ticket_preview"] = None
    return out


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


async def _force_answer(deps, messages: list, config: RunnableConfig | None = None) -> str:
    """不带工具再问一次逼出纯文本答案;失败也给兜底话术,保证收敛。"""
    try:
        forced = await deps.llm.ainvoke(messages + [HumanMessage(content=_FORCE_ANSWER_HINT)],
                                        config=config)
    except Exception as exc:  # noqa: BLE001
        print(f"[wf] force answer fail: {str(exc)[:200]}")
        return _FORCE_ANSWER_FALLBACK
    return forced.content or _FORCE_ANSWER_FALLBACK
