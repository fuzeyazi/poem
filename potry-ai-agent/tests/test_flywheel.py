"""飞轮后台:标准化→查重→建/并队列,失败留待重试,幂等。"""
import asyncio
import threading

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from flywheel import FlywheelService, snapshot_hits
from knowledge import KnowledgeBase, KnowledgeStorage


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def ainvoke(self, prompt):
        self.calls.append(prompt)
        return AIMessage(content=self.replies.pop(0))


def _storage():
    engine = create_engine("sqlite:///:memory:")
    KnowledgeBase.metadata.create_all(engine)
    return KnowledgeStorage(sessionmaker(bind=engine))


def test_snapshot_hits_serializes_top5_with_text():
    hits = [{"id": i, "score": 0.9 - i / 10, "source_type": "poem",
             "title": f"诗{i}", "writer": "李白", "dynasty": "唐", "text": "x" * 500}
            for i in range(7)]
    payload = snapshot_hits(hits)
    assert payload.count('"id"') == 5
    assert "\\u" not in payload
    assert '"title": "诗0"' in payload


@pytest.mark.asyncio
async def test_process_creates_review_and_links_pending():
    storage = _storage()
    pid = storage.add_pending_question("静夜思是谁写的", "s1", source_entry="retrieval_gate")
    llm = FakeLLM([
        '{"standard_question": "《静夜思》的作者是谁?", "example_answer": "李白"}',
        '{"matched_id": null}',
    ])
    service = FlywheelService(storage, llm)
    await service.process_pending(pid)
    review_id = storage.get_pending_question(pid)["matched_review_id"]
    assert review_id is not None
    assert storage.get_review(review_id)["occurrences"] == 1


@pytest.mark.asyncio
async def test_dedup_merges_existing_review():
    storage = _storage()
    rid = storage.create_review("《静夜思》的作者是谁?", "李白")
    pid = storage.add_pending_question("静夜思作者", "s1")
    llm = FakeLLM([
        '{"standard_question": "《静夜思》的作者是谁?", "example_answer": "李白"}',
        f'{{"matched_id": {rid}}}',
    ])
    await FlywheelService(storage, llm).process_pending(pid)
    assert storage.get_review(rid)["occurrences"] == 2
    assert storage.get_pending_question(pid)["matched_review_id"] == rid


@pytest.mark.asyncio
async def test_malformed_standardization_leaves_pending_unmatched():
    storage = _storage()
    pid = storage.add_pending_question("问题", "s1")
    await FlywheelService(storage, FakeLLM(["not json"])).process_pending(pid)
    assert storage.get_pending_question(pid)["matched_review_id"] is None


@pytest.mark.asyncio
async def test_idempotent_second_process_no_new_row():
    storage = _storage()
    pid = storage.add_pending_question("问题", "s1")
    llm = FakeLLM([
        '{"standard_question": "标准", "example_answer": "答案"}',
        '{"matched_id": null}',
    ])
    service = FlywheelService(storage, llm)
    await service.process_pending(pid)
    rid = storage.get_pending_question(pid)["matched_review_id"]
    await service.process_pending(pid)
    assert len(storage.list_reviews()) == 1
    assert storage.get_review(rid)["occurrences"] == 1


@pytest.mark.asyncio
async def test_schedule_from_thread_uses_attached_loop():
    """同步图节点在线程里调用 schedule 时,任务仍投递到主循环执行。"""
    storage = _storage()
    pid = storage.add_pending_question("问题", "s1")
    llm = FakeLLM([
        '{"standard_question": "标准", "example_answer": "答案"}',
        '{"matched_id": null}',
    ])
    service = FlywheelService(storage, llm)
    service.attach_loop(asyncio.get_running_loop())
    thread = threading.Thread(target=service.schedule, args=(pid,))
    thread.start()
    thread.join()
    for _ in range(50):
        if storage.get_pending_question(pid)["matched_review_id"]:
            break
        await asyncio.sleep(0.02)
    assert storage.get_pending_question(pid)["matched_review_id"] is not None


@pytest.mark.asyncio
async def test_drain_processes_unmatched_rows():
    storage = _storage()
    storage.add_pending_question("a", "s1")
    storage.add_pending_question("b", "s2")
    # 首条时待审队列为空,_dedup 不发请求;第二条才会调用查重
    llm = FakeLLM([
        '{"standard_question": "A", "example_answer": "a"}',
        '{"standard_question": "B", "example_answer": "b"}', '{"matched_id": null}',
    ])
    await FlywheelService(storage, llm).drain()
    assert len(storage.list_reviews()) == 2
