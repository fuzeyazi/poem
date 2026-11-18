"""进程内会话历史:按 sessionId 存储,请求时按 token 预算裁剪。"""
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.messages.utils import count_tokens_approximately, trim_messages

SESSION_MAX_MESSAGES = 50  # 每会话存储上限,超出丢最旧
SESSION_MAX_SESSIONS = 200  # 会话数上限,超出按 FIFO 逐出最老会话(防无鉴权撑爆内存)


class SessionStore:
    """内存 dict 会话存储,服务重启即丢(第一章最简版,接受)。"""

    def __init__(self) -> None:
        self._sessions: dict[str, list[BaseMessage]] = {}

    def get_history(self, session_id: str) -> list[BaseMessage]:
        return list(self._sessions.get(session_id, []))

    def append(self, session_id: str, user_message: str, assistant_message: str) -> None:
        hist = self._sessions.setdefault(session_id, [])
        if len(self._sessions) > SESSION_MAX_SESSIONS:
            # dict 保序:插入序最老的先出;仅在新会话加入致超限时触发
            self._sessions.pop(next(iter(self._sessions)))
        hist.append(HumanMessage(user_message))
        hist.append(AIMessage(assistant_message))
        if len(hist) > SESSION_MAX_MESSAGES:
            del hist[: len(hist) - SESSION_MAX_MESSAGES]

    def append_messages(self, session_id: str, messages: list[BaseMessage]) -> None:
        """原样追加一组消息(工具轮需保留 AIMessage.tool_calls / ToolMessage 回灌结构)。"""
        hist = self._sessions.setdefault(session_id, [])
        if len(self._sessions) > SESSION_MAX_SESSIONS:
            # dict 保序:插入序最老的先出;仅在新会话加入致超限时触发
            self._sessions.pop(next(iter(self._sessions)))
        hist.extend(messages)
        if len(hist) > SESSION_MAX_MESSAGES:
            del hist[: len(hist) - SESSION_MAX_MESSAGES]


def trim_history(messages: list[BaseMessage], max_tokens: int) -> list[BaseMessage]:
    """按 token 预算保留最近的消息,裁剪边界落在 human 消息上,最新消息必保留。

    未超预算时原样返回;超预算裁剪后若为空(最新单条即超预算),
    兜底保留最新一条,保证用户消息不被静默丢弃。
    """
    if count_tokens_approximately(messages) <= max_tokens:
        return list(messages)
    trimmed = trim_messages(
        messages,
        strategy="last",
        token_counter="approximate",
        max_tokens=max_tokens,
        start_on="human",
        end_on="human",
    )
    return trimmed or list(messages[-1:])
