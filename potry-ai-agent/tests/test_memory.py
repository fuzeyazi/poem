from langchain_core.messages import AIMessage, HumanMessage

from memory import (
    SESSION_MAX_MESSAGES,
    SESSION_MAX_SESSIONS,
    SessionStore,
    trim_history,
)


def test_trim_history_keeps_latest_human_and_cuts_old():
    msgs = []
    for i in range(20):
        msgs.append(HumanMessage(f"第{i}个问题,内容足够长以便超过token预算" * 5))
        msgs.append(AIMessage(f"第{i}个回答,内容足够长以便超过token预算" * 5))
    msgs.append(HumanMessage("最新问题"))
    trimmed = trim_history(msgs, max_tokens=100)
    assert trimmed[-1].content == "最新问题"
    assert trimmed[0].type == "human"
    assert len(trimmed) < len(msgs)


def test_trim_history_short_list_untouched():
    msgs = [HumanMessage("你好"), AIMessage("你好呀")]
    trimmed = trim_history(msgs, max_tokens=2000)
    assert [m.content for m in trimmed] == ["你好", "你好呀"]


def test_trim_history_oversized_latest_message_never_empty():
    msgs = [HumanMessage("新" * 20000)]
    trimmed = trim_history(msgs, max_tokens=100)
    assert trimmed == msgs  # 最新消息必须保留,不得静默丢弃


def test_session_store_roundtrip():
    store = SessionStore()
    store.append("s1", "你好", "你好呀")
    hist = store.get_history("s1")
    assert [(m.type, m.content) for m in hist] == [("human", "你好"), ("ai", "你好呀")]
    assert store.get_history("no-such") == []


def test_session_store_caps_message_count():
    store = SessionStore()
    for i in range(SESSION_MAX_MESSAGES // 2 + 10):
        store.append("s1", f"q{i}", f"a{i}")
    hist = store.get_history("s1")
    assert len(hist) <= SESSION_MAX_MESSAGES
    assert hist[-1].content == f"a{SESSION_MAX_MESSAGES // 2 + 9}"  # 保留最新的


def test_session_store_evicts_oldest_session_at_cap():
    store = SessionStore()
    for i in range(SESSION_MAX_SESSIONS + 5):
        store.append(f"s{i}", "q", "a")
    assert len(store._sessions) <= SESSION_MAX_SESSIONS
    assert store.get_history("s0") == []  # 最老的会话被逐出
    assert store.get_history(f"s{SESSION_MAX_SESSIONS + 4}") != []  # 最新的保留
