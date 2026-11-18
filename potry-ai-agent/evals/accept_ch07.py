"""Ch07 验收脚本:真实 HTTP + 真实模型 + MySQL 审计核对。

用法(服务已启动):
    .\\.venv\\Scripts\\python.exe evals\\accept_ch07.py --phase main
    .\\.venv\\Scripts\\python.exe evals\\accept_ch07.py --phase mcp-new
    .\\.venv\\Scripts\\python.exe evals\\accept_ch07.py --phase timeout
"""
import argparse
import json
import sys
import time
from pathlib import Path

import requests
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_storage import AppStorage, Ticket, ToolAuditLog  # noqa: E402
from config import load_settings  # noqa: E402
from db import get_engine  # noqa: E402

BASE = "http://127.0.0.1:8000"


def sse(url: str, payload: dict, timeout: float = 120.0):
    """POST 并解析 SSE,返回 [(event, data), ...]。"""
    events = []
    with requests.post(url, json=payload, stream=True, timeout=timeout) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"{url} HTTP {resp.status_code}: {resp.text[:300]}")
        buffer = ""
        for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
            if not chunk:
                continue
            buffer += chunk
            while "\n\n" in buffer:
                block, buffer = buffer.split("\n\n", 1)
                event, data = "message", ""
                for line in block.split("\n"):
                    line = line.rstrip("\r")
                    if line.startswith("event: "):
                        event = line[7:].strip()
                    elif line.startswith("data: "):
                        data += line[6:]
                if data:
                    events.append((event, json.loads(data)))
    return events


def chat(session_id: str, message: str):
    return sse(
        f"{BASE}/agent/workflow",
        {"sessionId": session_id, "userId": "accept-ch07", "message": message},
    )


def resume(session_id: str, confirmed: bool):
    return sse(
        f"{BASE}/agent/workflow/resume",
        {"sessionId": session_id, "confirmed": confirmed},
    )


def summarize(events):
    answer = "".join(
        data.get("content", "") for event, data in events if event == "token"
    )
    tools = [data.get("tool") for event, data in events if event == "tool_status"]
    actions = [data for event, data in events if event == "action"]
    done = next((data for event, data in events if event == "done"), {})
    return answer, tools, actions, done


def show(label, events):
    answer, tools, actions, done = summarize(events)
    print(f"\n[{label}] tools={tools} actions={actions} done={done}")
    print(f"[{label}] answer={answer}")
    return answer, tools, actions, done


def db_rows(session_id=None, tool_name=None, limit=5):
    settings = load_settings()
    factory = sessionmaker(bind=get_engine(settings.mysql_url))
    with factory() as session:
        stmt = select(ToolAuditLog).order_by(ToolAuditLog.id.desc()).limit(limit)
        if session_id:
            stmt = stmt.where(ToolAuditLog.session_id == session_id)
        if tool_name:
            stmt = stmt.where(ToolAuditLog.tool_name == tool_name)
        return session.execute(stmt).scalars().all()


def ticket_count() -> int:
    settings = load_settings()
    factory = sessionmaker(bind=get_engine(settings.mysql_url))
    with factory() as session:
        return session.execute(select(func.count()).select_from(Ticket)).scalar()


def ticket_rows(session_id):
    settings = load_settings()
    factory = sessionmaker(bind=get_engine(settings.mysql_url))
    with factory() as session:
        return session.execute(
            select(Ticket).where(Ticket.session_id == session_id).order_by(Ticket.id.desc())
        ).scalars().all()


def phase_main():
    print("=== 验收 1:插件即插即用(poem_reverse,API 启动后新增)===")
    show("acc1", chat("acc1", "必须调用 poem_reverse 工具,把「床前明月光」倒过来返回"))

    print("\n=== 验收 2a:档案 MCP ===")
    show("acc2a", chat("acc2a", "查一下《静夜思》的诗库档案"))
    print("\n=== 验收 2b:判定 MCP ===")
    show("acc2b", chat("acc2b", "查一下《春望》的判定记录"))

    print("\n=== 验收 4:建单确认 ===")
    show("acc4-1", chat("acc4", "帮我建个工单"))
    answer, tools, actions, done = show(
        "acc4-2", chat("acc4", "原文有错字,《静夜思》第二句应为床前明月光")
    )
    confirm = [a for a in actions if a.get("action") == "confirm_ticket"]
    if not confirm:
        print("[acc4] 未出现工单预览,停止")
    else:
        print(f"[acc4] preview={confirm[0].get('preview')}")
        before = ticket_count()
        answer, tools, actions, done = show("acc4-resume", resume("acc4", True))
        after = ticket_count()
        rows = ticket_rows("acc4")
        audits = db_rows(session_id="acc4", tool_name="create_ticket", limit=1)
        print(f"[acc4] tickets {before}->{after}, rows={[(r.ticket_no, r.description) for r in rows]}")
        print(f"[acc4] audit={[(a.status, a.retry_count, a.source) for a in audits]}")
        assert after == before + 1, "确认后 tickets 未新增"
        assert "TK" in answer, "回复未带工单号"
        assert audits and audits[0].status == "success", "create_ticket 审计不是 success"

    print("\n=== 验收 5:取消建单 ===")
    show("acc5-1", chat("acc5", "帮我建个工单"))
    answer, tools, actions, done = show(
        "acc5-2", chat("acc5", "原文有错字,《静夜思》第二句应为床前明月光")
    )
    confirm = [a for a in actions if a.get("action") == "confirm_ticket"]
    if not confirm:
        print("[acc5] 未出现工单预览,停止")
    else:
        before = ticket_count()
        answer, tools, actions, done = show("acc5-resume", resume("acc5", False))
        after = ticket_count()
        audits = db_rows(session_id="acc5", tool_name="create_ticket", limit=1)
        print(f"[acc5] tickets {before}->{after}, audit={[(a.status, a.retry_count) for a in audits]}")
        assert after == before, "取消后 tickets 不应新增"
        assert audits and audits[0].status == "permission_denied", "取消审计不是 permission_denied"
        assert "取消" in answer, "取消回复未说明已取消"
    print("\n=== 验收 main 完成 ===")


def phase_live():
    stamp = int(time.time())
    s1 = f"acc1-live-{stamp}"
    s2a = f"acc2a-live-{stamp}"
    s2b = f"acc2b-live-{stamp}"

    print(f"=== 验收 1:插件即插即用(session={s1})===")
    answer, tools, actions, done = show(
        "acc1", chat(s1, "必须调用 poem_reverse 工具,把「床前明月光」倒过来返回")
    )
    a1 = db_rows(session_id=s1, tool_name="poem_reverse", limit=1)
    print(f"[acc1] audit={[(a.status, a.source) for a in a1]}")
    assert "poem_reverse" in tools, "Agent 未调用 poem_reverse"
    assert a1 and a1[0].source == "builtin", "poem_reverse 审计来源不是 builtin"

    print(f"\n=== 验收 2a:档案 MCP(session={s2a})===")
    answer, tools, actions, done = show(
        "acc2a", chat(s2a, "查一下《静夜思》的诗库档案")
    )
    a2a = db_rows(session_id=s2a, tool_name="poem_archive_lookup", limit=1)
    print(f"[acc2a] audit={[(a.status, a.source) for a in a2a]}")
    assert "poem_archive_lookup" in tools, "Agent 未调用档案 MCP"
    assert a2a and a2a[0].source == "mcp:poetry_archive", "档案审计来源不对"

    print(f"\n=== 验收 2b:判定 MCP(session={s2b})===")
    answer, tools, actions, done = show(
        "acc2b", chat(s2b, "查一下《春望》的判定记录")
    )
    a2b = db_rows(session_id=s2b, tool_name="judgement_status_lookup", limit=1)
    print(f"[acc2b] audit={[(a.status, a.source) for a in a2b]}")
    assert "judgement_status_lookup" in tools, "Agent 未调用判定 MCP"
    assert a2b and a2b[0].source == "mcp:judgement", "判定审计来源不对"
    print("\n=== 验收 1/2 完成 ===")


def phase_ticket():
    stamp = str(int(time.time()))
    s4 = f"acc4-ticket-{stamp}"
    s5 = f"acc5-cancel-{stamp}"

    print(f"=== 验收 4:建单确认(session={s4})===")
    show("acc4-1", chat(s4, "帮我建个工单"))
    answer, tools, actions, done = show(
        "acc4-2", chat(s4, "帮我建个工单,原文有错字,《静夜思》第二句应为床前明月光")
    )
    confirm = [a for a in actions if a.get("action") == "confirm_ticket"]
    if not confirm:
        print("[acc4] 未出现工单预览,停止")
        return
    print(f"[acc4] preview={confirm[0].get('preview')}")
    before = ticket_count()
    answer, tools, actions, done = show("acc4-resume", resume(s4, True))
    after = ticket_count()
    rows = ticket_rows(s4)
    audits = db_rows(session_id=s4, tool_name="create_ticket", limit=1)
    print(f"[acc4] tickets {before}->{after}, rows={[(r.ticket_no, r.description) for r in rows]}")
    print(f"[acc4] audit={[(a.status, a.retry_count, a.source) for a in audits]}")
    assert after == before + 1, "确认后 tickets 未新增"
    assert "TK" in answer, "回复未带工单号"
    assert audits and audits[0].status == "success", "create_ticket 审计不是 success"

    print(f"\n=== 验收 5:取消建单(session={s5})===")
    show("acc5-1", chat(s5, "帮我建个工单"))
    answer, tools, actions, done = show(
        "acc5-2", chat(s5, "帮我建个工单,原文有错字,《静夜思》第二句应为床前明月光")
    )
    confirm = [a for a in actions if a.get("action") == "confirm_ticket"]
    if not confirm:
        print("[acc5] 未出现工单预览,停止")
        return
    before = ticket_count()
    answer, tools, actions, done = show("acc5-resume", resume(s5, False))
    after = ticket_count()
    audits = db_rows(session_id=s5, tool_name="create_ticket", limit=1)
    print(f"[acc5] tickets {before}->{after}, audit={[(a.status, a.retry_count) for a in audits]}")
    assert after == before, "取消后 tickets 不应新增"
    assert audits and audits[0].status == "permission_denied", "取消审计不是 permission_denied"
    assert "取消" in answer, "取消回复未说明已取消"
    print("\n=== 验收 ticket 完成 ===")


def phase_cancel():
    s5 = f"acc5-cancel-{int(time.time())}"
    print(f"=== 验收 5:取消建单(session={s5})===")
    show("acc5-1", chat(s5, "帮我建个工单"))
    answer, tools, actions, done = show(
        "acc5-2", chat(s5, "帮我建个工单,功能异常:聊天页发送消息后偶尔没有回复")
    )
    confirm = [a for a in actions if a.get("action") == "confirm_ticket"]
    if not confirm:
        print("[acc5] 未出现工单预览,停止")
        return
    print(f"[acc5] preview={confirm[0].get('preview')}")
    before = ticket_count()
    answer, tools, actions, done = show("acc5-resume", resume(s5, False))
    after = ticket_count()
    audits = db_rows(session_id=s5, tool_name="create_ticket", limit=1)
    print(f"[acc5] tickets {before}->{after}, audit={[(a.status, a.retry_count) for a in audits]}")
    assert after == before, "取消后 tickets 不应新增"
    assert audits and audits[0].status == "permission_denied", "取消审计不是 permission_denied"
    assert "取消" in answer, "取消回复未说明已取消"
    print("\n=== 验收 5 完成 ===")


def phase_mcp_new():
    print("=== 验收 3:MCP 侧新增 poem_first_line,只重启 9101 ===")
    answer, tools, actions, done = show(
        "acc3", chat("acc3", "必须调用 poem_first_line 工具,查一下《静夜思》的第一句")
    )
    assert "poem_first_line" in tools, "Agent 未调用 poem_first_line"
    audits = db_rows(session_id="acc3", tool_name="poem_first_line", limit=1)
    print(f"[acc3] audit={[(a.status, a.source) for a in audits]}")
    assert audits and audits[0].source == "mcp:poetry_archive", "来源不是档案 MCP"
    print("\n=== 验收 3 完成 ===")


def phase_timeout():
    print("=== 验收 6a:只读工具超时重试 ===")
    answer, tools, actions, done = show(
        "acc6", chat("acc6", "必须调用 slow_read_probe 工具,查一下静夜思")
    )
    audits = db_rows(session_id="acc6", tool_name="slow_read_probe", limit=1)
    print(f"[acc6] audit={[(a.status, a.retry_count, a.duration_ms) for a in audits]}")
    assert audits and audits[0].status == "timeout", "slow_read_probe 审计不是 timeout"
    assert audits[0].retry_count >= 1, "只读超时未发生重试"
    print("\n=== 验收 6a 完成;6b 请运行 evals/tool_audit_probe.py ===")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase", choices=["main", "live", "ticket", "cancel", "mcp-new", "timeout"], default="main"
    )
    args = parser.parse_args()
    started = time.time()
    if args.phase == "main":
        phase_main()
    elif args.phase == "live":
        phase_live()
    elif args.phase == "ticket":
        phase_ticket()
    elif args.phase == "cancel":
        phase_cancel()
    elif args.phase == "mcp-new":
        phase_mcp_new()
    else:
        phase_timeout()
    print(f"\n[accept] phase={args.phase} elapsed={int(time.time() - started)}s")


if __name__ == "__main__":
    main()
