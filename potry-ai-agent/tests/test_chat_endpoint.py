import json

from fastapi.testclient import TestClient

import main


def make_client(monkeypatch, stream_fn):
    monkeypatch.setattr(main.service, "stream_events", stream_fn)
    return TestClient(main.app)


def test_sse_event_sequence_with_tool(monkeypatch):
    # 按真实 stream_events 契约打桩:只产 tool_status/token/done,meta 由路由合成
    async def fake_stream(session_id, message):
        yield ("tool_status", {"tool": "query_poem", "status": "calling", "args": {"keyword": "静夜思"}, "durationMs": 0})
        yield ("tool_status", {"tool": "query_poem", "status": "done", "args": {"keyword": "静夜思"}, "durationMs": 12})
        yield ("token", {"content": "你"})
        yield ("token", {"content": "好"})
        yield ("done", {})

    client = make_client(monkeypatch, fake_stream)
    with client.stream("POST", "/agent/chat", json={"sessionId": "s1", "message": "hi"}) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join(resp.iter_text())
    assert "event: meta" in body
    assert "event: tool_status" in body
    assert body.index("event: meta") < body.index("event: tool_status") < body.index("event: token") < body.index("event: done")
    # done 由路由补齐 sessionId(服务只产空 payload),按 spec §7 契约断言
    assert json.dumps({"sessionId": "s1"}, ensure_ascii=False) in body
    assert json.dumps({"tool": "query_poem", "status": "calling"}, ensure_ascii=False) not in body  # 整包校验下面这行
    assert '"tool": "query_poem"' in body


def test_plain_flow_without_tools(monkeypatch):
    async def fake_stream(session_id, message):
        yield ("token", {"content": "你好"})
        yield ("done", {})

    client = make_client(monkeypatch, fake_stream)
    with client.stream("POST", "/agent/chat", json={"message": "hi"}) as resp:
        body = "".join(resp.iter_text())
    assert "event: meta" in body
    assert "event: token" in body
    assert "event: done" in body
    assert "event: tool_status" not in body


def test_upstream_failure_before_stream_returns_502(monkeypatch):
    async def broken_stream(session_id, message):
        raise ConnectionError("connect refused")
        yield  # pragma: no cover

    client = make_client(monkeypatch, broken_stream)
    resp = client.post("/agent/chat", json={"message": "hi"})
    assert resp.status_code == 502


def test_midstream_error_emits_error_event(monkeypatch):
    async def flaky_stream(session_id, message):
        yield ("token", {"content": "半句"})
        raise ConnectionError("reset")

    client = make_client(monkeypatch, flaky_stream)
    with client.stream("POST", "/agent/chat", json={"sessionId": "s1", "message": "hi"}) as resp:
        body = "".join(resp.iter_text())
    assert "event: token" in body
    assert "event: error" in body
    assert "event: done" not in body


def test_done_synthesized_when_stream_ends_without_done(monkeypatch):
    # 服务流正常耗尽但漏产 done 时,路由兜底补发带 sessionId 的 done,契约收尾不缺帧
    async def no_done_stream(session_id, message):
        yield ("token", {"content": "答"})

    client = make_client(monkeypatch, no_done_stream)
    with client.stream("POST", "/agent/chat", json={"sessionId": "s1", "message": "hi"}) as resp:
        body = "".join(resp.iter_text())
    assert "event: done" in body
    assert json.dumps({"sessionId": "s1"}, ensure_ascii=False) in body
    assert "event: error" not in body


def test_chat_page_is_not_heuristically_cached():
    # 静态页每章都会改,必须禁止启发式缓存,否则老用户会一直看到旧 UI(Ch04 实测踩到)
    client = TestClient(main.app)
    resp = client.get("/chat")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-cache"
