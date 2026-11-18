"""BGE-M3 本地嵌入封装:懒加载单例 + 测试注入钩子。

Ch03 只跑 dense 单路(设计 spec §2),故 encode 时关闭 sparse/colbert 分支。
模型目录来自 EMBEDDING_MODEL_PATH(从 modelscope 下载),BGE-M3 dense 维度 1024。
"""
import threading
from typing import Protocol

from config import load_settings

# 与 Milvus 集合 vector 维度必须一致(见 vector_store.VECTOR_DIM)
EMBED_DIM = 1024
# BGE-M3 上限;显式指定避免默认 512 静默截断(CHUNK_SIZE 可配得更大)
_MAX_TOKENS = 8192


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...  # pragma: no cover


class BGEM3Embedder:
    def __init__(self, model_path: str) -> None:
        # 重依赖与模型加载延迟到首调:import embeddings 时不加载 2GB 模型
        from FlagEmbedding import BGEM3FlagModel

        self._model = BGEM3FlagModel(model_path, use_fp16=False)

    def embed(self, texts: list[str], max_length: int = _MAX_TOKENS) -> list[list[float]]:
        if not texts:
            return []
        out = self._model.encode(
            texts,
            max_length=max_length,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        return [[float(x) for x in vec] for vec in out["dense_vecs"]]


class OnnxBGEM3Embedder:
    """ONNX Runtime 版 dense 嵌入(Ch09 改良)。

    与 PyTorch 版数值对齐(逐条余弦 1.000000,top5 排序一致,
    见 evals/verify_onnx_parity.py),故与 Milvus 存量向量兼容;
    单条嵌入约 51ms vs torch 142ms(常驻会话,2026-10-24 实测)。
    图内已含 CLS pooling + 归一化,直接取 sentence_embedding。
    """

    def __init__(self, model_path: str) -> None:
        import onnxruntime as ort
        from transformers import AutoTokenizer

        onnx_dir = f"{model_path}/onnx"
        self._tok = AutoTokenizer.from_pretrained(onnx_dir)
        self._sess = ort.InferenceSession(
            f"{onnx_dir}/model.onnx", providers=["CPUExecutionProvider"]
        )

    def embed(self, texts: list[str], max_length: int = _MAX_TOKENS) -> list[list[float]]:
        if not texts:
            return []
        import numpy as np

        enc = self._tok(
            list(texts), truncation=True, max_length=max_length,
            padding=True, return_tensors="np",
        )
        vecs = self._sess.run(
            ["sentence_embedding"],
            {
                "input_ids": enc["input_ids"].astype(np.int64),
                "attention_mask": enc["attention_mask"].astype(np.int64),
            },
        )[0]
        return [[float(x) for x in vec] for vec in vecs]


def _build_embedder() -> Embedder:
    settings = load_settings()
    if settings.embedding_engine == "onnx":
        return OnnxBGEM3Embedder(settings.embedding_model_path)
    return BGEM3Embedder(settings.embedding_model_path)


_embedder: Embedder | None = None
_get_lock = threading.Lock()


def get_embedder() -> Embedder:
    """首调加载、后续复用(模型加载失败只在调用时暴露,不阻断服务启动)。

    加锁避免冷启动并发首调重复加载 2.3GB 模型(与 db.py 的 engine 单例不同,此处代价大)。
    """
    global _embedder
    if _embedder is None:
        with _get_lock:
            if _embedder is None:
                _embedder = _build_embedder()
    return _embedder


def set_embedder(embedder: Embedder | None) -> None:
    """测试注入/复位钩子(传 None 复位,下次调用重新懒加载)。

    仅测试注入用;生产代码误传 None 会复位运行中的单例。
    """
    global _embedder
    _embedder = embedder


def embed(texts: list[str]) -> list[list[float]]:
    vectors = get_embedder().embed(texts)
    if vectors and any(len(vec) != EMBED_DIM for vec in vectors):
        got = next(len(vec) for vec in vectors if len(vec) != EMBED_DIM)
        raise ValueError(
            f"嵌入维度 {got} 与 EMBED_DIM({EMBED_DIM}) 不一致,请检查 EMBEDDING_MODEL_PATH 指向的模型"
        )
    return vectors
