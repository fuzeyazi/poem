"""后台异步摘要(spec §7):层 2 超预算 → 整批压一段 → 追加摘要表并推进锚点。"""
import asyncio
import time

from context_budget import estimate_rows_tokens
from context_layers import turn_groups
from context_log import log_line
from prompts import SUMMARY_PROMPT

_tasks: set[asyncio.Task] = set()
_scheduled: set[str] = set()
_locks: dict[str, asyncio.Lock] = {}

_ROLE_NAMES = {"user": "用户", "assistant": "青莲"}


def lock_for(session_id: str) -> asyncio.Lock:
    return _locks.setdefault(session_id, asyncio.Lock())


def reset_for_tests() -> None:
    _tasks.clear()
    _scheduled.clear()
    _locks.clear()


def format_transcript(rows: list[dict]) -> str:
    return "\n".join(
        f"{_ROLE_NAMES.get(row.get('role'), row.get('role') or '-')}: {row.get('content') or ''}"
        for row in rows
    )


def schedule_summary(
    deps, session_id: str, conversation_id: int, from_id: int, to_id: int, layer2_tokens: int
) -> None:
    """投递后台任务后立即返回;同一会话已有任务在跑则跳过。"""
    lock = lock_for(session_id)
    if session_id in _scheduled or lock.locked():
        log_line(f"summary skip 会话={session_id}(已有任务)")
        return
    log_line(
        f"summary trigger 会话={session_id} 层2 约 {layer2_tokens} token > 预算 {deps.budget.layer2}"
    )
    _scheduled.add(session_id)

    def _done(task, sid=session_id):
        _tasks.discard(task)
        _scheduled.discard(sid)
        active = _locks.get(sid)
        if active is not None and not active.locked():
            _locks.pop(sid, None)

    task = asyncio.create_task(_run(deps, session_id, conversation_id, from_id, to_id, lock))
    _tasks.add(task)
    task.add_done_callback(_done)


def _cap_batch(rows: list[dict], max_tokens: int) -> list[dict]:
    """超 SUMMARY_BATCH_MAX_TOKENS 时只取最旧的完整轮;至少压一轮。"""
    kept: list[dict] = []
    total = 0
    for group in turn_groups(rows):
        group_tokens = estimate_rows_tokens(group)
        if kept and total + group_tokens > max_tokens:
            break
        kept.extend(group)
        total += group_tokens
    return kept or turn_groups(rows)[0]


async def _run(deps, session_id: str, conversation_id: int, from_id: int, to_id: int, lock) -> None:
    async with lock:
        started = time.monotonic()
        try:
            snapshot = deps.chat_storage.load_context(session_id)
            rows = [
                row for row in snapshot.get("rows") or []
                if from_id < (row.get("id") or 0) <= to_id
            ]
            if not rows:
                log_line(f"summary skip 会话={session_id}(无内容)")
                return
            batch = _cap_batch(rows, deps.settings.summary_batch_max_tokens)
            upto = batch[-1]["id"]
            log_line(
                f"summary start 会话={session_id} 覆盖 {batch[0]['id']}..{upto}({len(batch)} 条)"
            )
            reply = await deps.llm.ainvoke(
                SUMMARY_PROMPT.invoke({"history": format_transcript(batch)})
            )
            content = (reply.content or "").strip()
            if not content:
                raise RuntimeError("空梗概")
            seq = deps.chat_storage.add_summary(conversation_id, content, upto)
            if seq is None:
                log_line(f"summary skip 会话={session_id}(已有同段)")
                return
            elapsed = int((time.monotonic() - started) * 1000)
            log_line(f"summary done 会话={session_id} 第 {seq} 段 覆盖到 {upto} 耗时 {elapsed}ms")
        except asyncio.CancelledError:
            log_line(f"summary skip 会话={session_id}(服务关闭)")
            raise
        except Exception as exc:  # noqa: BLE001 - 失败锚点不动,下一轮可重试
            log_line(f"summary fail 会话={session_id}: {str(exc)[:200]}")


async def wait_all() -> None:
    """测试用:等待当前所有摘要任务结束。"""
    tasks = list(_tasks)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def shutdown() -> None:
    tasks = list(_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
