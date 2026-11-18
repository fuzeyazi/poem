"""token 估算口径与从窗口倒推的预算(spec §6)。"""
import math

from config import Settings
from context_budget import (
    Budget,
    derive_budget,
    estimate_message_tokens,
    estimate_tokens,
    self_check_lines,
)


def make_settings(**over):
    base = dict(
        llm_base_url="http://fake", llm_api_key="sk-fake", llm_model="fake",
        history_max_tokens=2000, llm_temperature=0.7,
        mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
    )
    base.update(over)
    return Settings(**base)


def demo_settings():
    return make_settings(
        model_context_window=18000, max_output_tokens=2000,
        max_user_input_tokens=2000, max_agent_steps=3,
        tool_result_max_tokens=1200, rerank_top_k=5,
    )


def test_estimate_tokens_mixes_cjk_and_ascii():
    assert estimate_tokens("床前明月光") == 3          # ceil(5*0.6)
    assert estimate_tokens("abc") == 1                # ceil(3/4)
    assert estimate_tokens("诗abc") == math.ceil(0.6 + 0.75)
    assert estimate_tokens("") == 0
    assert estimate_message_tokens("床前明月光") == 7  # 3 + 4 开销


def test_demo_config_matches_acceptance_numbers():
    b = derive_budget(demo_settings())
    assert (b.history, b.layer1, b.layer2) == (5650, 3954, 1695)
    assert b.layer1 + b.layer2 + 1 == b.history
    assert b.ok is True


def test_default_config_keeps_twenty_turns_uncompressed():
    b = derive_budget(make_settings())
    assert (b.history, b.layer1, b.layer2) == (16000, 11199, 4800)
    assert b.layer1 >= 20 * 400


def test_zero_window_reports_budget_insufficient():
    b = derive_budget(make_settings(model_context_window=1000))
    assert b.ok is False and b.history == 0 and b.layer1 == 0
    lines = self_check_lines(b, turn_steady=400)
    assert any("上下文预算不足" in line for line in lines)


def test_layer1_smaller_than_one_turn_warns():
    b = Budget(window=18000, output=2000, user_input=2000, agent_peak=3600,
               fixed=4750, window_side=5650, history=5650, layer1=3954, layer2=1695, ok=True)
    assert self_check_lines(b, turn_steady=5000) == [
        "[ctx] 预算告警:layer1=3954 装不下完整一轮(约 5000 token)"
    ]
