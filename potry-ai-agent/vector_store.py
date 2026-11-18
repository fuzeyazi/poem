"""Milvus(Milvus Lite 嵌入式)封装:knowledge 集合的建/写/查。

已实测确认(pymilvus 3.0.2):
- 新 client 读前必须 load_collection,否则报 "Collection ... state 'released'";
- COSINE 返回相似度,越大越相似(同向量 = 1.0);
- upsert 按主键幂等(同 id 覆盖)。

运行约束(已实测):
- Milvus Lite 用操作系统级文件锁,**同一 .db 同一时刻只允许一个进程打开**;
  第二个进程(读或写)在 MilvusClient(db_path) 构造期抛 DataDirLockedError
  (pymilvus 包装为 ConnectionConfigException,属 MilvusException 子类)。
- 故:建库 CLI(build_kb)必须独占运行(此时 API 服务不能开着);
  API 侧在线检索与进程内定时 mining 共享同一单例 client(同进程内无冲突)。
- 锁冲突等失败由**工具层**捕获 MilvusException 降级返回 {"ok": false}(Task 8/9 负责),
  本模块自身不加跨进程锁、不吞异常。
"""
import os
import threading
from typing import Protocol

from config import load_settings

VECTOR_DIM = 1024
_METADATA_FIELDS = ("source_type", "title", "writer", "dynasty")
# 字段长度单一来源:schema 建字段与过滤值截断共用,避免魔法数漂移
_FIELD_MAX_LENGTH = {"source_type": 16, "title": 512, "writer": 128, "dynasty": 64}
# 过滤表达式的值只允许字母数字(含 CJK)/下划线/短横/空格;引号、反斜杠、换行等
# 注入字符一律剔除。值来自模型入参,故必须清洗。
_ALLOWED_PUNCT = set(" _-")


def safe_expr_value(value: str, max_len: int = 32) -> str:
    """过滤表达式里的值:只留字母数字(含 CJK)/下划线/短横/空格,并截断,防注入。

    注:实测 dynasty 字段值是中文(如「唐」),仅放行 ASCII 会把值清空导致过滤失效;
    用 str.isalnum() 放行 CJK,同时天然排除引号/反斜杠等注入字符。
    """
    return "".join(ch for ch in str(value) if ch.isalnum() or ch in _ALLOWED_PUNCT)[:max_len]


class VectorStore(Protocol):
    def upsert(self, ids: list[int], vectors: list[list[float]], metadatas: list[dict]) -> None:
        ...  # pragma: no cover

    def delete(self, ids: list[int]) -> None:
        ...  # pragma: no cover

    def search(self, vector: list[float], topk: int, source_type: str) -> list[dict]:
        ...  # pragma: no cover

    def query_by_dynasty(self, dynasty: str, limit: int) -> list[dict]:
        ...  # pragma: no cover


class MilvusLiteVectorStore:
    def __init__(self, db_path: str, collection: str, dim: int = VECTOR_DIM) -> None:
        from pymilvus import DataType, MilvusClient

        # Milvus Lite 要求父目录存在,否则构造期报 "Open local milvus failed, dir ... not exists"
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._client = MilvusClient(db_path)
        self._collection = collection
        if not self._client.has_collection(collection):
            schema = self._client.create_schema(auto_id=False)
            schema.add_field("id", DataType.INT64, is_primary=True)
            schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dim)
            schema.add_field("source_type", DataType.VARCHAR, max_length=_FIELD_MAX_LENGTH["source_type"])
            schema.add_field("title", DataType.VARCHAR, max_length=_FIELD_MAX_LENGTH["title"])
            schema.add_field("writer", DataType.VARCHAR, max_length=_FIELD_MAX_LENGTH["writer"])
            schema.add_field("dynasty", DataType.VARCHAR, max_length=_FIELD_MAX_LENGTH["dynasty"])
            index_params = self._client.prepare_index_params()
            index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
            self._client.create_collection(collection, schema=schema, index_params=index_params)
        self._load()

    def _load(self) -> None:
        # 新 client 时集合可能处于 released,读前必须 load
        self._client.load_collection(self._collection)

    def upsert(self, ids, vectors, metadatas) -> None:
        # zip 会静默截断,长度不一致会让部分行永远进不了 Milvus 却被上游标成"已嵌入",
        # 造成永久、不可自愈的数据不一致,故先显式校验再构造 rows
        if not (len(ids) == len(vectors) == len(metadatas)):
            raise ValueError(
                f"入参长度不一致: ids={len(ids)}, vectors={len(vectors)}, metadatas={len(metadatas)}"
            )
        rows = [
            # Milvus VARCHAR 不接受 None(实测直接写 None 抛 MilvusException),故缺值填空串
            {"id": int(i), "vector": [float(x) for x in v], **{k: (m.get(k) or "") for k in _METADATA_FIELDS}}
            for i, v, m in zip(ids, vectors, metadatas)
        ]
        if not rows:
            return
        self._client.upsert(self._collection, rows)
        # 兜底重新 load:防同进程内集合被再次 released(与构造期 load 语义一致)
        self._load()

    def delete(self, ids) -> None:
        """按主键删除向量(源库删除后的孤儿清理),空列表跳过。"""
        if not ids:
            return
        self._client.delete(collection_name=self._collection, ids=[int(i) for i in ids])

    def search(self, vector, topk, source_type) -> list[dict]:
        res = self._client.search(
            self._collection,
            data=[[float(x) for x in vector]],
            anns_field="vector",
            limit=topk,
            filter=f'source_type == "{safe_expr_value(source_type, _FIELD_MAX_LENGTH["source_type"])}"',
            output_fields=list(_METADATA_FIELDS),
            search_params={"metric_type": "COSINE"},
        )
        hits: list[dict] = []
        for hit in res[0]:
            entity = dict(hit.get("entity") or {})
            hits.append({"id": int(hit["id"]), "score": float(hit["distance"]), **entity})
        return hits

    def query_by_dynasty(self, dynasty, limit) -> list[dict]:
        """按朝代过滤查询块(非向量排序)。

        注意:返回的是**块**,同一首诗可能有多块;`limit` 是**块数**上限。
        调用方若需要"N 首诗",需按每首诗最大块数放大 limit 并自行按 title 去重。
        另注意 limit<=0 会被 Milvus 钳到 1 行,不要用它表示"不限制"。
        """
        expr = (
            f'dynasty == "{safe_expr_value(dynasty, _FIELD_MAX_LENGTH["dynasty"])}"'
            ' and source_type == "poem"'
        )
        rows = self._client.query(
            self._collection, filter=expr, output_fields=list(_METADATA_FIELDS), limit=limit
        )
        return [dict(r) for r in rows]


_store: VectorStore | None = None
_get_lock = threading.Lock()


def get_store() -> VectorStore:
    """首调建 client(并 load 集合),后续复用;失败只在调用时暴露。

    加锁避免并发首调重复建集合(has_collection → create_collection 是复合操作,
    定时 mining 线程与请求线程可能同时进入)。
    """
    global _store
    if _store is None:
        with _get_lock:
            if _store is None:
                settings = load_settings()
                _store = MilvusLiteVectorStore(settings.milvus_db_path, settings.milvus_collection)
    return _store


def set_store(store: VectorStore | None) -> None:
    """测试注入/复位钩子。"""
    global _store
    _store = store


def upsert(ids, vectors, metadatas) -> None:
    get_store().upsert(ids, vectors, metadatas)


def search(vector, topk, source_type) -> list[dict]:
    return get_store().search(vector, topk, source_type)


def query_by_dynasty(dynasty, limit) -> list[dict]:
    return get_store().query_by_dynasty(dynasty, limit)
