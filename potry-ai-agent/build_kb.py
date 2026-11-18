r"""离线建库 CLI:potry/writer → 切分 → MySQL(待向量化)→ 嵌入 → Milvus → 回填 + 已向量化。

用法(必须独占运行:Milvus Lite 是进程独占文件锁,建库时 API 服务不能开着):
    .\.venv\Scripts\python.exe build_kb.py                 # 全量
    .\.venv\Scripts\python.exe build_kb.py --limit 50      # 只处理前 50 首诗(小样本验证)
    .\.venv\Scripts\python.exe build_kb.py --skip-chunk    # 只补向量化(不重切)
中断后直接重跑即可:只取 status='pending' 的块补做(设计 spec §6.3)。
"""
import argparse
import os

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from chunking import chunk_poem, chunk_poet, chunk_policy_doc
from config import load_settings
from db import Potry, Writer, get_engine, new_session
from embeddings import embed
from knowledge import KnowledgeBase, KnowledgeStorage
from vector_store import MilvusLiteVectorStore, VectorStore

_EMBED_BATCH = 16
_PROGRESS_EVERY = 50  # 每 N 批打一次进度(全量约 1447 批,CPU 上跑十几分钟)

# 规则语料:文件名 → (source_id, 展示标题)。source_id 是**显式固定**的稳定映射,
# 不用「排序后取下标」——新增文档若排在前面会让既有 id 漂移,导致唯一键错位。
_POLICY_DOCS = (
    ("meter_rules.md", 1, "格律·词牌规则"),
    ("collation_rules.md", 2, "校勘准则"),
)
_DEFAULT_POLICY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policy_docs")


def collect_poem_chunks(session, chunk_size: int, overlap: int, limit: int | None = None) -> list[dict]:
    stmt = select(Potry).order_by(Potry.id)
    if limit is not None:
        stmt = stmt.limit(limit)
    out: list[dict] = []
    for p in session.execute(stmt).scalars():
        poem = {
            "title": p.title, "dynasty": p.dynasty, "writer": p.writer, "type": p.type,
            "content": p.content, "translation": p.translation, "shangxi": p.shangxi, "remark": p.remark,
        }
        for c in chunk_poem(poem, chunk_size, overlap):
            out.append(
                {"source_type": "poem", "source_id": p.id,
                 "title": p.title, "writer": p.writer, "dynasty": p.dynasty, **c}
            )
    return out


def collect_poet_chunks(session, chunk_size: int, overlap: int) -> list[dict]:
    out: list[dict] = []
    for w in session.execute(select(Writer).order_by(Writer.id)).scalars():
        for c in chunk_poet(
            {"name": w.name, "simpleIntro": w.simpleIntro, "detailIntro": w.detailIntro}, chunk_size, overlap
        ):
            out.append(
                {"source_type": "poet", "source_id": w.id, "title": w.name, "writer": w.name, "dynasty": None, **c}
            )
    return out


def collect_policy_chunks(policy_dir: str, chunk_size: int, overlap: int) -> list[dict]:
    """读规则文档 → 切块。文档不可读则跳过并告警(不阻断其余文档)。"""
    out: list[dict] = []
    for filename, source_id, title in _POLICY_DOCS:
        path = os.path.join(policy_dir, filename)
        try:
            with open(path, encoding="utf-8") as handle:
                markdown = handle.read()
        except OSError as exc:  # noqa: BLE001 - 缺文档只告警,不算失败
            print(f"[kb] 规则文档不可读,跳过 {filename}: {str(exc)[:200]}")
            continue
        for c in chunk_policy_doc({"title": title, "markdown": markdown}, chunk_size, overlap):
            out.append(
                {"source_type": "policy", "source_id": source_id,
                 "title": title, "writer": None, "dynasty": None, **c}
            )
    return out


def embed_pending(
    storage: KnowledgeStorage, store: VectorStore, batch_size: int = _EMBED_BATCH,
    source_type: str | None = None,
) -> dict:
    """把 status='pending' 的块分批嵌入并写入 Milvus,成功则转 embedded。

    `source_type` 非空时只处理该类(如只补 `policy`),避免把 1.1 万条 pending 诗词
    一并嵌入。整批嵌入/写入失败时**不标记**,块保持 pending —— 这就是"挂了能重跑"。
    配置类错误(ValueError,如维度/长度校验不通过)不吞:直接上抛。
    """
    embedded = failed = batches = 0
    total = storage.count_by_status(source_type=source_type).get("pending", 0)
    print(f"[kb] 待向量化 {total} 块(source_type={source_type or '全部'}),批大小 {batch_size}")
    while True:
        pending = storage.list_pending(limit=batch_size, source_type=source_type)
        if not pending:
            break
        ids = [c["id"] for c in pending]
        try:
            vectors = embed([c["chunk_text"] for c in pending])
            store.upsert(
                ids,
                vectors,
                [
                    {"source_type": c["source_type"], "title": c["title"],
                     "writer": c["writer"], "dynasty": c["dynasty"]}
                    for c in pending
                ],
            )
        except ValueError:
            raise  # 配置类错误(维度/长度校验)不降级,直接暴露
        except Exception as exc:  # noqa: BLE001 - 记录并停止本轮,块保持 pending 供重跑
            print(f"[kb] 批次失败(保持 pending,可重跑): {str(exc)[:200]}")
            failed += len(ids)
            break
        storage.mark_embedded(ids)
        embedded += len(ids)
        batches += 1
        if batches % _PROGRESS_EVERY == 0:
            print(f"[kb] 已嵌入 {embedded}/{total},failed={failed}")
    return {"embedded": embedded, "failed": failed, "remaining": storage.count_by_status(source_type=source_type).get("pending", 0)}


def run(
    limit: int | None = None, skip_chunk: bool = False,
    only: str | None = None, policy_dir: str | None = None,
) -> dict:
    """`only` ∈ {None, "poem", "poet", "policy"}:None = poem + poet(Ch03 语义,不动);
    显式给 "policy" 才纳入规则语料,并只嵌该来源的 pending。"""
    settings = load_settings()
    engine = get_engine(settings.mysql_url)
    KnowledgeBase.metadata.create_all(engine)
    storage = KnowledgeStorage(sessionmaker(bind=engine))
    store = MilvusLiteVectorStore(settings.milvus_db_path, settings.milvus_collection)

    written = 0
    if not skip_chunk:
        rows: list[dict] = []
        if only in (None, "poem", "poet"):
            session = new_session(settings.mysql_url)
            try:
                if only in (None, "poem"):
                    rows += collect_poem_chunks(session, settings.chunk_size, settings.chunk_overlap, limit)
                if only in (None, "poet"):
                    rows += collect_poet_chunks(session, settings.chunk_size, settings.chunk_overlap)
            finally:
                session.close()
        if only == "policy":
            rows += collect_policy_chunks(policy_dir or _DEFAULT_POLICY_DIR, settings.chunk_size, settings.chunk_overlap)
        written = storage.upsert_chunks(rows)
    stats = embed_pending(storage, store, source_type=only)
    return {"chunks_written": written, **stats, "status_counts": storage.count_by_status()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ch03 离线建库")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 首诗(小样本验证用)")
    parser.add_argument("--skip-chunk", action="store_true", help="跳过切分入库,只补向量化")
    parser.add_argument("--only", choices=("poem", "poet", "policy"), default=None,
                        help="只处理某类来源(如 --only policy 只切/只嵌规则语料)")
    parser.add_argument("--policy-dir", default=None, help="规则文档目录(默认 potry-ai-agent/policy_docs)")
    args = parser.parse_args()
    try:
        print(f"[kb] 结果: {run(limit=args.limit, skip_chunk=args.skip_chunk, only=args.only, policy_dir=args.policy_dir)}")
    except Exception as exc:  # noqa: BLE001 - CLI 顶层兜底,打印后以非零码退出
        print(f"[kb] 启动/执行失败: {str(exc)[:200]}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
