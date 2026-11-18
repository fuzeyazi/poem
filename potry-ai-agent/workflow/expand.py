"""Query 扩写 + 多查询检索去重合并(spec §1.2)。

只服务**判定子流程**:把一句问题泛化成多条侧重点不同的检索查询,各查一次 `policy` 源,
按 chunk id 去重后按相似度降序合并。扩写放在**检索侧现查现用**,知识库只留一份。
知识类(FAQ 式)不扩写 —— 由调用方决定是否走本模块。
"""
import json

from embeddings import embed
from prompts import EXPAND_PROMPT
from vector_store import search

_MAX_QUERIES = 5


def parse_queries(text: str) -> list[str]:
    """解析模型输出 `{"queries": [...]}`;失败 → `[]`,由调用方降级为单条原 query。"""
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
        raw = data.get("queries")
    except (ValueError, json.JSONDecodeError, AttributeError):
        return []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        text_item = str(item or "").strip()
        if text_item and text_item not in out:
            out.append(text_item)
    return out


async def expand_queries(llm, question: str) -> list[str]:
    """扩写成 2–5 条查询;任何失败降级为**单条原 query**(不阻断,spec §10)。"""
    question = (question or "").strip()
    try:
        message = await llm.ainvoke(EXPAND_PROMPT.invoke({"question": question}))
        queries = parse_queries(message.content or "")
    except Exception as exc:  # noqa: BLE001 - 扩写失败不阻断
        print(f"[wf] expand fail, degrade to single query: {str(exc)[:200]}")
        queries = []
    if not queries:
        return [question]
    return queries[:_MAX_QUERIES]


def search_multi(queries: list[str], source_type: str, topk: int) -> list[dict]:
    """对每条查询各查一次该来源,按 chunk id 去重(取最高分)后降序合并。

    `vector_store.search` 单次只吃一个 source_type,故必须多次调用;任何失败都退化为
    少查几条/空结果,不抛异常(spec §10)。
    """
    queries = [q for q in (queries or []) if q and q.strip()]
    if not queries:
        return []
    try:
        vectors = embed(queries)
    except Exception as exc:  # noqa: BLE001 - 嵌入失败整段降级为空
        print(f"[wf] search_multi embed fail: {str(exc)[:200]}")
        return []
    merged: dict[int, dict] = {}
    for vector in vectors:
        try:
            hits = search(vector, topk, source_type)
        except Exception as exc:  # noqa: BLE001 - 单条查询失败不拖垮其余
            print(f"[wf] search_multi fail source_type={source_type}: {str(exc)[:200]}")
            continue
        for hit in hits:
            prev = merged.get(hit["id"])
            if prev is None or hit.get("score", 0.0) > prev.get("score", 0.0):
                merged[hit["id"]] = hit
    return sorted(merged.values(), key=lambda h: h.get("score", 0.0), reverse=True)
