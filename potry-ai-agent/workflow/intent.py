"""八类意图定义 + **硬编码**分流映射(八类 → 六出口)。

分流规则不交给模型决策:意图识别节点只负责产出标签 + 置信度,出口由本模块常量表决定(spec §3)。

相对 Ch04 的归并(用户拍板):`reference_lookup`(典故/出处)并入 `poem_explain`;
`find_dynasty`(查朝代)并入 `find_poem`。两个工具仍保留,Agent 仍可自主调用。
"""
import json

# 六个出口
ROUTE_KNOWLEDGE = "knowledge"
ROUTE_BUSINESS = "business"
ROUTE_RULING = "ruling"          # 判定子流程(格律/体裁合规 + 诗作校勘核对)
ROUTE_COMPLAINT = "complaint"
ROUTE_CHITCHAT = "chitchat"
ROUTE_OTHER = "other"
ROUTES = (ROUTE_KNOWLEDGE, ROUTE_BUSINESS, ROUTE_RULING, ROUTE_COMPLAINT, ROUTE_CHITCHAT, ROUTE_OTHER)

# 八类意图标签(七类业务 + other 兜底)
INTENT_POEM_EXPLAIN = "poem_explain"
INTENT_FIND_POEM = "find_poem"
INTENT_FIND_POET = "find_poet"
INTENT_POEM_METER = "poem_meter"
INTENT_POEM_VERIFY = "poem_verify"
INTENT_COMPLAINT = "complaint"
INTENT_CHITCHAT = "chitchat"
INTENT_OTHER = "other"

INTENT_LABELS = (
    INTENT_POEM_EXPLAIN, INTENT_FIND_POEM, INTENT_FIND_POET,
    INTENT_POEM_METER, INTENT_POEM_VERIFY, INTENT_COMPLAINT, INTENT_CHITCHAT, INTENT_OTHER,
)

# 八类 → 六出口(硬编码,不得改为模型决策)
INTENT_TO_ROUTE = {
    INTENT_POEM_EXPLAIN: ROUTE_KNOWLEDGE,
    INTENT_FIND_POEM: ROUTE_BUSINESS,
    INTENT_FIND_POET: ROUTE_BUSINESS,
    INTENT_POEM_METER: ROUTE_RULING,
    INTENT_POEM_VERIFY: ROUTE_RULING,
    INTENT_COMPLAINT: ROUTE_COMPLAINT,
    INTENT_CHITCHAT: ROUTE_CHITCHAT,
    INTENT_OTHER: ROUTE_OTHER,
}

# 拿不准就归 other(spec §3.2:别硬塞进业务意图);解析失败/模型异常同样落这里
DEFAULT_INTENT = INTENT_OTHER


def parse_intent_response(text: str) -> tuple[str, float]:
    """从模型输出取出 `(intent, confidence)`。

    模型可能包 ```json 围栏或加解释文字,故按首 `{` / 末 `}` 截取再解析。
    解析失败、标签非法、置信度缺失/非数值 → 归 `other`,置信度 0.0(spec §3.2/§10:
    不抛异常、不阻断);置信度钳到 [0, 1]。
    """
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
        label = str(data.get("intent", "")).strip()
    except (ValueError, json.JSONDecodeError, AttributeError):
        return DEFAULT_INTENT, 0.0
    if label not in INTENT_LABELS:
        return DEFAULT_INTENT, 0.0
    raw = data.get("confidence", 0.0)
    try:
        confidence = min(1.0, max(0.0, float(raw)))
    except (TypeError, ValueError):
        confidence = 0.0
    return label, confidence
