import pytest

from embeddings import EMBED_DIM, embed, get_embedder, set_embedder


class FakeEmbedder:
    def embed(self, texts):
        # 首维用文本长度编码,其余补零凑够 EMBED_DIM(与真实维度契约一致)
        return [[float(len(t))] + [0.0] * (EMBED_DIM - 1) for t in texts]


def test_get_embedder_uses_injected_instance():
    fake = FakeEmbedder()
    set_embedder(fake)
    try:
        assert get_embedder() is fake
        assert embed(["abc"])[0][0] == 3.0  # Fake 用文本长度编码
    finally:
        set_embedder(None)


def test_set_embedder_none_resets_singleton():
    set_embedder(FakeEmbedder())
    set_embedder(None)
    # 复位后单例为空;此处不触发真模型加载,只断言"可复位"这一契约
    import embeddings

    assert embeddings._embedder is None


def test_embed_returns_empty_for_empty_input():
    set_embedder(FakeEmbedder())
    try:
        assert embed([]) == []
    finally:
        set_embedder(None)


def test_bgem3_embed_short_circuits_empty_without_model():
    from embeddings import BGEM3Embedder

    e = BGEM3Embedder.__new__(BGEM3Embedder)  # 不跑 __init__,故无 _model
    assert e.embed([]) == []


def test_embed_rejects_wrong_dimension():
    class BadEmbedder:
        def embed(self, texts):
            return [[0.0, 1.0] for _ in texts]  # 2 维,与 EMBED_DIM 不符

    set_embedder(BadEmbedder())
    try:
        with pytest.raises(ValueError, match="EMBED_DIM"):
            embed(["x"])
    finally:
        set_embedder(None)


def test_engine_factory_selects_by_config(monkeypatch):
    """EMBEDDING_ENGINE=onnx → Onnx 引擎;其余值(含拼错)回退 torch 引擎。"""
    import embeddings

    calls = []

    class FakeTorch:
        def __init__(self, path):
            calls.append("torch")

    class FakeOnnx:
        def __init__(self, path):
            calls.append("onnx")

    monkeypatch.setattr(embeddings, "BGEM3Embedder", FakeTorch)
    monkeypatch.setattr(embeddings, "OnnxBGEM3Embedder", FakeOnnx)
    try:
        for engine, expect in (("onnx", "onnx"), ("torch", "torch"), ("typo", "torch")):
            monkeypatch.setenv("EMBEDDING_ENGINE", engine)
            embeddings.set_embedder(None)
            embeddings.get_embedder()
            assert calls[-1] == expect, f"engine={engine} 应选 {expect}"
    finally:
        embeddings.set_embedder(None)
