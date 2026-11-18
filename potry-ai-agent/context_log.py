"""上下文可观测:统一追加写 log/app.log 并同步 stdout(spec §9)。"""
import os
from pathlib import Path

from context_budget import Budget, budget_line, self_check_lines

LOG_PATH = Path(__file__).resolve().parent / "log" / "app.log"
_DISABLE_FILE = os.getenv("CTX_LOG_DISABLE", "").strip().lower() in ("1", "true")


def _write(line: str) -> None:
    print(line)
    if _DISABLE_FILE:
        return
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception as exc:  # noqa: BLE001 - 日志失败不影响对话
        print(f"[ctx] 日志写入失败: {str(exc)[:200]}")


def _clip(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "…"


def log_line(line: str) -> None:
    """事件日志(层 1 降级 / 摘要生命周期)同样落 app.log,便于验收 grep。"""
    _write(line)


def log_history_ctx(session_id: str, turn: int, hc) -> None:
    """消解/意图共用的历史:摘要一行 + 滑窗;每轮必打,空历史也打 (无)。"""
    summary = _clip((hc.summary or "").replace("\n", " "), 80) if hc.summary else "(无)"
    lines = [
        f"[ctx] history_ctx 会话={session_id or '-'} 轮={turn} 摘要={summary} "
        f"滑窗={len(hc.layer2) + len(hc.layer1)}条 估算={hc.tokens}token"
    ]
    for row in hc.layer2:
        lines.append(f"  [层2] {row.get('role')}: {row.get('content')}")
    for row in hc.layer1:
        lines.append(f"  [层1] {row.get('role')}: {row.get('content')}")
    if len(lines) == 1:
        lines.append("  (无)")
    lines.append("[ctx] end history_ctx")
    _write("\n".join(lines))


def log_model_ctx(session_id: str, turn: int, ctx) -> None:
    """主力 Agent 实际发出的上下文:摘要全文 + 滑窗逐条 + 条数 + 估算。"""
    summary = (ctx.summary or "(无)").replace("\n", " ")
    lines = [
        f"[ctx] model_ctx 会话={session_id or '-'} 轮={turn} 摘要={summary} "
        f"窗口={len(ctx.layer2) + len(ctx.layer1)}条 估算={ctx.tokens}token",
        f"  [system] {_clip(ctx.system, 80)}",
    ]
    for row in ctx.layer2:
        lines.append(f"  [层2] {row.get('role')}: {row.get('content')}")
    for row in ctx.layer1:
        lines.append(f"  [层1] {row.get('role')}: {row.get('content')}")
    lines.append(f"  [当前] user: {ctx.current}")
    lines.append(f"  [梗概+证据] {ctx.combined or '(无)'}")
    lines.append("[ctx] end model_ctx")
    _write("\n".join(lines))


def log_budget(budget: Budget, turn_steady: int) -> None:
    _write(budget_line(budget))
    for line in self_check_lines(budget, turn_steady):
        _write(line)
