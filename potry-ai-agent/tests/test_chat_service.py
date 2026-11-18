import asyncio

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from chat_service import ChatService
from config import Settings
from memory import SessionStore


class FakeLLM:
    """可脚本化两阶段:tool_calls(非流式 ainvoke)与流式回答(astream)。"""

    def __init__(self, pieces, tool_call=None, final_pieces=None):
        self.pieces = pieces  # 无工具路径:流式片段;有工具路径:第一次流式(不用)
        self.tool_call = tool_call  # {"name":..., "args":..., "id":...} 或 None
        self.final_pieces = final_pieces if final_pieces is not None else pieces
        self.prompts = []

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, prompt):
        self.prompts.append(prompt)
        if self.tool_call:
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": self.tool_call["name"],
                    "args": self.tool_call["args"],
                    "id": self.tool_call["id"],
                    "type": "tool_call",
                }],
            )
        return AIMessage(content="".join(self.final_pieces))

    async def astream(self, prompt):
        self.prompts.append(prompt)
        for p in self.final_pieces:
            yield AIMessageChunk(p)


def make_settings():
    return Settings(
        llm_base_url="http://fake",
        llm_api_key="sk-fake",
        llm_model="fake",
        history_max_tokens=2000,
        llm_temperature=0.7,
        mysql_url="sqlite:///:memory:",
        embedding_model_path="fake-model-path",
    )


def _assert_tool_pairing_valid(messages):
    """历史合法性:每个 tool_call id 必有配对 ToolMessage,且无孤儿 ToolMessage(裸 tool_calls AI 禁止)。"""
    ai_ids = [tc["id"] for m in messages if isinstance(m, AIMessage) and m.tool_calls for tc in m.tool_calls]
    tool_ids = [m.tool_call_id for m in messages if isinstance(m, ToolMessage)]
    assert sorted(ai_ids) == sorted(tool_ids)


@pytest.mark.asyncio
async def test_stream_reply_yields_pieces_and_stores_history():
    store = SessionStore()
    service = ChatService(make_settings(), store, llm=FakeLLM(["你", "好", "呀"]))
    pieces = [p async for p in service.stream_reply("s1", "你好")]
    assert pieces == ["你", "好", "呀"]
    hist = store.get_history("s1")
    assert [m.content for m in hist] == ["你好", "你好呀"]


@pytest.mark.asyncio
async def test_history_persisted_when_consumer_closes_early():
    store = SessionStore()
    service = ChatService(make_settings(), store, llm=FakeLLM(["a", "b", "c"]))
    gen = service.stream_reply("s1", "你好")
    assert await gen.__anext__() == "a"
    await gen.aclose()  # 模拟客户端中途断开
    hist = store.get_history("s1")
    assert [m.content for m in hist] == ["你好", "a"]  # 已产出的部分也要落历史


@pytest.mark.asyncio
async def test_stream_reply_uses_history():
    store = SessionStore()
    store.append("s1", "我叫小明", "记住你了")
    seen = {}

    class ProbeLLM(FakeLLM):
        async def astream(self, prompt):
            seen["messages"] = prompt.to_messages()
            async for p in super().astream(prompt):
                yield p

    service = ChatService(make_settings(), store, llm=ProbeLLM(["嗯"]))
    _ = [p async for p in service.stream_reply("s1", "我叫什么?")]
    contents = [m.content for m in seen["messages"]]
    assert "我叫小明" in contents and "我叫什么?" in contents


@pytest.mark.asyncio
async def test_tool_call_flow_reinjects_and_converges():
    from langchain_core.tools import tool
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from storage import ChatBase, ChatStorage
    from tools.registry import ToolRegistry

    engine = create_engine("sqlite:///:memory:")
    ChatBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    storage = ChatStorage(factory)
    registry = ToolRegistry(timeout=5.0, max_retries=0)

    @tool
    def query_poem(keyword: str) -> dict:
        """查诗词。

        Args:
            keyword: 关键词
        """
        return {"ok": True, "found": True, "poem": {"title": "静夜思"}}

    registry.register(query_poem)
    llm = FakeLLM(
        [], tool_call={"name": "query_poem", "args": {"keyword": "静夜思"}, "id": "call_1"},
        final_pieces=["是", "李白"],
    )
    service = ChatService(make_settings(), SessionStore(), llm=llm, tool_registry=registry, storage=storage)
    events = [e async for e in service.stream_events("s1", "《静夜思》是谁写的")]

    statuses = [p for e, p in events if e == "tool_status"]
    assert statuses[0]["status"] == "calling"
    assert statuses[-1]["status"] == "done"
    assert statuses[0]["tool"] == "query_poem"
    assert [p["content"] for e, p in events if e == "token"] == ["是", "李白"]
    assert events[-1][0] == "done"

    # 第二次调用收到了 ToolMessage 回灌
    last_prompt = llm.prompts[-1]
    msgs = last_prompt.to_messages()
    assert any(isinstance(m, ToolMessage) for m in msgs)

    # 内存历史:4 条(user / AI(tool_calls) / ToolMessage / 最终 AI)
    hist = service._store.get_history("s1")
    assert len(hist) == 4
    assert isinstance(hist[1], AIMessage) and hist[1].tool_calls
    assert isinstance(hist[2], ToolMessage)

    # 落库:只落 user + 最终 assistant(工具结果不落消息表)
    rows = storage.load_messages(1)
    assert [r["role"] for r in rows] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_second_tool_call_is_not_executed():
    """单轮收敛:收敛段模型再发起 tool_calls,不执行、不循环。"""
    from langchain_core.tools import tool
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from storage import ChatBase, ChatStorage
    from tools.registry import ToolRegistry

    engine = create_engine("sqlite:///:memory:")
    ChatBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    storage = ChatStorage(factory)
    registry = ToolRegistry(timeout=5.0, max_retries=0)
    calls = {"n": 0}

    @tool
    def query_poem(keyword: str) -> dict:
        """查诗词。

        Args:
            keyword: 关键词
        """
        calls["n"] += 1
        return {"ok": True, "found": True}

    registry.register(query_poem)

    class GreedyLLM(FakeLLM):
        async def astream(self, prompt):
            yield AIMessageChunk(content="", tool_calls=[{
                "name": "query_poem", "args": {"keyword": "x"}, "id": "call_2", "type": "tool_call",
            }])
            yield AIMessageChunk("直接说")

    llm = GreedyLLM([], tool_call={"name": "query_poem", "args": {"keyword": "静夜思"}, "id": "call_1"})
    service = ChatService(make_settings(), SessionStore(), llm=llm, tool_registry=registry, storage=storage)
    events = [e async for e in service.stream_events("s1", "hi")]
    assert calls["n"] == 1  # 只执行了第一次
    assert [p["content"] for e, p in events if e == "token"] == ["直接说"]


@pytest.mark.asyncio
async def test_tool_error_still_converges():
    """工具失败:tool_status 尾帧 error,流式收敛与 done 照常,落库两行。"""
    from langchain_core.tools import tool
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from storage import ChatBase, ChatStorage
    from tools.registry import ToolRegistry

    engine = create_engine("sqlite:///:memory:")
    ChatBase.metadata.create_all(engine)
    storage = ChatStorage(sessionmaker(bind=engine))
    registry = ToolRegistry(timeout=5.0, max_retries=0)

    @tool
    def query_poem(keyword: str) -> dict:
        """查诗词。

        Args:
            keyword: 关键词
        """
        raise asyncio.TimeoutError()

    registry.register(query_poem)
    llm = FakeLLM(
        [], tool_call={"name": "query_poem", "args": {"keyword": "静夜思"}, "id": "call_1"},
        final_pieces=["这会儿查不了"],
    )
    service = ChatService(make_settings(), SessionStore(), llm=llm, tool_registry=registry, storage=storage)
    events = [e async for e in service.stream_events("s1", "《静夜思》是谁写的")]

    statuses = [p for e, p in events if e == "tool_status"]
    assert statuses[-1]["status"] == "error"
    assert [p["content"] for e, p in events if e == "token"] == ["这会儿查不了"]
    assert events[-1][0] == "done"
    rows = storage.load_messages(1)
    assert [r["role"] for r in rows] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_cancel_during_tool_execution_keeps_history_legal():
    """断流/取消落在工具执行窗口:内存历史不得出现无 ToolMessage 配对的裸 tool_calls AI。"""
    from langchain_core.tools import tool

    from tools.registry import ToolRegistry

    started = asyncio.Event()
    registry = ToolRegistry(timeout=5.0, max_retries=0)

    @tool
    async def slow_query(keyword: str) -> dict:
        """慢查询(测试专用,永不返回)。

        Args:
            keyword: 关键词
        """
        started.set()
        await asyncio.sleep(3600)
        return {"ok": True, "found": True}

    registry.register(slow_query)
    llm = FakeLLM(
        [], tool_call={"name": "slow_query", "args": {"keyword": "静夜思"}, "id": "call_1"},
        final_pieces=["答"],
    )
    store = SessionStore()
    service = ChatService(make_settings(), store, llm=llm, tool_registry=registry)
    gen = service.stream_events("s1", "hi")

    first = await gen.__anext__()
    assert first[0] == "tool_status" and first[1]["status"] == "calling"

    pending = asyncio.ensure_future(gen.__anext__())  # 推进到 execute 内部
    await asyncio.wait_for(started.wait(), timeout=2)  # 工具确实在执行中
    pending.cancel()  # 模拟取消/断流
    with pytest.raises(asyncio.CancelledError):
        await pending
    await gen.aclose()

    hist = store.get_history("s1")
    _assert_tool_pairing_valid(hist)  # 无裸 tool_calls AI、无孤儿 ToolMessage
    assert len(hist) == 4  # user / AI(tool_calls) / ToolMessage(合成) / AI
    assert isinstance(hist[2], ToolMessage) and "interrupted" in hist[2].content


@pytest.mark.asyncio
async def test_multi_tool_calls_replay_only_executed_call():
    """多 tool_calls 只执行第一个:回灌/落历史的 AI 副本只留已执行 id,与 ToolMessage id 一一对应。"""
    from langchain_core.tools import tool

    from tools.registry import ToolRegistry

    registry = ToolRegistry(timeout=5.0, max_retries=0)
    calls = []

    @tool
    def query_poem(keyword: str) -> dict:
        """查诗词。

        Args:
            keyword: 关键词
        """
        calls.append("query_poem")
        return {"ok": True, "found": True}

    @tool
    def query_poet(name: str) -> dict:
        """查诗人。

        Args:
            name: 诗人名
        """
        calls.append("query_poet")
        return {"ok": True, "found": True}

    registry.register(query_poem)
    registry.register(query_poet)

    class MultiCallLLM(FakeLLM):
        async def ainvoke(self, prompt):
            self.prompts.append(prompt)
            return AIMessage(content="", tool_calls=[
                {"name": "query_poem", "args": {"keyword": "静夜思"}, "id": "call_1", "type": "tool_call"},
                {"name": "query_poet", "args": {"name": "李白"}, "id": "call_2", "type": "tool_call"},
            ])

    llm = MultiCallLLM([], final_pieces=["只答"])
    store = SessionStore()
    service = ChatService(make_settings(), store, llm=llm, tool_registry=registry)
    events = [e async for e in service.stream_events("s1", "hi")]

    assert calls == ["query_poem"]  # 只执行第一个
    # 收敛段 prompt:tool_call id 与 ToolMessage id 一一对应,且只含已执行的 call_1
    msgs = llm.prompts[-1].to_messages()
    ai_ids = [tc["id"] for m in msgs if isinstance(m, AIMessage) and m.tool_calls for tc in m.tool_calls]
    tool_ids = [m.tool_call_id for m in msgs if isinstance(m, ToolMessage)]
    assert ai_ids == ["call_1"]
    assert tool_ids == ["call_1"]
    _assert_tool_pairing_valid(msgs)
    # 内存历史同样合法
    _assert_tool_pairing_valid(store.get_history("s1"))
    assert [p["content"] for e, p in events if e == "token"] == ["只答"]
