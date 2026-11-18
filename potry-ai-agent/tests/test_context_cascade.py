"""端到端(机制级)回归:演示配置下跑长会话,验证降级→摘要→梗概注入的完整级联。

使用脚本化假模型,只验证 Ch06 的上下文编排接线,不替代真实模型验收(见 dev-notes/ch06.md)。
"""
import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import summarizer
from config import Settings
from storage import ChatBase, ChatStorage
from tool_system.audit import AuditWriter
from tool_system.catalog import ToolCatalog
from tool_system.engine import ToolEngine
from workflow.deps import WorkflowDeps, configure
from workflow.graph import build_graph

SUMMARY_TEXT = "用户问过《静夜思》的作者,答案是李白;尚未解决押韵与版本异文。"


def _text(messages) -> str:
    if hasattr(messages, "to_string") and not isinstance(messages, list):
        return messages.to_string()
    parts = []
    for message in messages:
        content = getattr(message, "content", "")
        parts.append(content if isinstance(content, str) else str(content))
    return "\n".join(parts)


class ScriptedLLM:
    """按 prompt 类型吐固定结果;记录主力 Agent 实际收到的上下文。"""

    def __init__(self):
        self.agent_prompt = ""

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages, config=None):
        text = _text(messages)
        if "意图分类器" in text:
            return AIMessage(content='{"intent": "find_poet", "confidence": 0.9}')
        if "对话理解助手" in text:
            return AIMessage(content='{"query": "这首诗的作者是谁", "changed": false}')
        if "会话摘要助手" in text:
            return AIMessage(content=SUMMARY_TEXT)
        self.agent_prompt = text
        return AIMessage(content="答" * 200)


def make_settings(**over):
    base = dict(
        llm_base_url="http://fake", llm_api_key="sk-fake", llm_model="fake",
        history_max_tokens=2000, llm_temperature=0.7,
        mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
        model_context_window=18000, max_output_tokens=2000,
        max_user_input_tokens=2000, max_agent_steps=3,
        tool_result_max_tokens=1200, rerank_top_k=5,
    )
    base.update(over)
    return Settings(**base)


@pytest.mark.asyncio
async def test_demo_budget_cascades_downgrade_then_summary_then_injects(capsys):
    summarizer.reset_for_tests()
    engine = create_engine("sqlite:///:memory:")
    ChatBase.metadata.create_all(engine)
    storage = ChatStorage(sessionmaker(bind=engine))
    llm = ScriptedLLM()
    settings = make_settings()
    audit = AuditWriter(None)
    catalog = ToolCatalog(
        engine=ToolEngine(settings, audit), audit=audit,
        plugin_dir=None, mcp_provider=None,
    )
    configure(WorkflowDeps(settings, llm, catalog, None, storage))
    graph = build_graph(InMemorySaver())
    try:
        question = "这首诗的格律和背景请详细说说" + "补充" * 80
        for _ in range(40):
            await graph.ainvoke(
                {"session_id": "cascade", "user_input": question, "started_at": 0.0,
                 "messages": [], "tool_trace": []},
                config={"configurable": {"thread_id": "cascade"}},
            )
        await summarizer.wait_all()

        snapshot = storage.load_context("cascade")
        assert snapshot["layer1From"] > 0, "层 1 超预算后必须前移锚点"
        assert snapshot["summaries"], "层 2 超预算后必须落一段梗概"
        assert snapshot["summaryUpto"] > 0

        out = capsys.readouterr().out
        assert "[ctx] layer1 降级" in out
        assert "summary trigger" in out and "summary done" in out

        await graph.ainvoke(
            {"session_id": "cascade", "user_input": "最开始问的那首诗后来怎么说",
             "started_at": 0.0, "messages": [], "tool_trace": []},
            config={"configurable": {"thread_id": "cascade"}},
        )
        assert "【早期梗概" in llm.agent_prompt
        assert "静夜思" in llm.agent_prompt
    finally:
        summarizer.reset_for_tests()
        configure(None)
