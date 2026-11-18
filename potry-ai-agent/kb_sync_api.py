"""知识库在线增量同步(2026-10-25): MySQL(potry) ↔ Milvus 向量库一致性闭环。

此前唯一的同步手段是停服跑 build_kb.py 全量重建——导入诗词后 RAG 检索永远搜不到新数据。

一致性三层设计:
1. **导入即同步**: 后端管理端 add 诗词成功后自动 POST /api/admin/kb/sync
   (失败不阻塞导入,仅告警,由对账兜底);
2. **对账可见**: GET /api/admin/kb/syncstats 实时对比 potry 覆盖数 vs
   chunks(去重source_id)/pending/embedded,差异水位一眼可见;
3. **全量兜底**: 停服跑 build_kb.py(幂等,中断可重跑)。

同步动作(POST /api/admin/kb/sync)后台线程执行,三步幂等可重入:
  a. 清孤儿: chunks 中 source_id 已不在 potry 的(源库删除后残留) → Milvus delete + chunks 删除;
  b. 切分入库: 全量扫 potry 幂等 upsert(只为新诗/变更诗产生 pending 块);
  c. 嵌入: pending 块分批嵌入写 Milvus(复用进程内全局连接,绕开 Milvus Lite 进程锁),
     失败保持 pending 可重跑。
首次实测发现存量不一致: 830 首已删诗词的孤儿向量 + 11607 块从未嵌入的 pending。
"""
from __future__ import annotations

import threading
import time

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from auth import resolve_admin
from build_kb import collect_poem_chunks, embed_pending
from config import load_settings
from db import Potry, new_session
from knowledge import KnowledgeChunk, KnowledgeStorage
from vector_store import get_store

_sync_lock = threading.Lock()
_sync_state: dict = {"running": False, "last_result": None, "started_at": None, "finished_at": None}


def _sync_single_poem(storage: KnowledgeStorage, title: str) -> dict:
    """指定诗优先同步(秒级): 导入即同步链路用;存量债由无参全量sync慢慢还。"""
    settings = load_settings()
    t0 = time.time()
    session = new_session(settings.mysql_url)
    try:
        poem = session.execute(select(Potry).where(Potry.title == title)).scalar_one_or_none()
        if poem is None:
            return {"error": f"poem not found: {title}"}
        rows = [
            {"source_type": "poem", "source_id": poem.id, "title": poem.title,
             "writer": poem.writer, "dynasty": poem.dynasty, **c}
            for c in _chunk_one(poem, settings)
        ]
        pending_ids = list(session.execute(
            select(KnowledgeChunk.id).where(
                KnowledgeChunk.source_type == "poem",
                KnowledgeChunk.source_id == poem.id,
                KnowledgeChunk.status == "pending",
            )
        ).scalars())
    finally:
        session.close()
    written = storage.upsert_chunks(rows)
    # 刚upsert的新块: 重新查pending(含upsert后新增的)
    session = new_session(settings.mysql_url)
    try:
        pending_ids = list(session.execute(
            select(KnowledgeChunk.id).where(
                KnowledgeChunk.source_type == "poem",
                KnowledgeChunk.source_id == poem.id,
                KnowledgeChunk.status == "pending",
            )
        ).scalars())
    finally:
        session.close()
    embedded = 0
    store = get_store()
    from build_kb import _EMBED_BATCH
    from embeddings import embed
    for i in range(0, len(pending_ids), _EMBED_BATCH):
        batch_ids = pending_ids[i:i + _EMBED_BATCH]
        chunks = [storage.get_chunk(cid) for cid in batch_ids]
        vectors = embed([c["chunk_text"] for c in chunks])
        store.upsert(batch_ids, vectors, [
            {"source_type": c["source_type"], "title": c["title"],
             "writer": c["writer"], "dynasty": c["dynasty"]} for c in chunks
        ])
        storage.mark_embedded(batch_ids)
        embedded += len(batch_ids)
    return {"title": title, "chunks_written": written, "embedded": embedded,
            "elapsed_ms": int((time.time() - t0) * 1000)}


def _chunk_one(poem, settings) -> list[dict]:
    from chunking import chunk_poem
    data = {
        "title": poem.title, "dynasty": poem.dynasty, "writer": poem.writer, "type": poem.type,
        "content": poem.content, "translation": poem.translation, "shangxi": poem.shangxi,
        "remark": poem.remark,
    }
    return chunk_poem(data, settings.chunk_size, settings.chunk_overlap)


def _do_sync(storage: KnowledgeStorage) -> dict:
    settings = load_settings()
    t0 = time.time()
    # a. 清孤儿: 源库已删的诗词残留向量(检索会命中已删诗,必须双向一致)
    session = new_session(settings.mysql_url)
    try:
        orphan_ids = [
            row for row in session.execute(
                select(KnowledgeChunk.id).where(
                    KnowledgeChunk.source_type == "poem",
                    KnowledgeChunk.source_id.not_in(select(Potry.id)),
                )
            ).scalars()
        ]
    finally:
        session.close()
    orphan_vectors_deleted = 0
    if orphan_ids:
        get_store().delete(orphan_ids)
        orphan_vectors_deleted = storage.delete_chunks(orphan_ids)
    # b. 切分入库(幂等: 只为新诗/变更诗产生pending)
    session = new_session(settings.mysql_url)
    try:
        rows = collect_poem_chunks(session, settings.chunk_size, settings.chunk_overlap, None)
    finally:
        session.close()
    written = storage.upsert_chunks(rows)
    # c. 嵌入 pending(可能上万块,分钟级;失败保持pending可重跑)
    stats = embed_pending(storage, get_store(), source_type="poem")
    return {
        "orphan_chunks_deleted": orphan_vectors_deleted,
        "chunks_written": written,
        **stats,
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


def create_kb_sync_router(storage: KnowledgeStorage) -> APIRouter:
    router = APIRouter()

    @router.get("/api/admin/kb/syncstats")
    def syncstats(request: Request):
        """对账: potry 总数 vs 知识库覆盖/pending/embedded —— 差异即不一致水位。"""
        resolve_admin(request)
        settings = load_settings()
        session = new_session(settings.mysql_url)
        try:
            potry_count = session.scalar(select(func.count()).select_from(Potry)) or 0
            covered = session.scalar(
                select(func.count(func.distinct(KnowledgeChunk.source_id))).where(
                    KnowledgeChunk.source_type == "poem"
                )
            ) or 0
        finally:
            session.close()
        status = storage.count_by_status(source_type="poem")
        result = {
            "potry_total": potry_count,
            "poem_covered": covered,
            "uncovered": max(0, potry_count - covered),
            "chunks_pending": status.get("pending", 0),
            "chunks_embedded": status.get("embedded", 0),
            "consistent": potry_count == covered and status.get("pending", 0) == 0,
            "sync_running": _sync_state["running"],
            "last_sync": _sync_state["last_result"],
        }
        return result

    @router.post("/api/admin/kb/sync")
    def sync(request: Request, title: str | None = None):
        """增量同步: 带 title=秒级同步指定诗(导入即同步链路); 无参=后台全量(还存量债)。"""
        resolve_admin(request)
        if title:
            return _sync_single_poem(storage, title)
        if not _sync_lock.acquire(blocking=False):
            return {"accepted": False, "reason": "同步已在进行中", "state": _sync_state["last_result"]}

        def runner():
            _sync_state["running"] = True
            _sync_state["started_at"] = time.strftime("%H:%M:%S")
            try:
                _sync_state["last_result"] = _do_sync(storage)
            except Exception as exc:  # noqa: BLE001 - 状态可见,可重跑
                _sync_state["last_result"] = {"error": str(exc)[:300]}
            finally:
                _sync_state["running"] = False
                _sync_state["finished_at"] = time.strftime("%H:%M:%S")
                _sync_lock.release()

        threading.Thread(target=runner, daemon=True, name="kb-sync").start()
        return {"accepted": True, "hint": "后台执行中,GET /api/admin/kb/syncstats 查看进度"}

    return router
