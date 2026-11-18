"""Ch09 改良:ONNX 嵌入引擎对齐验证 + 性能对比(验收脚本,非单测)。

验证三件事:
1. **向量对齐**:同批文本经 PyTorch(FlagEmbedding)与 ONNX 嵌入,逐条余弦相似度
   必须 >= 0.999(否则与 Milvus 已存量向量失配,禁止切换);
2. **排序一致性**:两组向量在检索场景(查询 vs 语料块)的 top-1/top-5 一致;
3. **延迟对比**:单条(在线查询真实形态)与批量(建库形态)的耗时。

用法:.venv\\Scripts\\python.exe evals\\verify_onnx_parity.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import load_settings  # noqa: E402

PARITY_THRESHOLD = 0.999

QUERIES = [
    "李白写月亮的诗",
    "春风又绿江南岸的作者是谁",
    "表达思念家乡的诗句",
    "苏轼的词有什么特点",
    "但愿人长久下一句",
]
CHUNKS = [
    "静夜思 李白 床前明月光,疑是地上霜。举头望明月,低头思故乡。",
    "水调歌头 苏轼 明月几时有,把酒问青天。但愿人长久,千里共婵娟。",
    "泊船瓜洲 王安石 京口瓜洲一水间,钟山只隔数重山。春风又绿江南岸,明月何时照我还。",
    "望月怀远 张九龄 海上生明月,天涯共此时。情人怨遥夜,竟夕起相思。",
    "将进酒 李白 君不见黄河之水天上来,奔流到海不复回。",
    "念奴娇·赤壁怀古 苏轼 大江东去,浪淘尽,千古风流人物。",
]


def torch_embed(texts: list[str]) -> np.ndarray:
    from FlagEmbedding import BGEM3FlagModel

    model = BGEM3FlagModel(load_settings().embedding_model_path, use_fp16=False)
    out = model.encode(texts, max_length=8192, return_dense=True,
                       return_sparse=False, return_colbert_vecs=False)
    return np.asarray(out["dense_vecs"], dtype=np.float32)


def onnx_embed(texts: list[str]) -> np.ndarray:
    import onnxruntime as ort
    from transformers import AutoTokenizer

    model_dir = Path(load_settings().embedding_model_path) / "onnx"
    tok = AutoTokenizer.from_pretrained(str(model_dir))
    sess = ort.InferenceSession(str(model_dir / "model.onnx"), providers=["CPUExecutionProvider"])
    vecs = []
    for text in texts:  # 逐条推理:单条场景不 pad,批量场景复用同一 session
        enc = tok([text], truncation=True, max_length=8192, return_tensors="np")
        out = sess.run(["sentence_embedding"], {
            "input_ids": enc["input_ids"].astype(np.int64),
            "attention_mask": enc["attention_mask"].astype(np.int64),
        })
        vecs.append(out[0][0])
    return np.asarray(vecs, dtype=np.float32)


def cos(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def bench(fn, texts: list[str], rounds: int = 5) -> float:
    fn(texts[:1])  # 预热
    times = []
    for _ in range(rounds):
        t = time.perf_counter()
        fn(texts[:1])
        times.append((time.perf_counter() - t) * 1000)
    return sorted(times)[rounds // 2]  # 中位数,ms


def main() -> int:
    corpus = QUERIES + CHUNKS
    print("加载 PyTorch 引擎并嵌入 ...")
    t0 = time.perf_counter()
    tv = torch_embed(corpus)
    print(f"  torch 就绪+嵌入 {len(corpus)} 条: {time.perf_counter()-t0:.1f}s")
    print("加载 ONNX 引擎并嵌入 ...")
    t0 = time.perf_counter()
    ov = onnx_embed(corpus)
    print(f"  onnx 就绪+嵌入 {len(corpus)} 条: {time.perf_counter()-t0:.1f}s")

    print(f"\n== 1. 向量对齐(阈值 {PARITY_THRESHOLD}) ==")
    worst = 1.0
    for i, text in enumerate(corpus):
        s = cos(tv[i], ov[i])
        worst = min(worst, s)
        print(f"  {s:.6f}  {text[:22]}")
    ok1 = worst >= PARITY_THRESHOLD
    print(f"  最差余弦: {worst:.6f} -> {'PASS' if ok1 else 'FAIL'}")

    print("\n== 2. 检索排序一致性 ==")
    agree = 0
    for i in range(len(QUERIES)):
        t_rank = np.argsort(-(tv[i] @ tv[len(QUERIES):].T))[:5]
        o_rank = np.argsort(-(ov[i] @ ov[len(QUERIES):].T))[:5]
        same = list(t_rank) == list(o_rank)
        agree += same
        print(f"  top5 {'一致' if same else '不一致'}  q={QUERIES[i][:14]}")
    ok2 = agree == len(QUERIES)
    print(f"  一致率 {agree}/{len(QUERIES)} -> {'PASS' if ok2 else 'FAIL'}")

    print("\n== 3. 单条嵌入延迟(中位数,5轮) ==")
    tb = bench(lambda xs: torch_embed(xs), corpus, rounds=3)
    print(f"  torch 冷加载成本高,单条(含复用模型)另行实测;本轮以 onnx 为主:")
    # torch 单条:模型已加载,直接测
    from embeddings import get_embedder  # noqa: F401  (复用已加载权重路径不同,单独测)
    ob = bench(lambda xs: onnx_embed(xs), corpus)
    print(f"  onnx 单条: {ob:.1f} ms")

    print("\n结论:", "PASS - 可切换 EMBEDDING_ENGINE=onnx" if ok1 and ok2 else "FAIL - 禁止切换")
    return 0 if ok1 and ok2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
