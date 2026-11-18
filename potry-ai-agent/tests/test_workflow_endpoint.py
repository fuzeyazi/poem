"""Ch04 两个新接口的 SSE 契约与落库行为。"""
import json
import time

import pytest
from fastapi.testclient import TestClient

import main


def _token_text(body: str) -> str:
    """把 SSE 里的 token 帧内容拼回完整回答(分块不保证单号连续出现在原始 body)。"""
    pieces = []
    for chunk in body.split("\n\n"):
        event, data = "", ""
        for line in chunk.split("\n"):
            if line.startswith("event: "):
                event = line[7:].strip()
            elif line.startswith("data: "):
                data += line[6:]
        if event == "token" and data:
            pieces.append(json.loads(data).get("content") or "")
    return "".join(pieces)


class FakeInterrupt:
    def __init__(self, value):
        self.value = value


class FakeTask:
    def __init__(self, interrupts=()):
        self.interrupts = interrupts


class FakeState:
    def __init__(self, tasks=()):
        self.tasks = tasks


class FakeWorkflow:
    def __init__(self, final, tasks=()):
        self.final = final
        self.tasks = tasks
        self.records = []

    async def ainvoke(self, payload, config):
        self.records.append((payload, config))
        return self.final

    async def aget_state(self, config):
        return FakeState(self.tasks)


def _client(monkeypatch, final):
    fake = FakeWorkflow(final)
    monkeypatch.setattr(main, "_workflow", fake)
    return TestClient(main.app), fake


def test_workflow_sse_sequence_with_action(monkeypatch):
    final = {
        "route": "complaint",
        "answer": "抱歉,让你有不好的体验了。",
        "actions": ["handoff", "feedback"],
        "tool_trace": [{"tool": "query_poet", "args": {"name": "李白"}, "tool_call_id": "c1",
                        "content": "{}", "durationMs": 12, "status": "done"}],
    }
    client, fake = _client(monkeypatch, final)
    with client.stream("POST", "/agent/workflow", json={"sessionId": "s1", "message": "我要投诉"}) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())
    order = [body.index(f"event: {e}") for e in ("meta", "tool_status", "token", "action", "done")]
    assert order == sorted(order)                # 顺序契约
    assert '"actions": ["handoff", "feedback"]' in body
    assert '"sessionId": "s1"' in body
    assert fake.records[0][1] == {"configurable": {"thread_id": "s1"}}
    assert fake.records[0][0]["user_input"] == "我要投诉"


def test_workflow_plain_answer_has_no_action_event(monkeypatch):
    client, _ = _client(
        monkeypatch,
        {"route": "business", "answer": "是李白", "actions": [], "tool_trace": []},
    )
    with client.stream("POST", "/agent/workflow", json={"sessionId": "s2", "message": "谁写的"}) as resp:
        body = "".join(resp.iter_text())
    assert "event: token" in body and "event: action" not in body and "event: done" in body
    assert '"source": "model"' in body          # 无工具、非预设 → 模型知识作答


def test_workflow_returns_503_when_not_ready(monkeypatch):
    # TestClient 不加 with → 不跑 lifespan,故 _workflow 保持 None
    monkeypatch.setattr(main, "_workflow", None)
    client = TestClient(main.app)
    assert client.post("/agent/workflow", json={"message": "hi"}).status_code == 503


def test_workflow_midstream_failure_emits_error_event(monkeypatch):
    class BoomWorkflow:
        async def ainvoke(self, payload, config):
            raise RuntimeError("graph exploded")

    monkeypatch.setattr(main, "_workflow", BoomWorkflow())
    client = TestClient(main.app)
    with client.stream("POST", "/agent/workflow", json={"sessionId": "s3", "message": "hi"}) as resp:
        body = "".join(resp.iter_text())
    assert "event: error" in body
    assert "event: done" in body          # 收尾仍补 done,契约不缺帧


def test_feedback_endpoint_writes_row(monkeypatch):
    captured = {}

    def fake_add_feedback(message, userid=None):
        captured["message"] = message
        captured["userid"] = userid
        return 42

    monkeypatch.setattr(main.app_storage, "add_feedback", fake_add_feedback)
    client = TestClient(main.app)
    resp = client.post("/agent/feedback", json={"sessionId": "s1", "message": "工单内容"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "feedbackId": 42}
    assert captured["message"] == "工单内容"
    assert captured["userid"] is None


def test_feedback_endpoint_maps_numeric_userid(monkeypatch):
    seen = []
    monkeypatch.setattr(
        main.app_storage, "add_feedback",
        lambda message, userid=None: (seen.append(userid), 1)[1],
    )
    client = TestClient(main.app)
    client.post("/agent/feedback", json={"userId": "1001", "message": "x"})
    client.post("/agent/feedback", json={"userId": "not-a-number", "message": "x"})
    assert seen == [1001, None]


def test_workflow_emits_trace_frame_before_tokens(monkeypatch):
    # 编排轨迹帧:让前端能展示本轮调用链;必须在 token 之前发,面板才能随答案一起出现
    final = {
        "route": "knowledge",
        "answer": "写的是思乡",
        "actions": [],
        "tool_trace": [],
        "intent": "poem_explain",
        "gate_status": "pass",
        "evidence_score": 0.6316,
        "retrieved": [{"id": 1}, {"id": 2}, {"id": 3}],
        "iterations": 1,
        "tokens_used": 1152,
        "started_at": time.monotonic(),
    }
    client, _ = _client(monkeypatch, final)
    with client.stream(
        "POST", "/agent/workflow", json={"sessionId": "s9", "message": "《静夜思》表达了什么感情"}
    ) as resp:
        body = "".join(resp.iter_text())
    assert "event: trace" in body
    assert body.index("event: meta") < body.index("event: trace") < body.index("event: token")
    assert '"intent": "poem_explain"' in body
    assert '"route": "knowledge"' in body
    assert '"gate": "pass"' in body
    assert '"score": 0.6316' in body          # 数值型分数不得被转成字符串
    assert '"retrievedCount": 3' in body
    assert '"iters": 1' in body
    assert '"tokens": 1152' in body
    assert '"elapsedMs":' in body


def test_trace_frame_reports_skipped_branches(monkeypatch):
    # 投诉/闲聊不进 Agent、不检索:轨迹里必须是 skip / 0,不能沿用上一轮或伪造成数值
    final = {
        "route": "complaint",
        "answer": "抱歉,让你有不好的体验了。",
        "actions": ["handoff", "feedback"],
        "tool_trace": [],
        "intent": "complaint",
        "gate_status": "skip",
        "iterations": 0,
        "tokens_used": 0,
    }
    client, _ = _client(monkeypatch, final)
    with client.stream("POST", "/agent/workflow", json={"sessionId": "s10", "message": "我要投诉"}) as resp:
        body = "".join(resp.iter_text())
    assert '"gate": "skip"' in body
    assert '"score": null' in body            # 未检索 → null,而非 0.0 冒充分数
    assert '"retrievedCount": 0' in body
    assert '"iters": 0' in body
    assert '"elapsedMs": null' in body        # 缺 started_at 时不得算出天文数字


@pytest.mark.asyncio
async def test_workflow_tools_isolated_from_chat_registry(monkeypatch):
    monkeypatch.setattr(main.workflow_tools, "_mcp_provider", None)
    wf = {t.name for t in await main.workflow_tools.get_tools()}
    chat = {t.name for t in main.registry.get_tools()}
    assert {"query_poet", "query_dynasty_poems", "create_ticket", "poem_length"} <= wf
    assert "get_my_collection" in wf  # Ch09 打通:个性化工具进 workflow 目录
    assert "draft_forum_post" in wf  # Ch09 打通:文坛草稿工具
    assert "get_study_plan" in wf  # Ch09 打通:SRS 复习计划工具
    assert "query_poem" not in wf
    assert "submit_feedback" not in wf
    assert chat == {"query_poem", "query_poet", "query_dynasty_poems", "get_my_collection", "get_study_plan", "draft_forum_post"}


def _stream(client, payload):
    with client.stream("POST", "/agent/workflow", json=payload) as resp:
        assert resp.status_code == 200
        return "".join(resp.iter_text())


def test_workflow_passes_selected_poem_id_into_state(monkeypatch):
    client, fake = _client(monkeypatch, {"route": "ruling", "answer": "判定", "actions": []})
    _stream(client, {"sessionId": "s20", "message": "", "selectedPoemId": 7})
    assert fake.records[0][0]["selected_poem_id"] == 7
    assert fake.records[0][0]["user_input"] == ""


def test_workflow_emits_pick_poem_frame_and_awaiting_status(monkeypatch):
    final = {
        "route": "ruling", "answer": "先确认一下,你问的是哪首诗?",
        "actions": [], "tool_trace": [], "pending_subflow": True,
        "candidates": [{"poemId": 11, "title": "静夜思", "writer": "李白", "dynasty": "唐", "score": 0.9123}],
    }
    client, _ = _client(monkeypatch, final)
    body = _stream(client, {"sessionId": "s21", "message": "这句合不合律"})
    assert '"action": "pick_poem"' in body
    assert '"poemId": 11' in body
    assert '"status": "awaiting_slot"' in body


def test_workflow_emits_correction_form_frame(monkeypatch):
    final = {
        "route": "ruling", "answer": "这首是七律。", "actions": [], "tool_trace": [],
        "pending_subflow": False, "correction_categories": ["格律错误", "原文有误"],
    }
    client, _ = _client(monkeypatch, final)
    body = _stream(client, {"sessionId": "s22", "message": "这首是不是七律"})
    assert '"action": "open_correction_form"' in body
    assert '"格律错误"' in body
    assert '"status": "ok"' in body


def test_workflow_trace_frame_reports_ch05_fields(monkeypatch):
    final = {
        "route": "ruling", "answer": "判定", "actions": [], "tool_trace": [],
        "intent": "poem_meter", "confidence": 0.83, "query_changed": True,
        "subflow_kind": "meter", "policy_hits": [{"id": 1}, {"id": 2}],
    }
    client, _ = _client(monkeypatch, final)
    body = _stream(client, {"sessionId": "s23", "message": "这句合不合律"})
    assert '"confidence": 0.83' in body
    assert '"queryChanged": true' in body
    assert '"subflowKind": "meter"' in body
    assert '"policyCount": 2' in body


def test_correction_endpoint_writes_row(monkeypatch):
    captured = {}

    def fake_add_correction(category, detail=None, poem_id=None, session_id=None, userid=None):
        captured.update(category=category, detail=detail, poem_id=poem_id, session_id=session_id, userid=userid)
        return 42

    monkeypatch.setattr(main.app_storage, "add_correction", fake_add_correction)
    client = TestClient(main.app)
    resp = client.post(
        "/agent/correction",
        json={"sessionId": "s1", "poemId": 7, "category": "作者张冠李戴", "detail": "作者应为王某"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "correctionId": 42}
    assert captured == {"category": "作者张冠李戴", "detail": "作者应为王某",
                        "poem_id": 7, "session_id": "s1", "userid": None}


def test_correction_endpoint_rejects_unknown_category(monkeypatch):
    client = TestClient(main.app)
    resp = client.post("/agent/correction", json={"category": "乱填类目"})
    assert resp.status_code == 400


def test_trace_frame_carries_poem_id_from_slot_target(monkeypatch):
    final = {
        "route": "ruling", "answer": "判定", "actions": [], "tool_trace": [],
        "subflow_kind": "meter", "slot_target": {"poemId": 2134, "title": "击鼓"},
    }
    client, _ = _client(monkeypatch, final)
    body = _stream(client, {"sessionId": "s30", "message": "这样写合不合律"})
    assert '"poemId": 2134' in body


def test_trace_frame_marks_route_ruling_on_resume(monkeypatch):
    # 续跑轮跳过 classify,route 为空 → 用 subflow_kind 兜底成 ruling
    final = {
        "route": "", "answer": "判定", "actions": [], "tool_trace": [],
        "subflow_kind": "meter", "slot_target": {"poemId": 7}, "policy_hits": [],
    }
    client, _ = _client(monkeypatch, final)
    body = _stream(client, {"sessionId": "s31", "message": "", "selectedPoemId": 7})
    assert '"route": "ruling"' in body


def test_interrupt_emits_confirm_ticket_action_and_awaiting_status(monkeypatch):
    final = {
        "route": "other", "answer": "", "actions": [], "tool_trace": [],
        "__interrupt__": [FakeInterrupt({
            "action": "confirm_ticket",
            "preview": {"ticketType": "内容纠错", "description": "《静夜思》原文有错字"},
            "toolCallId": "tc1",
        })],
    }
    client, _ = _client(monkeypatch, final)
    body = _stream(client, {"sessionId": "s40", "message": "帮我建个工单"})
    assert '"action": "confirm_ticket"' in body
    assert '"ticketType": "内容纠错"' in body
    assert '"status": "awaiting_confirmation"' in body
    assert "event: token" not in body


def test_workflow_rejects_new_message_while_awaiting_confirmation(monkeypatch):
    fake = FakeWorkflow(
        {"answer": ""},
        tasks=(FakeTask(interrupts=(FakeInterrupt({"action": "confirm_ticket"}),)),),
    )
    monkeypatch.setattr(main, "_workflow", fake)
    client = TestClient(main.app)
    resp = client.post("/agent/workflow", json={"sessionId": "s41", "message": "再问一句"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["message"] == "请先确认或取消当前工单"


def test_resume_returns_409_without_pending_interrupt(monkeypatch):
    fake = FakeWorkflow({"answer": "ok"}, tasks=())
    monkeypatch.setattr(main, "_workflow", fake)
    client = TestClient(main.app)
    resp = client.post("/agent/workflow/resume", json={"sessionId": "s42", "confirmed": True})
    assert resp.status_code == 409


def test_resume_confirmed_streams_answer_and_resumes_graph(monkeypatch):
    fake = FakeWorkflow(
        {"route": "other", "answer": "工单已提交,单号 TK000001。",
         "actions": [], "tool_trace": []},
        tasks=(FakeTask(interrupts=(FakeInterrupt({"action": "confirm_ticket"}),)),),
    )
    monkeypatch.setattr(main, "_workflow", fake)
    client = TestClient(main.app)
    with client.stream(
        "POST", "/agent/workflow/resume",
        json={"sessionId": "s43", "confirmed": True},
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    order = [body.index(f"event: {e}") for e in ("meta", "trace", "token", "done")]
    assert order == sorted(order)
    assert "TK000001" in _token_text(body)
    assert '"status": "ok"' in body
    payload, config = fake.records[0]
    assert getattr(payload, "resume", None) == {"confirmed": True}
    assert config == {"configurable": {"thread_id": "s43"}}


def _stream_resume(client, payload):
    with client.stream("POST", "/agent/workflow/resume", json=payload) as resp:
        assert resp.status_code == 200
        return "".join(resp.iter_text())


def test_resume_cancel_streams_cancel_answer(monkeypatch):
    fake = FakeWorkflow(
        {"route": "other", "answer": "好,这次建单已取消。", "actions": [], "tool_trace": []},
        tasks=(FakeTask(interrupts=(FakeInterrupt({"action": "confirm_ticket"}),)),),
    )
    monkeypatch.setattr(main, "_workflow", fake)
    client = TestClient(main.app)
    body = _stream_resume(client, {"sessionId": "s44", "confirmed": False})
    assert "已取消" in _token_text(body)
    assert getattr(fake.records[0][0], "resume", None) == {"confirmed": False}


def test_workflow_emits_forum_draft_frame(monkeypatch):
    final = {
        "route": "knowledge", "answer": "我为你起草了一篇文坛帖子,看看合不合意。",
        "actions": [], "tool_trace": [],
        "forum_draft": {"title": "与月对饮:读李白的三个月夜", "content": "……(正文)", "tag": "诗友分享"},
    }
    client, _ = _client(monkeypatch, final)
    body = _stream(client, {"sessionId": "s23", "message": "帮我写一篇文坛帖子"})
    assert '"action": "forum_draft"' in body
    assert '"title": "与月对饮:读李白的三个月夜"' in body
    assert '"tag": "诗友分享"' in body
