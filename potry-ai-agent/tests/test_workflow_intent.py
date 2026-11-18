"""八类意图 → 六出口硬编码映射的完整性与解析降级(含新置信度字段)。"""
from workflow import intent


def test_mapping_covers_all_eight_intents():
    assert len(intent.INTENT_LABELS) == 8
    assert set(intent.INTENT_TO_ROUTE) == set(intent.INTENT_LABELS)


def test_route_values_are_legal():
    assert set(intent.INTENT_TO_ROUTE.values()) <= set(intent.ROUTES)
    assert set(intent.ROUTES) == {
        intent.ROUTE_KNOWLEDGE, intent.ROUTE_BUSINESS, intent.ROUTE_RULING,
        intent.ROUTE_COMPLAINT, intent.ROUTE_CHITCHAT, intent.ROUTE_OTHER,
    }


def test_mapping_matches_spec():
    assert intent.INTENT_TO_ROUTE["poem_explain"] == intent.ROUTE_KNOWLEDGE
    assert intent.INTENT_TO_ROUTE["find_poem"] == intent.ROUTE_BUSINESS
    assert intent.INTENT_TO_ROUTE["find_poet"] == intent.ROUTE_BUSINESS
    assert intent.INTENT_TO_ROUTE["poem_meter"] == intent.ROUTE_RULING
    assert intent.INTENT_TO_ROUTE["poem_verify"] == intent.ROUTE_RULING
    assert intent.INTENT_TO_ROUTE["complaint"] == intent.ROUTE_COMPLAINT
    assert intent.INTENT_TO_ROUTE["chitchat"] == intent.ROUTE_CHITCHAT
    assert intent.INTENT_TO_ROUTE["other"] == intent.ROUTE_OTHER


def test_merged_labels_are_gone():
    # 归并后这两个标签不再单列(工具与能力保留,只是标签消失)
    assert "reference_lookup" not in intent.INTENT_LABELS
    assert "find_dynasty" not in intent.INTENT_LABELS


def test_parse_intent_response_accepts_plain_json():
    label, conf = intent.parse_intent_response('{"intent": "find_poet", "confidence": 0.9}')
    assert (label, conf) == ("find_poet", 0.9)


def test_parse_intent_response_tolerates_fenced_json():
    assert intent.parse_intent_response(
        '```json\n{"intent": "poem_explain", "confidence": 0.8}\n```'
    )[0] == "poem_explain"


def test_parse_intent_response_defaults_confidence_when_missing():
    assert intent.parse_intent_response('{"intent": "poem_meter"}') == ("poem_meter", 0.0)


def test_parse_intent_response_clamps_out_of_range_confidence():
    assert intent.parse_intent_response('{"intent": "chitchat", "confidence": 7}')[1] == 1.0
    assert intent.parse_intent_response('{"intent": "chitchat", "confidence": -3}')[1] == 0.0
    assert intent.parse_intent_response('{"intent": "chitchat", "confidence": "高"}')[1] == 0.0


def test_parse_intent_response_degrades_to_other():
    assert intent.parse_intent_response("今天天气不错") == (intent.DEFAULT_INTENT, 0.0)
    assert intent.parse_intent_response('{"intent": "no_such_label"}') == (intent.DEFAULT_INTENT, 0.0)
    assert intent.parse_intent_response('{"nope": 1}') == (intent.DEFAULT_INTENT, 0.0)
    assert intent.DEFAULT_INTENT == intent.INTENT_OTHER == "other"
