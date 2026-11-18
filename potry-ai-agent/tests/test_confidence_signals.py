"""证据置信度代理公式:Top1/margin/有效条数。"""
from workflow.confidence import evidence_signals


def test_empty_hits_zero_confidence():
    s = evidence_signals([], min_score=0.3)
    assert s["top1"] == 0.0
    assert s["evidence_confidence"] == 0.0


def test_signals_use_top1_margin_count():
    hits = [{"score": 0.8}, {"score": 0.6}, {"score": 0.5}, {"score": 0.1}]
    s = evidence_signals(hits, min_score=0.3)
    assert s["top1"] == 0.8
    assert s["top2"] == 0.6
    assert s["margin"] == 0.2
    assert s["effective_count"] == 3
    assert 0.7 < s["evidence_confidence"] <= 1.0


def test_single_hit_has_no_margin_but_counts():
    s = evidence_signals([{"score": 0.9}], min_score=0.3)
    assert s["margin"] == 0.0
    assert s["effective_count"] == 1
    assert s["evidence_confidence"] < 0.9
