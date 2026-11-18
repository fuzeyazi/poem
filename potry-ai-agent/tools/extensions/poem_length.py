"""样例只读插件:统计诗文正文字数。新增此文件无需改核心代码即可被 Agent 使用。"""
from langchain_core.tools import tool

_PUNCT = set("，。！？；：、“”‘’《》（）.,!?;:\"'()[]{}—…· \t\n\r")


@tool
def poem_length(text: str) -> dict:
    """统计一段诗文的字数(不计空白与常用标点)。

    Args:
        text: 诗文原文
    """
    count = len([ch for ch in text if ch.strip() and ch not in _PUNCT])
    return {"ok": True, "found": True, "count": count, "text": text}


def register(catalog) -> None:
    catalog.register_builtin(poem_length)
