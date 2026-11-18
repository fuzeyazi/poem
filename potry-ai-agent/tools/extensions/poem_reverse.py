"""即插即用验收插件:把文字倒序返回。新增文件后不重启 API 即可被 Agent 使用。"""
from langchain_core.tools import tool


@tool
def poem_reverse(text: str) -> dict:
    """把一段文字倒序返回(验收即插即用插件)。

    Args:
        text: 要倒序的文字
    """
    return {"ok": True, "found": True, "reversed": text[::-1]}


def register(catalog) -> None:
    catalog.register_builtin(poem_reverse)
