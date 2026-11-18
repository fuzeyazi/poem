"""Ch09 检索闸阈值校准(spec §4.2 设计,本脚本补落地)。

在金标集(evals/retrieval_golden.py)上跑真实检索,输出:
1. 每条用例的 top1 / 证据置信度(纯检索,零 LLM 调用);
2. 阈值 0.30–0.95 扫描的 Precision/Recall/F1 表(正例=应过闸,负例=应拦截);
3. F1 最优阈值与正负例分布的可分性诊断(重叠区间)。

用法(需停掉 agent:Milvus Lite 单进程文件锁):
.venv\\Scripts\\python.exe evals\\calibrate_confidence.py [--write]
--write:把最优阈值写入 .env 的 EVIDENCE_CONFIDENCE_THRESHOLD(默认只打印)。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from retrieval_golden import NEGATIVE_CASES, POSITIVE_CASES  # noqa: E402
from config import load_settings  # noqa: E402
from workflow.confidence import evidence_signals, retrieve_evidence  # noqa: E402


def collect() -> list[tuple[str, bool, float, float]]:
    """返回 (问题, 是否应过闸, top1, 证据置信度) 列表。"""
    settings = load_settings()
    rows = []
    for label, cases, should_pass in (("正例", POSITIVE_CASES, True), ("负例", NEGATIVE_CASES, False)):
        print(f"-- {label} {len(cases)} 条 --")
        for q in cases:
            hits, top1 = retrieve_evidence(q, settings)
            sig = evidence_signals(hits, settings.evidence_min_score)
            conf = sig["evidence_confidence"]
            rows.append((q, should_pass, top1, conf))
            print(f"  top1={top1:.4f} conf={conf:.4f}  {q[:30]}")
    return rows


def sweep(rows: list[tuple[str, bool, float, float]]) -> None:
    print("\n== 阈值扫描(正例=应过闸) ==")
    print("阈值   Precision  Recall  F1")
    best = (0.0, 0.0, 0.0, 0.0)  # (f1, thr, p, r)
    thr = 0.30
    while thr <= 0.9501:
        tp = sum(1 for _, sp, _, c in rows if sp and c >= thr)
        fp = sum(1 for _, sp, _, c in rows if not sp and c >= thr)
        fn = sum(1 for _, sp, _, c in rows if sp and c < thr)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        if f1 > best[0]:
            best = (f1, round(thr, 2), p, r)
        if abs(thr * 100 - round(thr * 100)) < 1e-6 and int(round(thr * 100)) % 5 == 0:
            print(f"{thr:.2f}   {p:.3f}      {r:.3f}   {f1:.3f}")
        thr += 0.01
    print(f"\nF1 最优: 阈值={best[1]:.2f}  P={best[2]:.3f} R={best[3]:.3f} F1={best[0]:.3f}")

    pos = sorted(c for _, sp, _, c in rows if sp)
    neg = sorted(c for _, sp, _, c in rows if not sp)
    print(f"正例 conf 区间: [{pos[0]:.4f}, {pos[-1]:.4f}]  负例 conf 区间: [{neg[0]:.4f}, {neg[-1]:.4f}]")
    overlap = pos[0] < neg[-1]
    print("可分性:", "存在重叠区间 [" + f"{pos[0]:.4f},{neg[-1]:.4f}]" + " —— 重叠内阈值按 F1 取舍" if overlap
          else "完全可分,任取 (负例最大, 正例最小) 之间阈值即可")


def main() -> int:
    rows = collect()
    sweep(rows)
    if "--write" in sys.argv:
        f1, thr, _, _ = max(((0, 0, 0, 0),))
        # 重新计算最优(复用 sweep 逻辑)
        best = (0.0, 0.0)
        t = 0.30
        while t <= 0.9501:
            tp = sum(1 for _, sp, _, c in rows if sp and c >= t)
            fp = sum(1 for _, sp, _, c in rows if not sp and c >= t)
            fn = sum(1 for _, sp, _, c in rows if sp and c < t)
            p = tp / (tp + fp) if tp + fp else 0.0
            r = tp / (tp + fn) if tp + fn else 0.0
            f1 = 2 * p * r / (p + r) if p + r else 0.0
            if f1 > best[0]:
                best = (f1, round(t, 2))
            t += 0.01
        env = Path(__file__).parent.parent / ".env"
        text = env.read_text(encoding="utf-8")
        line = f"EVIDENCE_CONFIDENCE_THRESHOLD={best[1]:.2f}"
        if "EVIDENCE_CONFIDENCE_THRESHOLD=" in text:
            import re
            text = re.sub(r"EVIDENCE_CONFIDENCE_THRESHOLD=.*", line, text)
        else:
            text = text.rstrip("\n") + f"\n# Ch09 校准(evals/calibrate_confidence.py F1 最优)\n{line}\n"
        env.write_text(text, encoding="utf-8")
        print(f"已写入 .env: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
