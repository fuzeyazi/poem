"""单轮 Function Calling 编排:裁剪 → 非流式取 tool_calls → 执行回灌 → 流式收敛 → 落库。"""
import time
from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI

from config import Settings
from memory import SessionStore, trim_history
from prompts import CHAT_PROMPT
from tools.registry import make_tool_message

StreamEvent = tuple[str, dict]
# ("tool_status", {...}) | ("token", {"content"}) | ("done", {})


def build_llm(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        timeout=60,
    )


class ChatService:
    def __init__(self, settings, store, llm=None, tool_registry=None, storage=None) -> None:
        self._settings = settings
        self._store = store
        self._llm = llm if llm is not None else build_llm(settings)
        self._registry = tool_registry
        self._storage = storage

    async def stream_reply(self, session_id: str, user_message: str) -> AsyncIterator[str]:
        """Ch01 兼容包装:只 yield 回答文本(测试与旧调用方使用)。"""
        gen = self.stream_events(session_id, user_message)
        try:
            async for event, payload in gen:
                if event == "token":
                    yield payload["content"]
        finally:
            # 消费方中途 aclose 时内层生成器不会被同步回收,这里显式关闭,
            # 保证 stream_events 的 finally(落库/落内存历史)立即执行(Ch01 语义)
            await gen.aclose()

    async def stream_events(self, session_id: str, user_message: str) -> AsyncIterator[StreamEvent]:
        history = self._store.get_history(session_id)
        messages: list[BaseMessage] = history + [HumanMessage(user_message)]
        trimmed = trim_history(messages, self._settings.history_max_tokens)

        parts: list[str] = []
        # 工具轮完整消息序列(user / AI(tool_calls) / ToolMessage),finally 里补最终 AI 后写内存历史;
        # 无工具轮保持 Ch01 的 user/AI 两条简记。
        turn_messages: list[BaseMessage] | None = None
        tool_call: dict | None = None  # 已发起的 tool_call,finally 兜底合成 ToolMessage 用
        tool_msg_written = False  # 配对 ToolMessage 是否已落定
        try:
            bound = self._llm.bind_tools(self._registry.get_tools() if self._registry else [])
            first_turn = await bound.ainvoke(CHAT_PROMPT.invoke({"messages": trimmed}))
            tool_call = (first_turn.tool_calls or [None])[0]
            if tool_call is not None:
                # 回灌/落历史的 AI 副本只保留已执行的 tool_call:多 tool_calls 全量回灌
                # 会缺其余 id 的 ToolMessage 配对,真实 API 直接 400
                ai_msg = AIMessage(content=first_turn.content, tool_calls=[tool_call])
                trimmed.append(ai_msg)
                turn_messages = [HumanMessage(user_message), ai_msg]
                # 状态先落定、事件后发:记录就绪(或 finally 兜底覆盖)才发帧;
                # "calling" 在 execute 之前发,客户端实时看到进行中状态
                yield (
                    "tool_status",
                    {"tool": tool_call["name"], "status": "calling", "args": tool_call["args"], "durationMs": 0},
                )
                started = time.monotonic()
                result = await self._registry.execute(tool_call["name"], tool_call["args"])
                duration_ms = int((time.monotonic() - started) * 1000)
                tool_msg = make_tool_message(tool_call["id"], tool_call["name"], result)
                trimmed.append(tool_msg)
                turn_messages.append(tool_msg)
                tool_msg_written = True
                # 尾帧在结果落定后发
                yield (
                    "tool_status",
                    {
                        "tool": tool_call["name"],
                        "status": "done" if result.get("ok") else "error",
                        "args": tool_call["args"],
                        "durationMs": duration_ms,
                    },
                )

            # 第二次调用流式收敛;若模型再发起 tool_calls:不执行不循环(单轮语义),
            # 丢弃 tool_calls 块只取文本。
            async for chunk in self._llm.astream(CHAT_PROMPT.invoke({"messages": trimmed})):
                text = chunk.content
                if isinstance(text, str) and text:
                    parts.append(text)
                    yield ("token", {"content": text})
        finally:
            final_text = "".join(parts)
            if turn_messages is not None and not tool_msg_written:
                synth = make_tool_message(
                    tool_call["id"], tool_call["name"], {"ok": False, "error": "interrupted"}
                )
                turn_messages.append(synth)
            if self._storage is not None:
                try:
                    # Ch06:工具结果不落消息表,只落 user + 最终 assistant
                    self._storage.persist_turn(session_id, user_message, final_text)
                except Exception as exc:  # noqa: BLE001 - 落库失败不打断对话,仅记录
                    print(f"[storage] 落库失败: {str(exc)[:200]}")
            if turn_messages is not None:
                self._store.append_messages(session_id, turn_messages + [AIMessage(final_text)])
            else:
                self._store.append(session_id, user_message, final_text)

        yield ("done", {})
