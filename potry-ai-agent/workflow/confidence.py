"""置信度闸:知识类检索与"证据是否够进 Agent"的判定。

仅作用于知识类意图**检索完成后、进 Agent 之前**(spec §7):
- 检索范围 = 全库,`poem` / `poet` / `qa` 三类各取 top-k 后合并降序(最简实现;
  `vector_store.search` 单次只吃一个 source_type,故需三次调用);
- 阈值**复用 Ch03 已有配置** `settings.similarity_threshold`,不新增环境变量;
- 检索失败(模型/向量库不可用)一律视为**证据不足**(spec §10)。
"""
from config import Settings

SOURCE_TYPES = ("poem", "poet", "qa")


def retrieve_evidence(question: str, settings: Settings) -> tuple[list[dict], float]:
    """返回 `(合并降序后的命中列表, top1 相似度)`;任何失败都退化为 `([], 0.0)`。"""
    try:
        from embeddings import embed
        from vector_store import search

        vector = embed([question])[0]
        hits: list[dict] = []
        for source_type in SOURCE_TYPES:
            try:
                hits.extend(search(vector, settings.milvus_topk, source_type))
            except Exception as exc:  # noqa: BLE001 - 单类失败不拖垮其余两类
                print(f"[wf] retrieve fail source_type={source_type}: {str(exc)[:200]}")
        hits.sort(key=lambda h: h.get("score", 0.0), reverse=True)
        return hits, (hits[0]["score"] if hits else 0.0)
    except Exception as exc:  # noqa: BLE001 - 嵌入失败整段降级为证据不足
        print(f"[wf] retrieve fail: {str(exc)[:200]}")
        return [], 0.0


def is_evidence_sufficient(score: float, threshold: float) -> bool:
    """`evidence_score >= 阈值` 即判定证据充足(spec §7)。"""
    return score >= threshold


_MARGIN_SCALE = 0.20
_COUNT_TARGET = 3


def evidence_signals(hits: list[dict], min_score: float) -> dict:
    """用现有稠密检索分做证据置信度代理（无 reranker）。"""
    scores = sorted(
        (max(0.0, min(1.0, float(h.get("score", 0.0)))) for h in hits),
        reverse=True,
    )
    top1 = scores[0] if scores else 0.0
    top2 = scores[1] if len(scores) > 1 else 0.0
    margin = max(0.0, top1 - top2) if len(scores) > 1 else 0.0
    effective_count = sum(1 for s in scores if s >= min_score)
    confidence = (
        0.5 * top1
        + 0.3 * min(margin / _MARGIN_SCALE, 1.0)
        + 0.2 * min(effective_count / _COUNT_TARGET, 1.0)
    )
    return {
        "top1": round(top1, 4), "top2": round(top2, 4),
        "margin": round(margin, 4), "effective_count": effective_count,
        "evidence_confidence": round(confidence, 4),
    }


def is_confidence_sufficient(confidence: float, threshold: float) -> bool:
    return confidence >= threshold
