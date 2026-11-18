"""诗词档案 MCP Server(9101):独立进程 + mock 数据,不接 MySQL、不建表。

启动:
    .\\.venv\\Scripts\\python.exe mcp_servers\\poetry_archive_server.py
"""
import random

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "poetry-archive", host="127.0.0.1", port=9101,
    stateless_http=True, json_response=True,
)

POEMS = {
    "静夜思": {
        "title": "静夜思", "writer": "李白", "dynasty": "唐",
        "content": "床前明月光,疑是地上霜。举头望明月,低头思故乡。",
        "translation": "明亮的月光洒在床前,好像地上泛起了一层白霜;抬头望月,低头思乡。",
    },
    "春望": {
        "title": "春望", "writer": "杜甫", "dynasty": "唐",
        "content": "国破山河在,城春草木深。感时花溅泪,恨别鸟惊心。",
        "translation": "国都沦陷而山河依旧,春日的长安城草木丛生;感伤时局,见花落泪。",
    },
    "登鹳雀楼": {
        "title": "登鹳雀楼", "writer": "王之涣", "dynasty": "唐",
        "content": "白日依山尽,黄河入海流。欲穷千里目,更上一层楼。",
        "translation": "夕阳依山而落,黄河奔流入海;想看得更远,就要再登高一层。",
    },
    "江雪": {
        "title": "江雪", "writer": "柳宗元", "dynasty": "唐",
        "content": "千山鸟飞绝,万径人踪灭。孤舟蓑笠翁,独钓寒江雪。",
        "translation": "群山不见飞鸟,万径没有人迹;孤舟上一位蓑笠老翁,独钓寒江雪。",
    },
    "山居秋暝": {
        "title": "山居秋暝", "writer": "王维", "dynasty": "唐",
        "content": "空山新雨后,天气晚来秋。明月松间照,清泉石上流。",
        "translation": "空山新雨过后,傍晚秋意渐浓;明月照松林,清泉流石上。",
    },
}

POETS = {
    "李白": {"name": "李白", "dynasty": "唐", "courtesy": "太白", "intro": "唐代浪漫主义诗人,号青莲居士。"},
    "杜甫": {"name": "杜甫", "dynasty": "唐", "courtesy": "子美", "intro": "唐代现实主义诗人,被尊为诗圣。"},
    "王维": {"name": "王维", "dynasty": "唐", "courtesy": "摩诘", "intro": "唐代山水田园诗人,诗中有画。"},
    "柳宗元": {"name": "柳宗元", "dynasty": "唐", "courtesy": "子厚", "intro": "唐代文学家,唐宋八大家之一。"},
    "王之涣": {"name": "王之涣", "dynasty": "唐", "courtesy": "季凌", "intro": "唐代边塞诗人,存诗不多而名篇极盛。"},
}


@mcp.tool()
def poem_archive_lookup(title: str = "", poet: str = "") -> dict:
    """查询诗词档案:按诗题或诗人匹配,返回原文、译文与档案状态。"""
    matched = [
        p for p in POEMS.values()
        if (title and title in p["title"]) or (poet and poet in p["writer"])
    ]
    item = dict(random.choice(matched or list(POEMS.values())))
    item["archive_status"] = random.choice(["在库", "整理中"])
    return {"ok": True, "found": True, "archive": item}


@mcp.tool()
def poet_archive_lookup(name: str) -> dict:
    """查询诗人档案:按姓名匹配,返回朝代、字号与简介。"""
    item = POETS.get(name) or random.choice(list(POETS.values()))
    return {"ok": True, "found": True, "poet": dict(item)}


@mcp.tool()
def poem_line_count(title: str) -> dict:
    """统计指定诗题在档案中的诗句数量(按逗号/句号切分)。"""
    poem = POEMS.get(title)
    if poem is None:
        return {"ok": True, "found": False, "message": "档案中没有这首诗"}
    import re
    lines = [x for x in re.split(r"[。;,]", poem["content"]) if x.strip()]
    return {"ok": True, "found": True, "title": title, "lines": len(lines)}


@mcp.tool()
def poem_first_line(title: str) -> dict:
    """返回指定诗题在档案中的首句。"""
    poem = POEMS.get(title)
    if poem is None:
        return {"ok": True, "found": False, "message": "档案中没有这首诗"}
    first = poem["content"].split("。")[0]
    return {"ok": True, "found": True, "title": title, "line": first}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
