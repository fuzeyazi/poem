import asyncio

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import summarizer
from config import Settings
from context_budget import derive_budget
from storage import ChatBase, ChatStorage


class FakeLLM:
    def __init__(self, reply="用户问过《静夜思》并核对作者,尚未确认朝代。", boom=False):
        self.reply = reply
        self.boom = boom
        self.prompts = []

    async def ainvoke(self, messages):
        self.prompts.append(messages)
        if self.boom:
            raise ConnectionError("upstream down")
        return AIMessage(content=self.reply)


class FakeDeps:
    def __init__(self, storage, llm, **over):
        base = dict(
            llm_base_url="http://fake", llm_api_key="sk-fake", llm_model="fake",
            history_max_tokens=2000, llm_temperature=0.7,
            mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
        )
        base.update(over)
        self.settings = Settings(**base)
        self.chat_storage = storage
        self.llm = llm
        self.budget = derive_budget(self.settings)


def make_storage():
    engine = create_engine("sqlite:///:memory:")
    ChatBase.metadata.create_all(engine)
    return ChatStorage(sessionmaker(bind=engine))


def seed_two_turns(storage):
    storage.persist_turn("s1", "《静夜思》是谁写的", "是李白")
    storage.persist_turn("s1", "他是什么朝代的", "唐代")
    return storage.load_context("s1")


@pytest.fixture(autouse=True)
def _reset_state():
    summarizer.reset_for_tests()
    yield
    summarizer.reset_for_tests()


@pytest.mark.asyncio
async def test_summary_appends_paragraph_and_moves_anchor(capsys):
    storage = make_storage()
    seed_two_turns(storage)
    deps = FakeDeps(storage, FakeLLM())
    summarizer.schedule_summary(deps, "s1", 1, from_id=0, to_id=4, layer2_tokens=5000)
    await summarizer.wait_all()
    snapshot = storage.load_context("s1")
    assert snapshot["summaryUpto"] == 4
    assert snapshot["summaries"][0]["content"].startswith("用户问过")
    out = capsys.readouterr().out
    assert "summary trigger 会话=s1 层2 约 5000 token > 预算" in out
    assert "summary start 会话=s1 覆盖 1..4(4 条)" in out
    assert "summary done 会话=s1 第 1 段 覆盖到 4 耗时" in out


@pytest.mark.asyncio
async def test_summary_failure_keeps_anchor(capsys):
    storage = make_storage()
    seed_two_turns(storage)
    deps = FakeDeps(storage, FakeLLM(boom=True))
    summarizer.schedule_summary(deps, "s1", 1, from_id=0, to_id=4, layer2_tokens=5000)
    await summarizer.wait_all()
    snapshot = storage.load_context("s1")
    assert snapshot["summaryUpto"] == 0 and snapshot["summaries"] == []
    assert "summary fail 会话=s1" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_summary_skips_when_task_already_running(capsys):
    storage = make_storage()
    seed_two_turns(storage)
    deps = FakeDeps(storage, FakeLLM())
    lock = summarizer.lock_for("s1")
    await lock.acquire()
    try:
        summarizer.schedule_summary(deps, "s1", 1, from_id=0, to_id=4, layer2_tokens=5000)
        out = capsys.readouterr().out
        assert "summary skip 会话=s1(已有任务)" in out
        assert "summary trigger" not in out
    finally:
        lock.release()
    await summarizer.wait_all()


@pytest.mark.asyncio
async def test_schedule_dedupes_before_task_starts(capsys):
    storage = make_storage()
    seed_two_turns(storage)
    deps = FakeDeps(storage, FakeLLM())
    summarizer.schedule_summary(deps, "s1", 1, from_id=0, to_id=4, layer2_tokens=5000)
    summarizer.schedule_summary(deps, "s1", 1, from_id=0, to_id=4, layer2_tokens=5000)
    out = capsys.readouterr().out
    assert out.count("summary skip 会话=s1(已有任务)") == 1
    await summarizer.wait_all()
    assert len(storage.load_context("s1")["summaries"]) == 1


@pytest.mark.asyncio
async def test_summary_skips_when_no_rows(capsys):
    storage = make_storage()
    storage.persist_turn("s1", "问", "答")
    deps = FakeDeps(storage, FakeLLM())
    summarizer.schedule_summary(deps, "s1", 1, from_id=0, to_id=0, layer2_tokens=5000)
    await summarizer.wait_all()
    assert "summary skip 会话=s1(无内容)" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_batch_cap_advances_only_to_compressed_position(capsys):
    storage = make_storage()
    for i in range(4):
        storage.persist_turn("s1", f"问题{i}" * 20, f"回答{i}" * 20)
    deps = FakeDeps(storage, FakeLLM(), summary_batch_max_tokens=60)
    summarizer.schedule_summary(deps, "s1", 1, from_id=0, to_id=8, layer2_tokens=5000)
    await summarizer.wait_all()
    snapshot = storage.load_context("s1")
    assert 0 < snapshot["summaryUpto"] < 8
    assert "summary done" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_schedule_returns_without_waiting_for_model():
    storage = make_storage()
    seed_two_turns(storage)

    class SlowLLM(FakeLLM):
        async def ainvoke(self, messages):
            await asyncio.sleep(0.2)
            return AIMessage(content="慢梗概")

    deps = FakeDeps(storage, SlowLLM())
    started = asyncio.get_event_loop().time()
    summarizer.schedule_summary(deps, "s1", 1, from_id=0, to_id=4, layer2_tokens=5000)
    elapsed = asyncio.get_event_loop().time() - started
    assert elapsed < 0.1                      # 投递即返回,不阻塞当前轮
    await summarizer.wait_all()


@pytest.mark.asyncio
async def test_shutdown_cancels_and_awaits_tasks(capsys):
    storage = make_storage()
    seed_two_turns(storage)

    class SlowLLM(FakeLLM):
        async def ainvoke(self, messages):
            await asyncio.sleep(10)
            return AIMessage(content="慢梗概")

    deps = FakeDeps(storage, SlowLLM())
    summarizer.schedule_summary(deps, "s1", 1, from_id=0, to_id=4, layer2_tokens=5000)
    await asyncio.sleep(0.05)                 # 让任务真正进入锁内并阻塞在模型调用
    await summarizer.shutdown()
    assert not summarizer._tasks
    assert "summary skip 会话=s1(服务关闭)" in capsys.readouterr().out
