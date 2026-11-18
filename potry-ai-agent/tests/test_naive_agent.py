"""无框架原生 Agent 循环测试:收敛 / 多轮迭代 / 迭代上限。"""
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from naive_agent import run_naive_agent
from tools.registry import ToolRegistry


class ScriptedLLM:
    """按脚本吐 AIMessage;脚本取空后返回固定收敛文本。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        self.calls += 1
        if self.script:
            return self.script.pop(0)
        return AIMessage(content="兜底收敛")


def _registry():
    calls = []

    @tool
    def query_poem(keyword: str) -> dict:
        """查诗词。

        Args:
            keyword: 关键词
        """
        calls.append(keyword)
        return {"ok": True, "found": True, "poem": {"title": "静夜思"}}

    registry = ToolRegistry(timeout=5.0, max_retries=0)
    registry.register(query_poem)
    return registry, calls


@pytest.mark.asyncio
async def test_converges_without_tool_calls():
    llm = ScriptedLLM([AIMessage(content="《静夜思》写的是思乡")])
    registry, calls = _registry()
    result = await run_naive_agent(llm, registry, [HumanMessage(content="hi")])
    assert result["answer"] == "《静夜思》写的是思乡"
    assert result["iterations"] == 1
    assert result["stop_reason"] == "no_tool_calls"
    assert calls == []


@pytest.mark.asyncio
async def test_multi_round_loop_executes_tools_then_converges():
    llm = ScriptedLLM([
        AIMessage(content="", tool_calls=[{"name": "query_poem", "args": {"keyword": "静夜思"}, "id": "c1", "type": "tool_call"}]),
        AIMessage(content="是李白写的"),
    ])
    registry, calls = _registry()
    messages = [HumanMessage(content="《静夜思》是谁写的")]
    result = await run_naive_agent(llm, registry, messages)
    assert calls == ["静夜思"]                      # 工具确实被执行
    assert result["answer"] == "是李白写的"
    assert result["iterations"] == 2                # 多轮迭代 > 1
    assert any(isinstance(m, ToolMessage) for m in messages)  # 结果已回灌


@pytest.mark.asyncio
async def test_stops_at_max_iter_and_forces_answer():
    # 永远要工具的模型:循环必须在 max_iter 处停下,不得无限转
    tool_call = [{"name": "query_poem", "args": {"keyword": "x"}, "id": "c1", "type": "tool_call"}]

    class GreedyLLM(ScriptedLLM):
        async def ainvoke(self, messages):
            self.calls += 1
            return AIMessage(content="", tool_calls=tool_call)

    llm = GreedyLLM([])
    registry, calls = _registry()
    result = await run_naive_agent(llm, registry, [HumanMessage(content="hi")], max_iter=3)
    assert result["iterations"] == 3
    assert result["stop_reason"] == "max_iter"
    assert len(calls) == 2  # 第 3 轮不再执行工具,直接强制收敛
