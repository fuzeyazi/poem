"""真流式(astream_events)路径的帧契约:

- agent 节点的 LLM delta 实时转 token 帧;classify/log 等其他节点的调用不漏进对话流;
- on_tool_start/end 实时转 tool_status 帧(calling→done);
- preset/fallback 等不经 agent LLM 的答案,图结束后按前缀规则补发(未流式→整段;前缀→补差值);
- 发散(流出的与最终 answer 不一致)不补帧,防前端文本重复;
- 装配无 astream_events 时回退伪流式,旧帧序契约不变。
"""
import json
from types import SimpleNamespace

import main


def _sse_events(body: str):
    out = []
    for block in body.split("\n\n"):
        event, data = None, None
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    data = json.loads(line[5:].lstrip())
                except ValueError:
                    data = line[5:].lstrip()
        if event:
            out.append((event, data))
    return out


def _token_text(events) -> str:
    return "".join(d.get("content", "") for e, d in events if e == "token" and isinstance(d, dict))


class _FakeStreamingWorkflow:
    """按 astream_events 契约吐出预置事件;根 chain_end 回给最终状态。无 ainvoke → 走真流式分支。"""

    def __init__(self, events, final):
        self._events = events
        self._final = final

    async def astream_events(self, payload, config=None):
        root = "run-root"
        yield {"event": "on_chain_start", "run_id": root, "name": "LangGraph"}
        for ev in self._events:
            yield ev
        yield {"event": "on_chain_end", "run_id": root, "name": "LangGraph",
               "data": {"output": self._final}}


class _FakeLegacyWorkflow:
    """只有 ainvoke 的旧式替身:验证回退路径(伪流式帧序)仍然可用。"""

    def __init__(self, final):
        self._final = final

    async def ainvoke(self, payload, config=None):
        return self._final


def _chunk(text):
    return SimpleNamespace(content=text)


def _stream_ev(text, node):
    return {"event": "on_chat_model_stream", "name": "FakeChat", "run_id": f"run-{text}-{node}",
            "metadata": {"langgraph_node": node}, "data": {"chunk": _chunk(text)}}


def _post_workflow(monkeypatch, workflow, message="你好"):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(main, "_workflow", workflow)
    client = TestClient(main.app)
    resp = client.post("/agent/workflow", json={"message": message, "userId": "u1"})
    assert resp.status_code == 200
    return resp.text


def test_agent_delta_streams_live_and_classify_filtered(monkeypatch):
    wf = _FakeStreamingWorkflow(
        [_stream_ev("我是", "classify"), _stream_ev("你好", "agent"), _stream_ev("呀", "agent")],
        {"route": "business", "answer": "你好呀", "actions": [], "tool_trace": [], "tokens_used": 10},
    )
    events = _sse_events(_post_workflow(monkeypatch, wf))

    assert _token_text(events) == "你好呀"           # 只流 agent 节点,classify 的"我是"被过滤
    order = [e for e, _ in events]
    assert order.index("meta") < order.index("token") < order.index("trace") < order.index("done")
    assert any(e == "done" and isinstance(d, dict) and d.get("status") == "ok" for e, d in events)


def test_tool_events_stream_realtime_before_tokens(monkeypatch):
    events_raw = [
        {"event": "on_tool_start", "run_id": "t1", "name": "query_poet",
         "data": {"input": {"name": "李白"}}},
        {"event": "on_tool_end", "run_id": "t1", "name": "query_poet"},
        _stream_ev("答案是", "agent"),
        _stream_ev("杜甫。", "agent"),
    ]
    wf = _FakeStreamingWorkflow(
        events_raw,
        {"route": "business", "answer": "答案是杜甫。", "actions": [], "tool_trace": [], "tokens_used": 8},
    )
    events = _sse_events(_post_workflow(monkeypatch, wf))

    statuses = [d for e, d in events if e == "tool_status" and isinstance(d, dict)]
    assert [s["status"] for s in statuses] == ["calling", "done"]
    assert statuses[0]["tool"] == "query_poet"
    assert statuses[0]["args"] == {"name": "李白"}
    assert isinstance(statuses[1].get("durationMs"), int)
    first_token = next(i for i, (e, _) in enumerate(events) if e == "token")
    tool_idxs = [i for i, (e, _) in enumerate(events) if e == "tool_status"]
    assert tool_idxs and all(i < first_token for i in tool_idxs)


def test_preset_answer_replayed_when_no_agent_stream(monkeypatch):
    wf = _FakeStreamingWorkflow([], {"route": "other", "answer": "预设话术", "actions": [],
                                    "tool_trace": [], "tokens_used": 0})
    events = _sse_events(_post_workflow(monkeypatch, wf))
    assert _token_text(events) == "预设话术"          # 图结束后整段补发


def test_prefix_remainder_completed(monkeypatch):
    wf = _FakeStreamingWorkflow(
        [_stream_ev("你好", "agent")],
        {"route": "business", "answer": "你好呀", "actions": [], "tool_trace": [], "tokens_used": 5},
    )
    events = _sse_events(_post_workflow(monkeypatch, wf))
    assert _token_text(events) == "你好呀"            # 补差值"呀"


def test_divergence_does_not_duplicate(monkeypatch):
    wf = _FakeStreamingWorkflow(
        [_stream_ev("ABC", "agent")],
        {"route": "business", "answer": "XYZ", "actions": [], "tool_trace": [], "tokens_used": 5},
    )
    events = _sse_events(_post_workflow(monkeypatch, wf))
    assert _token_text(events) == "ABC"               # 发散不补帧,防前端文本重复
    assert any(e == "done" for e, _ in events)


def test_legacy_fallback_frame_order_preserved(monkeypatch):
    final = {"route": "business", "answer": "是李白", "actions": [{"kind": "x"}],
             "tool_trace": [{"tool": "query_poet", "args": {"name": "李白"}, "tool_call_id": "c1",
                             "content": "{}", "durationMs": 12, "status": "done"}],
             "tokens_used": 100, "intent": "知识问答", "retrieved_count": 3}
    body = _post_workflow(monkeypatch, _FakeLegacyWorkflow(final))
    order = [body.index(f"event: {e}") for e in ("meta", "trace", "tool_status", "token", "action", "done")]
    assert order == sorted(order)                     # 伪流式回退:旧帧序契约不变
