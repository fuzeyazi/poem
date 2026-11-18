"""无框架原生 Agent 循环:LLM 调用 → 工具调用 → 结果回传 → 无工具调用即收敛。

Ch04 需求第 1 条明确要求"先完成无框架原生实现,彻底明确 Agent 本质为带工具调用能力的
循环,完成后再基于 LangGraph 重构"。本模块即那份**先行验证版**,与
`workflow/agent_react.py`(LangGraph 版)互为对照;两者停止判定语义保持一致。

停止判定三条(spec §6):
1. 响应不含 tool_calls → 自然收敛;
2. iterations 达到 max_iter → 强制收敛(丢弃带 tool_calls 的裸 AI,改发纯文本请求);
3. tokens_used 达到 max_tokens → 同上。
"""
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.messages.utils import count_tokens_approximately

from tools.registry import make_tool_message

DEFAULT_MAX_ITER = 4
DEFAULT_MAX_TOKENS = 8000

_FORCE_ANSWER_HINT = "请直接根据目前已有的信息作答,不要再调用任何工具。"
_FORCE_ANSWER_FALLBACK = "信息比较多,我先说到这儿;如果你能再补充一点线索,我可以答得更准。"


async def run_naive_agent(
    llm,
    registry,
    messages: list,
    max_iter: int = DEFAULT_MAX_ITER,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict:
    """手写 Agent 循环。原地修改 `messages`(便于测试断言回灌结构)。

    返回 `{"answer": str, "iterations": int, "tokens_used": int, "stop_reason": str}`,
    `stop_reason` ∈ `no_tool_calls` / `max_iter` / `max_tokens`。
    """
    # 带上工具再问,模型才可能产出 tool_calls
    bound = llm.bind_tools(registry.get_tools())
    iterations = 0
    tokens_used = 0  # 必须先初始化:max_iter<=0 时循环不进入,后面 return 会用到
    while iterations < max_iter:
        iterations += 1
        ai: AIMessage = await bound.ainvoke(messages)
        messages.append(ai)
        tokens_used = count_tokens_approximately(messages)
        if not ai.tool_calls:
            return _result(ai.content, iterations, tokens_used, "no_tool_calls")
        if tokens_used >= max_tokens:
            # 丢弃裸 tool_calls AI(无配对 ToolMessage 会让真实 API 400),改发纯文本
            messages.pop()
            return _result(
                await _force_answer(llm, messages), iterations, tokens_used, "max_tokens"
            )
        if iterations >= max_iter:
            break  # 最后一轮不再执行工具,交给循环外强制收敛
        for tc in ai.tool_calls:
            result = await registry.execute(tc["name"], tc["args"])
            messages.append(make_tool_message(tc["id"], tc["name"], result))
    # 迭代上限:第 max_iter 轮不再执行工具,直接强制收敛(故 calls 少一次)
    if messages and isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        messages.pop()
    return _result(await _force_answer(llm, messages), iterations, tokens_used, "max_iter")


async def _force_answer(llm, messages: list) -> str:
    """不带工具再问一次,逼出一段纯文本答案(强制收敛用)。"""
    try:
        forced = await llm.ainvoke(messages + [HumanMessage(content=_FORCE_ANSWER_HINT)])
    except Exception as exc:  # noqa: BLE001 - 强制作答失败也要收敛,不让整轮崩掉
        print(f"[naive] 强制作答失败: {str(exc)[:200]}")
        return _FORCE_ANSWER_FALLBACK
    return forced.content or _FORCE_ANSWER_FALLBACK


def _result(answer: str | None, iterations: int, tokens_used: int, stop_reason: str) -> dict:
    return {
        "answer": answer or "",
        "iterations": iterations,
        "tokens_used": tokens_used,
        "stop_reason": stop_reason,
    }
