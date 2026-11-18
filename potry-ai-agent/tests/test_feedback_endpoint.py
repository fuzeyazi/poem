from fastapi.testclient import TestClient

import main


class FakeState:
    def __init__(self, values):
        self.values = values


class FakeWorkflow:
    def __init__(self, values):
        self.values = values
        self.calls = 0

    async def aget_state(self, config):
        self.calls += 1
        return FakeState(self.values)


class FakeStorage:
    def __init__(self):
        self.rows = []

    def add_pending_question(self, question, session_id=None, **kwargs):
        self.rows.append({"question": question, "session_id": session_id, **kwargs})
        return 1


class FakeFlywheel:
    def __init__(self):
        self.ids = []

    def schedule(self, pending_id):
        self.ids.append(pending_id)


def test_negative_feedback_writes_pool_with_snapshot(monkeypatch):
    storage, flywheel = FakeStorage(), FakeFlywheel()
    monkeypatch.setattr(main, "_workflow", FakeWorkflow({
        "user_input": "静夜思是谁写的", "retrieved": [{"id": 1, "title": "静夜思", "score": 0.9}],
    }))
    monkeypatch.setattr(main, "knowledge_storage", storage)
    monkeypatch.setattr(main, "workflow_deps", type("D", (), {"flywheel": flywheel})())
    client = TestClient(main.app)
    resp = client.post("/agent/feedback/negative", json={
        "sessionId": "s1", "message": "静夜思是谁写的",
    })
    assert resp.status_code == 200
    assert storage.rows[0]["source_entry"] == "user_dislike"
    assert "静夜思" in storage.rows[0]["retrieved_snapshot"]
    assert flywheel.ids == [1]


def test_negative_feedback_mismatch_uses_empty_snapshot(monkeypatch):
    storage, flywheel = FakeStorage(), FakeFlywheel()
    monkeypatch.setattr(main, "_workflow", FakeWorkflow({
        "user_input": "新问题", "retrieved": [{"id": 1, "title": "旧", "score": 0.9}],
    }))
    monkeypatch.setattr(main, "knowledge_storage", storage)
    monkeypatch.setattr(main, "workflow_deps", type("D", (), {"flywheel": flywheel})())
    client = TestClient(main.app)
    resp = client.post("/agent/feedback/negative", json={
        "sessionId": "s1", "message": "旧问题",
    })
    assert resp.status_code == 200
    assert storage.rows[0]["retrieved_snapshot"] == "[]"
