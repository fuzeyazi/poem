"""审核 API:列表/详情/通过写库/驳回/409。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from knowledge import KnowledgeBase, KnowledgeStorage
from review_api import create_review_router


class FakeStore:
    def __init__(self):
        self.rows = []

    def upsert(self, ids, vectors, metadatas):
        self.rows.append((ids, vectors, metadatas))


def _client():
    # TestClient 在独立线程跑路由:内存库需 StaticPool 共享同一连接,否则新连接看不到建好的表
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    KnowledgeBase.metadata.create_all(engine)
    storage = KnowledgeStorage(sessionmaker(bind=engine))
    store = FakeStore()
    app = FastAPI()
    app.include_router(create_review_router(
        storage,
        embed_fn=lambda texts: [[0.1] * 1024 for _ in texts],
        store_factory=lambda: store,
    ))
    return TestClient(app), storage, store


def test_list_and_detail_include_pending_snapshot():
    client, storage, _ = _client()
    rid = storage.create_review("标准问题", "示例答案")
    pid = storage.add_pending_question(
        "用户原话", "s1", source_entry="user_dislike",
        retrieved_snapshot='[{"title": "静夜思", "score": 0.9, "text": "床前明月光"}]',
    )
    storage.mark_pending_matched(pid, rid)
    listing = client.get("/api/admin/review").json()
    assert listing["items"][0]["standard_question"] == "标准问题"
    detail = client.get(f"/api/admin/review/{rid}").json()
    assert detail["pending"][0]["question"] == "用户原话"
    assert detail["pending"][0]["snapshot"][0]["title"] == "静夜思"


def test_approve_writes_chunk_and_marks_embedded():
    client, storage, store = _client()
    rid = storage.create_review("标准问题", "示例答案")
    resp = client.post(f"/api/admin/review/{rid}/approve", json={
        "approved_answer": "核准答案",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert store.rows and store.rows[0][0] == [body["chunkId"]]
    assert storage.get_review(rid)["status"] == "approved"
    assert storage.get_review(rid)["approved_answer"] == "核准答案"
    chunk = storage.get_chunk(body["chunkId"])
    assert chunk["status"] == "embedded"


def test_approve_edit_standard_question_and_answer():
    client, storage, _ = _client()
    rid = storage.create_review("旧问题", "旧答案")
    client.post(f"/api/admin/review/{rid}/approve", json={
        "standard_question": "新问题", "approved_answer": "新答案",
    })
    assert storage.get_review(rid)["standard_question"] == "新问题"


def test_reject_does_not_write_chunk():
    client, storage, _ = _client()
    rid = storage.create_review("问题", "答案")
    resp = client.post(f"/api/admin/review/{rid}/reject")
    assert resp.status_code == 200
    assert storage.get_review(rid)["status"] == "rejected"


def test_approve_non_pending_returns_409():
    client, storage, _ = _client()
    rid = storage.create_review("问题", "答案")
    storage.update_review_status(rid, "approved", approved_answer="x")
    resp = client.post(f"/api/admin/review/{rid}/approve", json={"approved_answer": "y"})
    assert resp.status_code == 409
