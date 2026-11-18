"""Ch08 验收 2/3/4:闸兜底入池 → 待审队列 → 审核通过 → 复问答对;👎 入池。

前置:MySQL + API 已启动,知识库已建好。
运行:
    .\.venv\Scripts\python.exe evals\accept_ch08_flywheel.py
"""
import json
import sys
import time
from pathlib import Path

import requests
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_settings  # noqa: E402
from db import get_engine  # noqa: E402
from knowledge import PendingQuestion, ReviewQueue  # noqa: E402

BASE = "http://127.0.0.1:8000"


def sse(url: str, payload: dict, timeout: float = 180.0):
    events = []
    with requests.post(url, json=payload, stream=True, timeout=timeout) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"{url} HTTP {resp.status_code}: {resp.text[:300]}")
        buffer = ""
        for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
            if not chunk:
                continue
            buffer += chunk
            while "\n\n" in buffer:
                block, buffer = buffer.split("\n\n", 1)
                event, data = "message", ""
                for line in block.split("\n"):
                    line = line.rstrip("\r")
                    if line.startswith("event: "):
                        event = line[7:].strip()
                    elif line.startswith("data: "):
                        data += line[6:]
                if data:
                    events.append((event, json.loads(data)))
    return events


def chat(session_id: str, message: str):
    events = sse(f"{BASE}/agent/workflow", {
        "sessionId": session_id, "userId": "accept-ch08", "message": message,
    })
    answer = "".join(d.get("content", "") for e, d in events if e == "token")
    trace = next((d for e, d in events if e == "trace"), {})
    done = next((d for e, d in events if e == "done"), {})
    return answer, trace, done


def _factory():
    return sessionmaker(bind=get_engine(load_settings().mysql_url))


def latest_pending(session_id: str, source_entry: str | None = None):
    with _factory()() as session:
        stmt = select(PendingQuestion).where(PendingQuestion.session_id == session_id)
        if source_entry:
            stmt = stmt.where(PendingQuestion.source_entry == source_entry)
        return session.execute(
            stmt.order_by(PendingQuestion.id.desc())
        ).scalars().first()


def wait_matched(pending_id: int, timeout: float = 60.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _factory()() as session:
            row = session.get(PendingQuestion, pending_id)
            if row and row.matched_review_id:
                return row.matched_review_id
        time.sleep(0.5)
    return None


def main() -> int:
    suffix = time.strftime("%H%M%S")
    q1 = f"请解释《秋江夜泊{suffix}》里“孤灯照寒水”的典故出处"
    session1 = f"acc2-gate-{suffix}"

    print(f"=== 验收 2:闸兜底入池 ===\n问题:{q1}")
    answer, trace, done = chat(session1, q1)
    print(f"trace={trace}\nanswer={answer[:120]}")
    if trace.get("gate") != "insufficient":
        print("FAIL: 该问题没有走闸兜底(可能被分到其他出口或已入库)")
        return 1
    pending = latest_pending(session1, "retrieval_gate")
    if pending is None:
        print("FAIL: 问题没有进入 pending_questions")
        return 1
    review_id = wait_matched(pending.id)
    if review_id is None:
        print("FAIL: 飞轮没有在 60s 内把问题放进待审队列")
        return 1
    detail = requests.get(f"{BASE}/api/admin/review/{review_id}", timeout=30).json()
    matched = [p for p in detail.get("pending", []) if p["id"] == pending.id]
    if not matched:
        print("FAIL: 审核详情没有关联这条用户原话")
        return 1
    if not matched[0].get("snapshot"):
        print("FAIL: 审核详情没有召回快照")
        return 1
    print(f"PASS: pending={pending.id} review={review_id} "
          f"snapshot={len(matched[0]['snapshot'])} 条;详情含原话与片段")

    print("\n=== 验收 3:审核通过后复问答对 ===")
    approved = "该句并非引用某一具体典故，而是诗人由秋江夜景生发的羁旅之思。"
    resp = requests.post(
        f"{BASE}/api/admin/review/{review_id}/approve",
        json={"standard_question": q1, "approved_answer": approved}, timeout=120,
    )
    if resp.status_code != 200:
        print(f"FAIL: 审核通过失败 {resp.status_code} {resp.text[:200]}")
        return 1
    print(f"审核通过:chunkId={resp.json().get('chunkId')}")
    answer2, trace2, done2 = chat(f"acc3-reask-{suffix}", q1)
    print(f"trace={trace2}\nanswer={answer2[:220]}")
    if trace2.get("gate") != "pass" or "羁旅" not in answer2:
        print("FAIL: 复问没有放行或回答未使用核准答案")
        return 1
    print("PASS: 同一问题再问已答对")

    print("\n=== 验收 4:👎 入池并进待审队列 ===")
    q2 = "《静夜思》表达了什么感情?"
    session2 = f"acc4-dislike-{suffix}"
    answer3, trace3, _ = chat(session2, q2)
    print(f"trace={trace3}\nanswer={answer3[:120]}")
    resp = requests.post(
        f"{BASE}/agent/feedback/negative",
        json={"sessionId": session2, "message": q2}, timeout=30,
    )
    if resp.status_code != 200:
        print(f"FAIL: 👎 接口失败 {resp.status_code} {resp.text[:200]}")
        return 1
    dislike = latest_pending(session2, "user_dislike")
    if dislike is None:
        print("FAIL: 👎 没有写入 pending_questions")
        return 1
    review2 = wait_matched(dislike.id)
    if review2 is None:
        print("FAIL: 👎 问题没有进入待审队列")
        return 1
    detail2 = requests.get(f"{BASE}/api/admin/review/{review2}", timeout=30).json()
    matched2 = [p for p in detail2.get("pending", []) if p["id"] == dislike.id]
    if not matched2:
        print("FAIL: 待审详情没有关联 👎 的用户原话")
        return 1
    print(f"PASS: pending={dislike.id} review={review2} "
          f"occurrences={detail2.get('occurrences')} 快照={len(matched2[0].get('snapshot') or [])} 条")

    print("\n=== 验收 2/3/4 全部通过 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
