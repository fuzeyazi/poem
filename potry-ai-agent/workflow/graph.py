"""Ch04 图装配:七个节点 + 条件边(含 ReAct 子循环)+ AsyncSqliteSaver checkpointer。

节点顺序严格按 spec §3.1:
START → 指代消解 → 意图识别 → 意图分流 ─┬─ 知识类: 知识检索 → 置信度闸 ─┬─ 证据足 → 主力Agent ─┐
                                        │                              └─ 不足 → 兜底 + 落 pending ─┤
                                        ├─ 业务类: ─────────────────── 主力Agent ────────────────┤
                                        ├─ 投诉类: 安抚话术 + ["handoff","feedback"] ───────────┤
                                        └─ 闲聊类: 固定话术(不调模型/工具) ─────────────────────┴→ 日志记录 → END
"""
import os

from langgraph.graph import END, START, StateGraph

from workflow.agent_react import agent_node, should_continue, tool_node
from workflow.nodes import (
    after_gate,
    after_resolve,
    after_route,
    after_slot_check,
    classify_node,
    expand_query_node,
    gate_node,
    log_node,
    resolve_node,
    retrieve_node,
    retrieve_policy_node,
    route_node,
    slot_check_node,
    ticket_confirm_node,
)
from workflow.state import WorkflowState

DEFAULT_CHECKPOINT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "checkpoints", "graph.sqlite"
)


async def open_checkpointer(db_path: str = DEFAULT_CHECKPOINT_PATH):
    """建 `AsyncSqliteSaver`,返回 `(saver, conn)`;调用方负责 `await conn.close()`。

    注意两点(均实测):
    1. 官方 `SqliteSaver` 是**同步专用**,异步图会抛 NotImplementedError,故必须用
       `langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver`(已请示用户获批,见 spec §12);
    2. 父目录不存在时 aiosqlite 报 `unable to open database file`,故先 makedirs。
    """
    import aiosqlite
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    if db_path != ":memory:":
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    conn = await aiosqlite.connect(db_path)
    try:
        saver = AsyncSqliteSaver(conn)
        await saver.setup()
    except Exception:  # setup 失败必须回收已开的连接,否则连接泄漏且调用方拿不到它
        await conn.close()
        raise
    return saver, conn


def build_graph(checkpointer):
    """按固定顺序装配并编译(spec §4)。"""
    builder = StateGraph(WorkflowState)
    builder.add_node("resolve", resolve_node)
    builder.add_node("classify", classify_node)
    builder.add_node("route", route_node)
    builder.add_node("slot_check", slot_check_node)
    builder.add_node("expand_query", expand_query_node)
    builder.add_node("retrieve_policy", retrieve_policy_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("gate", gate_node)
    builder.add_node("agent", agent_node)
    builder.add_node("tool_node", tool_node)
    builder.add_node("ticket_confirm", ticket_confirm_node)
    builder.add_node("log", log_node)

    builder.add_edge(START, "resolve")
    builder.add_conditional_edges(
        "resolve", after_resolve, {"slot_check": "slot_check", "classify": "classify"}
    )
    builder.add_edge("classify", "route")
    builder.add_conditional_edges(
        "route", after_route,
        {"retrieve": "retrieve", "agent": "agent", "slot_check": "slot_check", "log": "log"},
    )
    builder.add_edge("retrieve", "gate")
    builder.add_conditional_edges("gate", after_gate, {"agent": "agent", "log": "log"})
    builder.add_conditional_edges(
        "slot_check", after_slot_check, {"expand_query": "expand_query", "log": "log"}
    )
    builder.add_edge("expand_query", "retrieve_policy")
    builder.add_edge("retrieve_policy", "agent")
    builder.add_conditional_edges(
        "agent", should_continue,
        {"tool_node": "tool_node", "ticket_confirm": "ticket_confirm", "log": "log"},
    )
    builder.add_edge("ticket_confirm", "tool_node")
    builder.add_edge("tool_node", "agent")   # ReAct 子循环:工具执行后回到 Agent
    builder.add_edge("log", END)
    return builder.compile(checkpointer=checkpointer)
