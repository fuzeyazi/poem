from context_layers import downgrade_anchor, split_layers, truncate_layer2, turn_groups


ROWS = [
    {"id": 1, "role": "user", "content": "问一"},
    {"id": 2, "role": "assistant", "content": "答一"},
    {"id": 3, "role": "user", "content": "问二"},
    {"id": 4, "role": "assistant", "content": "答二"},
    {"id": 5, "role": "user", "content": "问三"},
    {"id": 6, "role": "assistant", "content": "答三"},
]


def test_split_layers_respects_both_anchors():
    layers = split_layers(ROWS, summary_upto_msg_id=2, layer1_from_msg_id=4)
    assert [r["id"] for r in layers.layer2] == [3, 4]
    assert [r["id"] for r in layers.layer1] == [5, 6]


def test_split_layers_all_in_layer1_when_anchors_zero():
    layers = split_layers(ROWS, 0, 0)
    assert layers.layer2 == []
    assert [r["id"] for r in layers.layer1] == [1, 2, 3, 4, 5, 6]


def test_truncate_keeps_user_verbatim_and_cuts_assistant_and_blob():
    rows = [
        {"id": 1, "role": "user", "content": "用" * 500},
        {"id": 2, "role": "assistant", "content": "答" * 41},
        {"id": 3, "role": "assistant", "content": "答" * 500},
    ]
    out = truncate_layer2(rows, prefix_chars=40, blob_chars=400)
    assert out[0]["content"] == "用" * 500
    assert out[1]["content"] == "答" * 40 + "…"
    assert out[2]["content"] == "[工具结果:500字]"


def test_turn_groups_split_on_user_boundary():
    groups = turn_groups(ROWS)
    assert [[r["id"] for r in g] for g in groups] == [[1, 2], [3, 4], [5, 6]]


def test_downgrade_returns_none_when_within_budget():
    assert downgrade_anchor(ROWS, budget_tokens=10_000) is None


def test_downgrade_moves_complete_turns_until_under_budget():
    # 共 36 token(每轮 2 条 × 6);25 token 只装得下两轮 → 搬走最早一轮,锚点=2
    assert downgrade_anchor(ROWS, budget_tokens=25) == 2
