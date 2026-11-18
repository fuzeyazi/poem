"""数据飞轮后台:标准化 → 查重 → 入待审队列。"""
import asyncio
import json
import re

from prompts import DEDUP_PROMPT, STANDARDIZE_PROMPT


def snapshot_hits(hits: list[dict], top_n: int = 5) -> str:
    rows = [
        {
            "id": h.get("id"), "source_type": h.get("source_type"),
            "title": h.get("title"), "writer": h.get("writer"),
            "dynasty": h.get("dynasty"), "score": h.get("score"),
            "text": (h.get("text") or "")[:400],
        }
        for h in (hits or [])[:top_n]
    ]
    return json.dumps(rows, ensure_ascii=False, default=str)


def _parse_json(text: str) -> dict | None:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


class FlywheelService:
    def __init__(self, storage, llm, *, max_dedup_candidates: int = 50) -> None:
        self._storage = storage
        self._llm = llm
        self._max = max_dedup_candidates
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """记录主事件循环:同步图节点在线程里调用 schedule 时用它投递任务。"""
        self._loop = loop

    def _track(self, task: asyncio.Task) -> None:
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def schedule(self, pending_id: int) -> None:
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        loop = running or self._loop
        if loop is None or loop.is_closed():
            return
        if running is loop:
            self._track(loop.create_task(self.process_pending(pending_id)))
        else:
            loop.call_soon_threadsafe(
                lambda: self._track(loop.create_task(self.process_pending(pending_id)))
            )

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()

    async def drain(self, limit: int = 50) -> int:
        processed = 0
        for row in self._storage.list_unmatched_pending(limit):
            await self.process_pending(row["id"])
            processed += 1
        return processed

    async def process_pending(self, pending_id: int) -> None:
        async with self._lock:
            pending = self._storage.get_pending_question(pending_id)
            if not pending or pending["matched_review_id"]:
                return
            standardized = await self._standardize(pending)
            if standardized is None:
                return
            candidates = self._storage.list_reviews(status="pending", limit=self._max)
            matched_id = await self._dedup(standardized["standard_question"], candidates)
            if matched_id:
                self._storage.increment_review_occurrences(matched_id)
                review_id = matched_id
            else:
                review_id = self._storage.create_review(
                    standardized["standard_question"], standardized["example_answer"],
                )
            self._storage.mark_pending_matched(pending_id, review_id)

    async def _standardize(self, pending: dict) -> dict | None:
        try:
            message = await self._llm.ainvoke(STANDARDIZE_PROMPT.invoke({
                "question": pending["question"],
                "evidence": pending.get("retrieved_snapshot") or "[]",
            }))
            data = _parse_json(message.content or "")
            if not data:
                return None
            question = str(data.get("standard_question") or "").strip()
            answer = str(data.get("example_answer") or "").strip()
            if not question or not answer:
                return None
            return {"standard_question": question[:500], "example_answer": answer[:2000]}
        except Exception as exc:  # noqa: BLE001 - 后台失败留待重试
            print(f"[flywheel] standardize fail id={pending['id']}: {str(exc)[:160]}")
            return None

    async def _dedup(self, question: str, candidates: list[dict]) -> int | None:
        if not candidates:
            return None
        lines = "\n".join(f"{c['id']}. {c['standard_question']}" for c in candidates)
        try:
            message = await self._llm.ainvoke(DEDUP_PROMPT.invoke({
                "question": question, "candidates": lines,
            }))
            data = _parse_json(message.content or "")
        except Exception as exc:  # noqa: BLE001
            print(f"[flywheel] dedup fail: {str(exc)[:160]}")
            return None
        if not data or data.get("matched_id") is None:
            return None
        try:
            matched = int(data["matched_id"])
        except (TypeError, ValueError):
            return None
        return matched if any(c["id"] == matched for c in candidates) else None
