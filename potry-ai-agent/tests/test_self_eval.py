import pytest
from langchain_core.messages import AIMessage

from self_eval import assess_answer, self_eval_after_turn


class FakeLLM:
    def __init__(self, content):
        self.content = content

    async def ainvoke(self, prompt):
        return AIMessage(content=self.content)


class FakeStorage:
    def __init__(self):
        self.rows = []

    def add_pending_question(self, question, session_id=None, **kwargs):
        self.rows.append({"question": question, "session_id": session_id, **kwargs})
        return len(self.rows)


class FakeFlywheel:
    def __init__(self):
        self.ids = []

    def schedule(self, pending_id):
        self.ids.append(pending_id)


@pytest.mark.asyncio
async def test_assess_true_for_insufficient():
    result = await assess_answer(FakeLLM('{"insufficient": true, "reason": "缺资料"}'), "q", "a", [])
    assert result["insufficient"] is True


@pytest.mark.asyncio
async def test_self_eval_writes_pool_for_insufficient_answer():
    storage, flywheel = FakeStorage(), FakeFlywheel()
    deps = type("D", (), {"llm": FakeLLM('{"insufficient": true, "reason": "x"}'),
                          "knowledge_storage": storage, "flywheel": flywheel})()
    await self_eval_after_turn(
        {"user_input": "q", "answer": "我不知道", "route": "other",
         "retrieved": [{"id": 1, "title": "静夜思", "score": 0.2, "text": "x"}]},
        deps, "s1",
    )
    assert storage.rows[0]["source_entry"] == "model_self_eval"
    assert flywheel.ids == [1]


@pytest.mark.asyncio
async def test_self_eval_skips_gate_fallback():
    storage, flywheel = FakeStorage(), FakeFlywheel()
    deps = type("D", (), {"llm": FakeLLM('{"insufficient": true}'),
                          "knowledge_storage": storage, "flywheel": flywheel})()
    await self_eval_after_turn(
        {"user_input": "q", "answer": "fallback", "route": "knowledge",
         "gate_status": "insufficient", "retrieved": []},
        deps, "s1",
    )
    assert storage.rows == []
