import pytest

from vector_store import (
    MilvusLiteVectorStore,
    safe_expr_value,
    search,
    set_store,
    upsert,
)


@pytest.fixture
def store(tmp_path):
    # 直接持有实例即可;不再无意义地复位单例(单例路径测试自行 try/finally 复位)
    return MilvusLiteVectorStore(str(tmp_path / "kb.db"), "knowledge", dim=4)


def _meta(source_type="poem", title="静夜思", writer="李白", dynasty="唐"):
    return {"source_type": source_type, "title": title, "writer": writer, "dynasty": dynasty}


def test_upsert_and_search_returns_similarity(store):
    store.upsert([1, 2], [[1.0, 0, 0, 0], [0, 1.0, 0, 0]], [_meta(title="静夜思"), _meta(title="春晓")])
    hits = store.search([1.0, 0, 0, 0], topk=2, source_type="poem")
    assert hits[0]["id"] == 1
    assert hits[0]["title"] == "静夜思"
    assert hits[0]["score"] > hits[1]["score"]


def test_upsert_is_idempotent_by_primary_key(store):
    store.upsert([1], [[1.0, 0, 0, 0]], [_meta(title="静夜思")])
    store.upsert([1], [[1.0, 0, 0, 0]], [_meta(title="静夜思(改)")])
    hits = store.search([1.0, 0, 0, 0], topk=5, source_type="poem")
    assert len(hits) == 1
    assert hits[0]["title"] == "静夜思(改)"


def test_search_filters_by_source_type(store):
    store.upsert(
        [1, 2],
        [[1.0, 0, 0, 0], [0.9, 0.1, 0, 0]],
        [_meta(source_type="poem"), _meta(source_type="poet", title="李白")],
    )
    hits = store.search([1.0, 0, 0, 0], topk=5, source_type="poet")
    assert [h["title"] for h in hits] == ["李白"]


def test_query_by_dynasty_filters(store):
    store.upsert(
        [1, 2],
        [[1.0, 0, 0, 0], [0, 1.0, 0, 0]],
        [_meta(dynasty="唐"), _meta(dynasty="宋", title="春晓")],
    )
    rows = store.query_by_dynasty("唐", limit=10)
    assert [r["title"] for r in rows] == ["静夜思"]


def test_data_survives_new_client_on_same_file(tmp_path):
    path = str(tmp_path / "kb.db")
    first = MilvusLiteVectorStore(path, "knowledge", dim=4)
    first.upsert([1], [[1.0, 0, 0, 0]], [_meta()])
    second = MilvusLiteVectorStore(path, "knowledge", dim=4)  # 新 client 必须能读(load_collection)
    assert second.search([1.0, 0, 0, 0], topk=1, source_type="poem")[0]["id"] == 1


# ---------- safe_expr_value:过滤表达式注入清洗(安全逻辑回归保护) ----------


def test_safe_expr_value_keeps_cjk():
    assert safe_expr_value("唐") == "唐"
    assert safe_expr_value("李白") == "李白"


def test_safe_expr_value_strips_injection_chars():
    # 引号/反斜杠/换行/分号/括号/比较符一律剔除,无法构造表达式逃逸
    assert safe_expr_value('a"b\\c\nd;e(f)') == "abcdef"
    assert '"' not in safe_expr_value('唐" or id >= 0 or "x')


def test_safe_expr_value_truncates():
    assert len(safe_expr_value("x" * 40)) == 32


# ---------- 模块级函数经单例路径 ----------


def test_module_level_search_goes_through_singleton(store):
    set_store(store)
    try:
        upsert([1], [[1.0, 0, 0, 0]], [_meta()])
        assert search([1.0, 0, 0, 0], topk=1, source_type="poem")[0]["id"] == 1
    finally:
        set_store(None)


# ---------- upsert 入参校验 ----------


def test_upsert_rejects_length_mismatch(store):
    with pytest.raises(ValueError, match="长度不一致"):
        store.upsert([1, 2, 3], [[1.0, 0, 0, 0]], [_meta()])


def test_upsert_accepts_empty_input(store):
    # 空入参不应抛异常(与长度校验共存:三者等长为 0)
    store.upsert([], [], [])


# ---------- 父目录自动创建 ----------


def test_creates_missing_parent_directory(tmp_path):
    """Milvus Lite 要求父目录存在;构造时应自动创建,否则建库/首问直接失败。"""
    nested = tmp_path / "milvus_data" / "knowledge.db"
    assert not nested.parent.exists()
    s = MilvusLiteVectorStore(str(nested), "knowledge", dim=4)
    assert nested.parent.exists()
    s.upsert([1], [[1.0, 0, 0, 0]], [_meta()])
    assert s.search([1.0, 0, 0, 0], topk=1, source_type="poem")[0]["id"] == 1
