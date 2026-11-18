from dataclasses import dataclass

import context_log
from context_budget import Budget


@dataclass
class FakeHistory:
    summary: str
    layer2: list
    layer1: list
    tokens: int


@dataclass
class FakeAgent:
    messages: list
    summary: str
    layer2: list
    layer1: list
    current: str
    evidence: str
    combined: str
    system: str
    tokens: int
    turn: int


def _hc():
    return FakeHistory(
        summary="用户问过《静夜思》,诉求是核对作者。",
        layer2=[{"id": 3, "role": "user", "content": "问二"}],
        layer1=[{"id": 5, "role": "assistant", "content": "答三"}],
        tokens=42,
    )


def test_history_ctx_block_is_written_and_terminated(tmp_path, monkeypatch, capsys):
    log_file = tmp_path / "app.log"
    monkeypatch.setattr(context_log, "LOG_PATH", log_file)
    monkeypatch.setattr(context_log, "_DISABLE_FILE", False)
    context_log.log_history_ctx("s1", 2, _hc())
    text = log_file.read_text(encoding="utf-8")
    assert "[ctx] history_ctx 会话=s1 轮=2 摘要=用户问过《静夜思》" in text
    assert "  [层2] user: 问二" in text and "  [层1] assistant: 答三" in text
    assert text.rstrip().endswith("[ctx] end history_ctx")
    assert "history_ctx" in capsys.readouterr().out


def test_history_ctx_empty_still_prints_placeholder(tmp_path, monkeypatch):
    log_file = tmp_path / "app.log"
    monkeypatch.setattr(context_log, "LOG_PATH", log_file)
    monkeypatch.setattr(context_log, "_DISABLE_FILE", False)
    context_log.log_history_ctx("s1", 1, FakeHistory("", [], [], 0))
    text = log_file.read_text(encoding="utf-8")
    assert "  (无)" in text and "[ctx] end history_ctx" in text


def test_model_ctx_contains_summary_window_and_ends(tmp_path, monkeypatch):
    log_file = tmp_path / "app.log"
    monkeypatch.setattr(context_log, "LOG_PATH", log_file)
    monkeypatch.setattr(context_log, "_DISABLE_FILE", False)
    ctx = FakeAgent(
        messages=[], summary="用户问过《静夜思》。", layer2=[{"role": "user", "content": "问二"}],
        layer1=[{"role": "assistant", "content": "答三"}], current="问四",
        evidence="【检索资料】床前明月光", combined="【早期梗概】\n用户问过《静夜思》。",
        system="你是青莲", tokens=99, turn=3,
    )
    context_log.log_model_ctx("s2", 3, ctx)
    text = log_file.read_text(encoding="utf-8")
    assert "[ctx] model_ctx 会话=s2 轮=3 摘要=用户问过《静夜思》。 窗口=2条 估算=99token" in text
    assert "  [层2] user: 问二" in text and "  [层1] assistant: 答三" in text
    assert "  [当前] user: 问四" in text and "  [梗概+证据]" in text
    assert text.rstrip().endswith("[ctx] end model_ctx")


def test_model_ctx_summary_head_line_stays_single_line(tmp_path, monkeypatch):
    log_file = tmp_path / "app.log"
    monkeypatch.setattr(context_log, "LOG_PATH", log_file)
    monkeypatch.setattr(context_log, "_DISABLE_FILE", False)
    ctx = FakeAgent(
        messages=[], summary="第一段事实\n第二段事实", layer2=[], layer1=[], current="",
        evidence="", combined="", system="你是青莲", tokens=1, turn=1,
    )
    context_log.log_model_ctx("s2", 1, ctx)
    head = log_file.read_text(encoding="utf-8").splitlines()[0]
    assert "摘要=第一段事实 第二段事实" in head


def test_log_write_failure_is_tolerated(tmp_path, monkeypatch):
    # 目录位置被普通文件占住:写失败只告警,不抛异常
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(context_log, "LOG_PATH", blocker / "app.log")
    monkeypatch.setattr(context_log, "_DISABLE_FILE", False)
    context_log.log_history_ctx("s1", 1, FakeHistory("", [], [], 0))   # 不抛即通过


def test_budget_line_and_self_check(tmp_path, monkeypatch):
    log_file = tmp_path / "app.log"
    monkeypatch.setattr(context_log, "LOG_PATH", log_file)
    monkeypatch.setattr(context_log, "_DISABLE_FILE", False)
    budget = Budget(64000, 4000, 2000, 4800, 4750, 48450, 16000, 11199, 4800, True)
    context_log.log_budget(budget, turn_steady=400)
    text = log_file.read_text(encoding="utf-8")
    assert "[ctx] 预算:window=64000 history=16000 layer1=11199 layer2=4800" in text
    assert "预算告警" not in text
