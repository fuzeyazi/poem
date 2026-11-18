"""指代消解 + Query 改写:透传 / 改写 / 失败降级 / 历史为空走捷径。"""
import pytest
from langchain_core.messages import AIMessage

from workflow.resolve import format_history, parse_resolve_result, resolve_input


class ScriptedLLM:
    def __init__(self, reply="", boom=False):
        self.reply = reply
        self.boom = boom
        self.calls = 0

    async def ainvoke(self, messages):
        self.calls += 1
        if self.boom:
            raise ConnectionError("upstream down")
        return AIMessage(content=self.reply)


def test_parse_resolve_result_accepts_plain_json():
    assert parse_resolve_result('{"query": "这句合不合律", "changed": true}') == ("这句合不合律", True)


def test_parse_resolve_result_tolerates_fenced_json():
    assert parse_resolve_result('```json\n{"query": "x", "changed": false}\n```') == ("x", False)


def test_parse_resolve_result_degrades_on_garbage():
    assert parse_resolve_result("我觉得不用改写") == ("", False)
    assert parse_resolve_result('{"query": ""}') == ("", False)


def test_format_history_renders_roles():
    text = format_history([{"role": "user", "content": "《静夜思》是谁写的"}, {"role": "assistant", "content": "李白"}])
    assert "用户:" in text and "青莲:" in text and "静夜思" in text


def test_format_history_empty():
    assert format_history([]) == "(无)"


def test_format_history_renders_summary_line():
    text = format_history([{"role": "summary", "content": "问过《静夜思》"}])
    assert text == "【早期梗概】问过《静夜思》"


@pytest.mark.asyncio
async def test_resolve_passes_through_when_no_history():
    llm = ScriptedLLM(reply='{"query": "不该被用到", "changed": true}')
    assert await resolve_input(llm, "《静夜思》表达了什么感情", []) == ("《静夜思》表达了什么感情", False)
    assert llm.calls == 0          # 无历史时不调模型(已完整问题原样透传)


@pytest.mark.asyncio
async def test_resolve_rewrites_with_history():
    llm = ScriptedLLM(reply='{"query": "《静夜思》这首诗合不合律", "changed": true}')
    history = [{"role": "user", "content": "《静夜思》是谁写的"}, {"role": "assistant", "content": "李白"}]
    assert await resolve_input(llm, "它合不合律", history) == ("《静夜思》这首诗合不合律", True)


@pytest.mark.asyncio
async def test_resolve_keeps_original_when_model_says_unchanged():
    llm = ScriptedLLM(reply='{"query": "《春晓》写的是什么", "changed": false}')
    assert await resolve_input(llm, "《春晓》写的是什么", [{"role": "user", "content": "x"}]) == ("《春晓》写的是什么", False)


@pytest.mark.asyncio
async def test_resolve_passes_through_when_model_fails():
    llm = ScriptedLLM(boom=True)
    assert await resolve_input(llm, "它合律吗", [{"role": "user", "content": "x"}]) == ("它合律吗", False)


@pytest.mark.asyncio
async def test_resolve_passes_through_when_json_unparsable():
    llm = ScriptedLLM(reply="这句得补一下上下文")
    assert await resolve_input(llm, "它合律吗", [{"role": "user", "content": "x"}]) == ("它合律吗", False)
