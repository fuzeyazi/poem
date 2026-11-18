from langchain_core.messages import HumanMessage

from prompts import CHAT_PROMPT, SYSTEM_PROMPT_TEMPLATE


def test_system_template_has_role_and_constraints():
    text = SYSTEM_PROMPT_TEMPLATE.format()
    assert "诗人" in text
    assert "约束" in text


def test_system_prompt_has_tool_guidance():
    text = SYSTEM_PROMPT_TEMPLATE.format()
    assert "查数据" in text  # 工具使用指引已追加
    assert "青莲" in text  # 人设不变


def test_chat_prompt_renders_system_plus_messages():
    result = CHAT_PROMPT.invoke({"messages": [HumanMessage("春眠不觉晓")]})
    msgs = result.to_messages()
    assert msgs[0].type == "system"
    assert msgs[1].content == "春眠不觉晓"


def test_system_prompt_has_ticket_guidance():
    text = SYSTEM_PROMPT_TEMPLATE.format()
    assert "create_ticket" in text
    assert "追问" in text
    assert "不要替用户核实事实" in text


def test_intent_prompt_has_ticket_routing_few_shot():
    from prompts import INTENT_PROMPT
    text = INTENT_PROMPT.invoke({"question": "x"}).to_messages()[0].content
    assert "帮我建个工单" in text
    assert "不是 complaint" in text
