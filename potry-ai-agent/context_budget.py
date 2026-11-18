"""token 估算与会话历史预算(从模型窗口倒推,spec §6)。

估算口径与预算常量必须一起校准:只改一边会让净效果反向(估算偏小 → 实际超窗)。
"""
import math
import re
from dataclasses import dataclass

CJK_TOKENS_PER_CHAR = 0.6
CHARS_PER_TOKEN = 4.0
MESSAGE_OVERHEAD_TOKENS = 4

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def estimate_tokens(text: str | None) -> int:
    """中文按 0.6 token/字、其余按 4 字符/token,向上取整。"""
    if not text:
        return 0
    cjk = len(_CJK_RE.findall(text))
    other = len(text) - cjk
    return math.ceil(cjk * CJK_TOKENS_PER_CHAR + other / CHARS_PER_TOKEN)


def estimate_message_tokens(content: str | None) -> int:
    """消息级估算:正文 + role/分隔固定开销。"""
    return estimate_tokens(content) + MESSAGE_OVERHEAD_TOKENS


def estimate_rows_tokens(rows: list[dict]) -> int:
    return sum(estimate_message_tokens(row.get("content")) for row in rows or [])


def estimate_messages_tokens(messages: list) -> int:
    """LangChain 消息列表估算(只数 content,工具定义走固定预留)。"""
    total = 0
    for message in messages or []:
        content = getattr(message, "content", "")
        total += estimate_message_tokens(content if isinstance(content, str) else str(content))
    return total


@dataclass(frozen=True)
class Budget:
    window: int          # 模型上下文窗口
    output: int          # 输出预留
    user_input: int      # 用户输入预留
    agent_peak: int      # 单轮 ReAct 瞬时峰值
    fixed: int           # 系统提示 + 证据 + 梗概 + 安全余量
    window_side: int     # 窗口实际匀给历史的量
    history: int         # min(想留住的轮数×每轮稳态, window_side)
    layer1: int          # 七成(扣层间 1 token)
    layer2: int          # 三成
    ok: bool


def derive_budget(settings) -> Budget:
    """严格按需求原文:history = min(KEEP_TURNS×TURN_STEADY, window_side),再七三分。"""
    agent_peak = max(0, settings.max_agent_steps * settings.tool_result_max_tokens)
    fixed = (
        settings.system_reserve_tokens
        + settings.rerank_top_k * settings.evidence_per_chunk_tokens
        + settings.summary_reserve_tokens
        + settings.safety_reserve_tokens
    )
    window_side = (
        settings.model_context_window
        - settings.max_output_tokens
        - settings.max_user_input_tokens
        - agent_peak
        - fixed
    )
    history = min(settings.keep_turns * settings.turn_steady_tokens, window_side)
    if history <= 0:
        return Budget(
            window=settings.model_context_window, output=settings.max_output_tokens,
            user_input=settings.max_user_input_tokens, agent_peak=agent_peak,
            fixed=fixed, window_side=window_side, history=0, layer1=0, layer2=0, ok=False,
        )
    layer2 = int(history * 0.3)
    layer1 = history - layer2 - settings.boundary_reserve_tokens
    return Budget(
        window=settings.model_context_window, output=settings.max_output_tokens,
        user_input=settings.max_user_input_tokens, agent_peak=agent_peak,
        fixed=fixed, window_side=window_side, history=history,
        layer1=max(layer1, 0), layer2=layer2, ok=layer1 > 0,
    )


def budget_line(budget: Budget) -> str:
    return (
        f"[ctx] 预算:window={budget.window} history={budget.history} "
        f"layer1={budget.layer1} layer2={budget.layer2}"
    )


def self_check_lines(budget: Budget, turn_steady: int) -> list[str]:
    """启动自检:预算归零 → 报警;层 1 装不下一整轮 → 告警。"""
    if not budget.ok:
        return [
            f"[ctx] 上下文预算不足:history_budget={budget.history} layer1={budget.layer1}"
            "(请调大 MODEL_CONTEXT_WINDOW 或调小固定开销)"
        ]
    if budget.layer1 < turn_steady:
        return [f"[ctx] 预算告警:layer1={budget.layer1} 装不下完整一轮(约 {turn_steady} token)"]
    return []
