"""诗词域业务工具:查诗词 / 诗人 / 朝代。

Ch03:查诗词(query_poem)、查诗人(query_poet)内部实现从关键词查表改为向量语义检索
(问题向量化 → Milvus Top-K → 回查 MySQL 权威原文);查朝代(query_dynasty_poems)
走**结构化过滤**(按 dynasty 精确匹配块,非语义检索)。三者**签名与返回结构保持
Ch02 契约不变**;工具描述文案同步改为新口径(它只是给模型看的说明,不改变契约)。
"""
from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from config import load_settings
from db import Potry, Writer, get_engine, new_session
from embeddings import embed
from knowledge import KnowledgeStorage
from vector_store import query_by_dynasty, search

_MAX_CONTENT = 300  # 诗文/译文回灌截断,防上下文爆炸
_MAX_TITLES = 20  # 朝代标题列表上限
_DYNASTY_SCAN = _MAX_TITLES * 5  # 初始扫描块数(同一首诗会切成多块,故按块扫再按 title 去重)
_DYNASTY_SCAN_MAX = _MAX_TITLES * 100  # 翻倍扫描的上限,防无界放大


def _get_session() -> Session:
    return new_session(load_settings().mysql_url)


def _get_storage() -> KnowledgeStorage:
    return KnowledgeStorage(sessionmaker(bind=get_engine(load_settings().mysql_url)))


def _truncate(text: str | None) -> str | None:
    return text[:_MAX_CONTENT] if text else text


def _fetch_poem_by_id(session: Session, poem_id: int) -> dict | None:
    p = session.execute(select(Potry).where(Potry.id == poem_id)).scalars().first()
    if p is None:
        return None
    return {
        "title": p.title,
        "dynasty": p.dynasty,
        "writer": p.writer,
        "type": p.type,
        "content": _truncate(p.content),
        "translation": _truncate(p.translation),
        "shangxi": _truncate(p.shangxi),
        "remark": _truncate(p.remark),
    }


def _fetch_poet_by_id(session: Session, writer_id: int) -> dict | None:
    w = session.execute(select(Writer).where(Writer.id == writer_id)).scalars().first()
    if w is None:
        return None
    return {
        "name": w.name,
        "simpleIntro": _truncate(w.simpleIntro),
        "detailIntro": _truncate(w.detailIntro),
        "headImageUrl": w.headImageUrl,
    }


def _fetch_works(session: Session, name: str) -> list[str]:
    stmt = select(Potry.title).where(Potry.writer == name).limit(5)
    return [t for t in session.execute(stmt).scalars() if t]


def _top_hit(query: str, source_type: str) -> dict | None:
    """向量检索取最高相似度命中;低于阈值或空结果返回 None。

    依赖 vector_store.search 返回已按相似度降序排列(hits[0] 即最高分)。
    """
    settings = load_settings()
    vector = embed([query])[0]
    hits = search(vector, settings.milvus_topk, source_type)
    if not hits or hits[0]["score"] < settings.similarity_threshold:
        return None
    return hits[0]


def _collect_dynasty_titles(dynasty: str) -> list[str]:
    """按朝代取标题:块数不足则翻倍重扫,直到凑满 _MAX_TITLES 或触上限。

    query_by_dynasty 返回的是**块**且无排序/无 DISTINCT,同一首诗(尤其长诗拆
    原文/译文/赏析/注释)会占多块;固定 scan 可能前若干块集中在少数几首上,
    去重后远不足 _MAX_TITLES,故按需放大扫描量。
    """
    scan = _DYNASTY_SCAN
    titles: list[str] = []
    while True:
        hits = query_by_dynasty(dynasty, scan)
        seen: set[str] = set()
        titles = []
        for h in hits:
            t = h.get("title")
            if t and t not in seen:
                seen.add(t)
                titles.append(t)
            if len(titles) >= _MAX_TITLES:
                break
        # 凑满 20 或"没取满本次请求的块数"(说明已耗尽)或触上限即停
        if len(titles) >= _MAX_TITLES or len(hits) < scan or scan >= _DYNASTY_SCAN_MAX:
            return titles
        scan = min(scan * 2, _DYNASTY_SCAN_MAX)


@tool
def query_poem(keyword: str) -> dict:
    """语义检索诗词:按问题的意思找最匹配的一首诗词(含朝代、作者、原文、译文)。

    Args:
        keyword: 用自然语言描述想找的诗词(如「那首讲月亮的叫啥」「李白写思乡的诗」);
            直接给诗名(如「静夜思」)也可以。
    """
    try:
        hit = _top_hit(keyword, "poem")
        if hit is None:
            return {"ok": True, "found": False}
        chunk = _get_storage().get_chunk(hit["id"])
        if chunk is None:
            return {"ok": True, "found": False}
        with _get_session() as session:
            poem = _fetch_poem_by_id(session, chunk["source_id"])
    except Exception as exc:  # noqa: BLE001 - 统一走契约里的失败分支,不抛
        return {"ok": False, "error": str(exc)[:200]}
    if poem is None:
        return {"ok": True, "found": False}
    return {"ok": True, "found": True, "poem": poem}


@tool
def query_poet(name: str) -> dict:
    """查诗人:生平简介与代表作标题列表。

    Args:
        name: 诗人姓名或自然语言描述,如「李白」「杜甫」「写诗很豪放的那位」
    """
    try:
        hit = _top_hit(name, "poet")
        if hit is None:
            return {"ok": True, "found": False}
        chunk = _get_storage().get_chunk(hit["id"])
        if chunk is None:
            return {"ok": True, "found": False}
        with _get_session() as session:
            poet = _fetch_poet_by_id(session, chunk["source_id"])
            works = _fetch_works(session, poet["name"]) if poet else []
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200]}
    if poet is None:
        return {"ok": True, "found": False}
    return {"ok": True, "found": True, "poet": poet, "works": works}


@tool
def query_dynasty_poems(dynasty: str) -> dict:
    """按朝代查诗词:返回该朝代的诗词标题列表(最多 20 条)。

    Args:
        dynasty: 朝代名,如「唐」「宋」
    """
    try:
        titles = _collect_dynasty_titles(dynasty)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200]}
    if not titles:
        return {"ok": True, "found": False}
    return {"ok": True, "found": True, "count": len(titles), "titles": titles}
