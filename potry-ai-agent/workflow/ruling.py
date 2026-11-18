"""判定子流程共用逻辑(两条子流程只差 `subflow_kind` 与检索哪类 policy,spec §8)。

职责:
1. 槽位检查:优先用用户点选的 `selected_poem_id`;否则用 LLM 从 query 抽对象;
   抽不到 → 用 query 做一次 poem 源向量检索取候选卡片下发,收尾等回填(两段式第一段);
2. 取对象数据:命中对象后回查 `potry` 表拿权威数据(标题/作者/朝代/体裁/原文/译文);
3. 规则条款检索:对扩写后的多条查询各查一次 `policy` 源,去重合并。
"""
from app_storage import CORRECTION_CATEGORIES
from prompts import SLOT_EXTRACT_PROMPT, SLOT_NO_CANDIDATE_REPLY, SLOT_PROMPT_REPLY
from workflow import expand

_MAX_CANDIDATES = 5
_MAX_CONTENT = 300  # 回灌截断,防上下文爆炸(与 tools/poetry_tools 同一口径)


def fetch_poem(poem_id: int) -> dict | None:
    """取诗作权威数据(potry 表)。**单一入口**,测试可 monkeypatch 本函数。"""
    from sqlalchemy import select

    from config import load_settings
    from db import Potry, new_session

    try:
        with new_session(load_settings().mysql_url) as session:
            row = session.execute(select(Potry).where(Potry.id == poem_id)).scalars().first()
    except Exception as exc:  # noqa: BLE001 - 回查失败按"取不到"处理
        print(f"[wf] fetch_poem fail id={poem_id}: {str(exc)[:200]}")
        return None
    if row is None:
        return None
    content = (row.content or "")[:_MAX_CONTENT]
    translation = (row.translation or "")[:_MAX_CONTENT]
    return {
        "poemId": row.id,
        "title": row.title or "",
        "writer": row.writer or "",
        "dynasty": row.dynasty or "",
        "type": row.type or "",
        "content": content,
        "translation": translation,
    }


def parse_slot_title(text: str) -> str | None:
    """解析 `{"title": "..."}`;null / 空白 / 解析失败 → None(不硬猜,spec §10)。"""
    import json

    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError, AttributeError):
        return None
    title = str(data.get("title") or "").strip()
    return title or None


async def extract_slot_title(llm, question: str) -> str | None:
    """用 LLM 从问题里抽诗作对象;失败一律当"没抽到"。"""
    try:
        message = await llm.ainvoke(SLOT_EXTRACT_PROMPT.invoke({"question": question}))
        return parse_slot_title(message.content or "")
    except Exception as exc:  # noqa: BLE001 - 抽取失败按缺槽位处理
        print(f"[wf] extract slot fail: {str(exc)[:200]}")
        return None


def build_candidates(question: str, deps, limit: int = _MAX_CANDIDATES) -> list[dict]:
    """用 query 做一次 poem 源检索,按**诗作**去重(取该诗最高分块)后取 top-k 作候选卡片。

    hit 的 `id` 是 chunk id;卡片的 `poemId` 取 `chunk.source_id`(= potry.id)。
    """
    hits = expand.search_multi([question], "poem", deps.settings.milvus_topk)
    seen: dict[int, dict] = {}
    for hit in hits:
        chunk = None
        try:
            if deps.knowledge_storage is not None:
                chunk = deps.knowledge_storage.get_chunk(hit["id"])
        except Exception as exc:  # noqa: BLE001 - 回查失败跳过该命中
            print(f"[wf] candidate chunk fail id={hit.get('id')}: {str(exc)[:200]}")
        if not chunk:
            continue
        poem_id = chunk.get("source_id")
        if poem_id is None:
            continue
        candidate = {
            "poemId": int(poem_id),
            "title": hit.get("title") or chunk.get("title") or "",
            "writer": hit.get("writer") or chunk.get("writer") or "",
            "dynasty": hit.get("dynasty") or chunk.get("dynasty") or "",
            "score": round(float(hit.get("score", 0.0)), 4),
        }
        prev = seen.get(poem_id)
        if prev is None or candidate["score"] > prev["score"]:
            seen[poem_id] = candidate
    ordered = sorted(seen.values(), key=lambda c: c["score"], reverse=True)
    return ordered[:limit]


async def resolve_slot(state: dict, deps) -> dict:
    """槽位检查节点:拿到对象 → 继续子流程;拿不到 → 下发候选卡片等回填。"""
    selected = state.get("selected_poem_id")
    if selected:
        target = fetch_poem(int(selected))
        if target:
            return {"slot_target": target, "pending_subflow": False}
    question = state.get("resolved_input", "")
    title = await extract_slot_title(deps.llm, question)
    if title:
        found = build_candidates(title, deps)
        if found:
            target = fetch_poem(found[0]["poemId"])
            if target:
                return {"slot_target": target, "pending_subflow": False}
    candidates = build_candidates(question, deps)
    if not candidates:
        # 连候选都没有:不下发卡片(否则前端无从点选),如实请用户补充线索
        return {"slot_target": None, "pending_subflow": False, "answer": SLOT_NO_CANDIDATE_REPLY}
    return {
        "candidates": candidates, "pending_subflow": True, "slot_target": None,
        "answer": SLOT_PROMPT_REPLY,
    }


def after_slot_check(state: dict) -> str:
    """槽位检查后条件边:拿到对象 → 扩写+检索条款;否则日志收尾(答案已就位)。"""
    return "expand_query" if state.get("slot_target") else "log"


def collect_policy(state: dict, deps) -> dict:
    """对扩写后的多条查询各查一次 `policy` 源,去重合并后作为"规则条款依据"。

    同时把纠错单固定类目写进 state —— 判定子流程**总是**给出纠错单入口(已请示用户获批)。
    """
    queries = state.get("expanded_queries") or [state.get("resolved_input", "")]
    hits = expand.search_multi(queries, "policy", deps.settings.milvus_topk)
    return {"policy_hits": hits, "correction_categories": list(CORRECTION_CATEGORIES)}
