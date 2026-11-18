"""审核后台 API:待审列表 / 详情 / 通过写库 / 驳回。"""
import json

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from embeddings import embed as default_embed
from vector_store import get_store as default_store


class ApproveRequest(BaseModel):
    standard_question: str | None = None
    approved_answer: str


def _snapshot(raw: str | None) -> list:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def create_review_router(storage, *, embed_fn=None, store_factory=None) -> APIRouter:
    router = APIRouter()
    from auth import resolve_admin  # 管理鉴权(未配置密钥时开放)
    embed_fn = embed_fn or default_embed
    store_factory = store_factory or default_store

    @router.get("/api/admin/review")
    def list_reviews(request: Request, status: str = "pending", limit: int = 50, offset: int = 0):
        resolve_admin(request)
        items = storage.list_reviews(status=status or None, limit=limit, offset=offset)
        return {"items": items}

    @router.get("/api/admin/review/{review_id}")
    def get_review(request: Request, review_id: int):
        resolve_admin(request)
        review = storage.get_review(review_id)
        if review is None:
            raise HTTPException(status_code=404, detail={"message": "审核项不存在"})
        pending = storage.list_pending_by_review(review_id)
        for row in pending:
            row["snapshot"] = _snapshot(row.get("retrieved_snapshot"))
        return {**review, "pending": pending}

    @router.post("/api/admin/review/{review_id}/approve")
    def approve(request: Request, review_id: int, body: ApproveRequest):
        resolve_admin(request)
        review = storage.get_review(review_id)
        if review is None:
            raise HTTPException(status_code=404, detail={"message": "审核项不存在"})
        if review["status"] != "pending":
            raise HTTPException(status_code=409, detail={"message": "该审核项已处理"})
        answer = (body.approved_answer or "").strip()
        if not answer:
            raise HTTPException(status_code=400, detail={"message": "核准答案不能为空"})
        standard = (body.standard_question or review["standard_question"]).strip()
        if not standard:
            raise HTTPException(status_code=400, detail={"message": "标准问题不能为空"})
        text = f"Q: {standard}\nA: {answer}"
        try:
            storage.upsert_chunks([{
                "source_type": "qa", "source_id": review_id, "section": "faq", "seq": 0,
                "chunk_text": text, "raw_text": text, "title": standard,
            }])
            chunk_id = storage.get_chunk_id("qa", review_id, "faq", 0)
            if chunk_id is None:
                raise RuntimeError("知识块写入后未取到 id")
            vector = embed_fn([text])[0]
            store_factory().upsert(
                [chunk_id], [vector],
                [{"source_type": "qa", "title": standard, "writer": "", "dynasty": ""}],
            )
            storage.mark_embedded([chunk_id])
        except Exception as exc:  # noqa: BLE001 - 向量写入失败保持 pending,可重试
            print(f"[review] approve fail id={review_id}: {str(exc)[:200]}")
            raise HTTPException(
                status_code=503,
                detail={"message": f"知识库写入失败,请稍后重试: {str(exc)[:120]}"},
            )
        storage.update_review_status(
            review_id, "approved", approved_answer=answer, standard_question=standard,
        )
        return {"ok": True, "chunkId": chunk_id, "review": storage.get_review(review_id)}

    @router.post("/api/admin/review/{review_id}/reject")
    def reject(request: Request, review_id: int):
        resolve_admin(request)
        review = storage.get_review(review_id)
        if review is None:
            raise HTTPException(status_code=404, detail={"message": "审核项不存在"})
        if review["status"] != "pending":
            raise HTTPException(status_code=409, detail={"message": "该审核项已处理"})
        storage.update_review_status(review_id, "rejected")
        return {"ok": True, "review": storage.get_review(review_id)}

    return router
