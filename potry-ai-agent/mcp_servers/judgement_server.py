"""判定与纠错 MCP Server(9102):独立进程 + mock 数据,不落库。

启动:
    .\\.venv\\Scripts\\python.exe mcp_servers\\judgement_server.py
"""
import random

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "judgement", host="127.0.0.1", port=9102,
    stateless_http=True, json_response=True,
)

_CONCLUSIONS = {
    ("meter", "pass"): "句式与平仄合规,符合近体诗要求。",
    ("meter", "fail"): "句数或平仄不合,建议按近体诗规则调整。",
    ("verify", "pass"): "作者、原文与权威数据一致。",
    ("verify", "fail"): "发现作者或原文与权威数据不一致,需复核。",
}


@mcp.tool()
def judgement_status_lookup(title: str) -> dict:
    """查询某首诗最近一次格律/校勘判定记录(类型、结果、结论、日期)。"""
    kind = random.choice(["meter", "verify"])
    result = random.choice(["pass", "fail"])
    return {
        "ok": True,
        "found": True,
        "judgement": {
            "title": title,
            "kind": kind,
            "result": result,
            "conclusion": _CONCLUSIONS[(kind, result)],
            "date": f"2026-10-{random.randint(10, 22)}",
        },
    }


@mcp.tool()
def correction_progress_lookup(ticket_no: str) -> dict:
    """查询纠错单处理进度(received/reviewing/done)。"""
    status = random.choice(["received", "reviewing", "done"])
    note = {
        "received": "已受理,等待编辑复核。",
        "reviewing": "编辑正在复核原文与译文。",
        "done": "复核完成,已更新词条。",
    }[status]
    return {
        "ok": True,
        "found": True,
        "progress": {
            "ticket_no": ticket_no,
            "status": status,
            "updated_at": f"2026-10-{random.randint(10, 22)}",
            "note": note,
        },
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
