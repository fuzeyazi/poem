from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main
from storage import ChatBase, ChatStorage


def _storage(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'chat.db'}")
    ChatBase.metadata.create_all(engine)
    return ChatStorage(sessionmaker(bind=engine))


def _client(monkeypatch, storage):
    monkeypatch.setattr(main, "storage", storage)
    return TestClient(main.app)


def test_list_conversations_filters_by_user_and_orders_desc(tmp_path, monkeypatch):
    st = _storage(tmp_path)
    st.persist_turn("old", "《静夜思》是谁写的", "李白", userid="u1")
    st.persist_turn("new", "找一首写月亮的诗", "《静夜思》", userid="u1")
    st.persist_turn("other", "别人的会话", "答", userid="u2")
    st.add_summary(1, "梗概", upto_msg_id=2)
    client = _client(monkeypatch, st)
    resp = client.get("/api/conversations", params={"userId": "u1"})
    assert resp.status_code == 200
    data = resp.json()
    assert [c["sessionId"] for c in data] == ["new", "old"]
    assert data[0]["preview"] == "找一首写月亮的诗"
    assert data[1]["summarized"] is True


def test_list_conversations_without_identity_401(tmp_path, monkeypatch):
    """无 token 且无 userId(无身份)→ 401:不允许匿名拉取会话列表。"""
    st = _storage(tmp_path)
    st.persist_turn("a", "问", "答", userid="u1")
    client = _client(monkeypatch, st)
    assert client.get("/api/conversations").status_code == 401


def test_messages_endpoint_returns_user_and_assistant_only(tmp_path, monkeypatch):
    st = _storage(tmp_path)
    st.persist_turn("s1", "问", "答", userid="u1")
    client = _client(monkeypatch, st)
    resp = client.get("/api/conversations/s1/messages", params={"userId": "u1"})
    assert resp.status_code == 200
    assert [r["role"] for r in resp.json()] == ["user", "assistant"]


def test_messages_endpoint_404_on_user_mismatch(tmp_path, monkeypatch):
    st = _storage(tmp_path)
    st.persist_turn("s1", "问", "答", userid="u1")
    client = _client(monkeypatch, st)
    assert client.get("/api/conversations/s1/messages", params={"userId": "u2"}).status_code == 404


def test_messages_endpoint_404_on_missing(tmp_path, monkeypatch):
    client = _client(monkeypatch, _storage(tmp_path))
    resp = client.get("/api/conversations/nope/messages", params={"userId": "u1"})
    assert resp.status_code == 404


def test_list_conversations_500_on_storage_error(monkeypatch):
    class Boom:
        def list_conversations(self, userid=None):
            raise RuntimeError("mysql down")

    monkeypatch.setattr(main, "storage", Boom())
    resp = TestClient(main.app).get("/api/conversations", params={"userId": "u1"})
    assert resp.status_code == 500
