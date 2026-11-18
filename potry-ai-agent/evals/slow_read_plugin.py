"""超时验收用插件:访问期间复制到 tools/extensions/ 即可热加载。"""
import asyncio

from langchain_core.tools import tool


@tool
async def slow_read_probe(keyword: str) -> dict:
    """故意很慢的只读工具,用于验证超时重试与错误兜底。

    Args:
        keyword: 查询词
    """
    await asyncio.sleep(3)
    return {"ok": True, "found": True, "keyword": keyword}


def register(catalog) -> None:
    catalog.register_builtin(slow_read_probe, timeout=0.3)
