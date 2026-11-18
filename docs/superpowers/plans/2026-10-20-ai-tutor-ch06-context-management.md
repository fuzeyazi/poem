# Ch06 会话上下文管理实现计划(三层裁剪 · 异步摘要 · token 预算 · 多会话)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把内存 dict + 按 token 截断升级为「三层上下文 + 锚点降级 + 后台异步摘要 + 窗口倒推预算 + 上下文日志 + 多会话侧栏」。

**Architecture:** `messages` 表按锚点切成层 2(规则截短)/层 1(原文),层 3 由 `conversation_summaries` 段落承载;`log_node` 落库后只前移 `layer1_from_msg_id` 或投递 `asyncio` 摘要任务;`build_agent_context` 每轮按固定顺序现拼「system → 层 2 → 层 1 → 当前句 → 梗概+证据 → 本轮 ReAct 消息」,State 只经 `add_messages` + checkpoint 保留完整历史。

**Tech Stack:** LangGraph `StateGraph` + `add_messages` + `AsyncSqliteSaver`;LangChain `trim_messages`(既定技术栈,本计划共用其 token 估算思路,不额外引入依赖);MySQL / SQLite;FastAPI;原生 HTML/JS。

---

## 执行约定

- 工作目录:`e:\javatexts\poetry-spring2\potry-ai-agent`
- Python:`.\.venv\Scripts\python.exe`
- 单测:`.\.venv\Scripts\python.exe -m pytest tests\<file> -q`
- 全量:`.\.venv\Scripts\python.exe -m pytest -q`
- 每个任务先写失败测试、再实现、再跑通、再提交;**Task 2–Task 10 只要求本任务测试通过**,全量回归在 Task 11 统一收口(中间任务会短暂破坏既有测试,属计划内)。
- 提交信息用 `feat(ch06): …` / `test(ch06): …` / `fix(ch06): …`。

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `config.py` | Modify | 新增 17 个预算/截短配置项与校验 |
| `context_budget.py` | Create | token 估算、预算推导、启动自检文案 |
| `context_layers.py` | Create | 三层切分、层 2 截短、整轮分组、降级锚点计算 |
| `context_builder.py` | Create | `build_history_context` / `build_agent_context` 固定顺序拼装 |
| `context_log.py` | Create | `log/app.log` 追加写、`model_ctx` / `history_ctx` / 预算日志 |
| `summarizer.py` | Create | 触发判定、`asyncio` 任务、每会话锁、段落追加、锚点推进 |
| `prompts.py` | Modify | 新增 `SUMMARY_PROMPT` |
| `storage.py` | Modify | 加 4 列、`ConversationSummary`、两段式 `persist_turn`、上下文快照/会话列表/消息回载、`ensure_schema` |
| `chat_service.py` | Modify | Ch01 单轮路径改为只落 user+assistant |
| `workflow/deps.py` | Modify | 装配 `budget`;`max_iter` 改用 `max_agent_steps` |
| `workflow/state.py` | Modify | `messages` 改 `add_messages`;新增 `turn_message_start` / `userid`;删 `history` / `HISTORY_TURNS` |
| `workflow/resolve.py` | Modify | `format_history` 支持 `summary` 行 |
| `workflow/nodes.py` | Modify | `resolve` 追加用户消息并打 `history_ctx`;`log` 异步、补 AI、两段式落库、降级与摘要触发 |
| `workflow/agent_react.py` | Modify | 用 `build_agent_context` 取代 `_seed_messages` |
| `main.py` | Modify | `userid` 透传、两个只读接口、启动迁移/预算日志、关闭摘要任务 |
| `static/chat.html` | Modify | 会话侧栏、切换回载、新对话、匿名 userId |
| `eval_summary.py` | Create | 摘要质量评估集(≥10 条真实模型跑批) |
| `evals/demo_ch06.py` | Create | 多轮演示/验收脚本 |
| `tests/test_context_budget.py` 等 6 个新测试 | Create | 见各任务 |
| `tests/test_workflow_*.py`、`test_storage.py`、`test_chat_service.py` | Modify | 适配新契约 |

---

### Task 1: 预算配置与 token 估算

**Files:**
- Modify: `potry-ai-agent/config.py`
- Create: `potry-ai-agent/context_budget.py`
- Test: `potry-ai-agent/tests/test_context_budget.py`

- [ ] **Step 1: 写失败测试**

```python
"""token 估算口径与从窗口倒推的预算(spec §6)。"""
import math

from config import Settings
from context_budget import (
    Budget,
    derive_budget,
    estimate_message_tokens,
    estimate_tokens,
    self_check_lines,
)


def make_settings(**over):
    base = dict(
        llm_base_url="http://fake", llm_api_key="CONFIGURE_LOCALLY", llm_model="fake",
        history_max_tokens=2000, llm_temperature=0.7,
        mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
    )
    base.update(over)
    return Settings(**base)


def demo_settings():
    return make_settings(
        model_context_window=18000, max_output_tokens=2000,
        max_user_input_tokens=2000, max_agent_steps=3,
        tool_result_max_tokens=1200, rerank_top_k=5,
    )


def test_estimate_tokens_mixes_cjk_and_ascii():
    assert estimate_tokens("床前明月光") == 3          # ceil(5*0.6)
    assert estimate_tokens("abc") == 1                # ceil(3/4)
    assert estimate_tokens("诗abc") == math.ceil(0.6 + 0.75)
    assert estimate_tokens("") == 0
    assert estimate_message_tokens("床前明月光") == 7  # 3 + 4 开销


def test_demo_config_matches_acceptance_numbers():
    b = derive_budget(demo_settings())
    assert (b.history, b.layer1, b.layer2) == (5650, 3954, 1695)
    assert b.layer1 + b.layer2 + 1 == b.history
    assert b.ok is True


def test_default_config_keeps_twenty_turns_uncompressed():
    b = derive_budget(make_settings())
    assert (b.history, b.layer1, b.layer2) == (16000, 11199, 4800)
    assert b.layer1 >= 20 * 400


def test_zero_window_reports_budget_insufficient():
    b = derive_budget(make_settings(model_context_window=1000))
    assert b.ok is False and b.history == 0 and b.layer1 == 0
    lines = self_check_lines(b, turn_steady=400)
    assert any("上下文预算不足" in line for line in lines)


def test_layer1_smaller_than_one_turn_warns():
    b = Budget(window=18000, output=2000, user_input=2000, agent_peak=3600,
               fixed=4750, window_side=5650, history=5650, layer1=3954, layer2=1695, ok=True)
    assert self_check_lines(b, turn_steady=5000) == [
        "[ctx] 预算告警:layer1=3954 装不下完整一轮(约 5000 token)"
    ]
```

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_context_budget.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'context_budget'`

- [ ] **Step 3: 实现 `context_budget.py`**

```python
"""token 估算与会话历史预算(从模型窗口倒推,spec §6)。

估算口径与预算常量必须一起校准:只改一边会让净效果反向(估算偏小 → 实际超窗)。
"""
import math
import re
from dataclasses import dataclass

CJK_TOKENS_PER_CHAR = 0.6
CHARS_PER_TOKEN = 4.0
MESSAGE_OVERHEAD_TOKENS = 4

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def estimate_tokens(text: str | None) -> int:
    """中文按 0.6 token/字、其余按 4 字符/token,向上取整。"""
    if not text:
        return 0
    cjk = len(_CJK_RE.findall(text))
    other = len(text) - cjk
    return math.ceil(cjk * CJK_TOKENS_PER_CHAR + other / CHARS_PER_TOKEN)


def estimate_message_tokens(content: str | None) -> int:
    """消息级估算:正文 + role/分隔固定开销。"""
    return estimate_tokens(content) + MESSAGE_OVERHEAD_TOKENS


def estimate_rows_tokens(rows: list[dict]) -> int:
    return sum(estimate_message_tokens(row.get("content")) for row in rows or [])


def estimate_messages_tokens(messages: list) -> int:
    """LangChain 消息列表估算(只数 content,工具定义走固定预留)。"""
    total = 0
    for message in messages or []:
        content = getattr(message, "content", "")
        total += estimate_message_tokens(content if isinstance(content, str) else str(content))
    return total


@dataclass(frozen=True)
class Budget:
    window: int          # 模型上下文窗口
    output: int          # 输出预留
    user_input: int      # 用户输入预留
    agent_peak: int      # 单轮 ReAct 瞬时峰值
    fixed: int           # 系统提示 + 证据 + 梗概 + 安全余量
    window_side: int     # 窗口实际匀给历史的量
    history: int         # min(想留住的轮数×每轮稳态, window_side)
    layer1: int          # 七成(扣层间 1 token)
    layer2: int          # 三成
    ok: bool


def derive_budget(settings) -> Budget:
    """严格按需求原文:history = min(KEEP_TURNS×TURN_STEADY, window_side),再七三分。"""
    agent_peak = max(0, settings.max_agent_steps * settings.tool_result_max_tokens)
    fixed = (
        settings.system_reserve_tokens
        + settings.rerank_top_k * settings.evidence_per_chunk_tokens
        + settings.summary_reserve_tokens
        + settings.safety_reserve_tokens
    )
    window_side = (
        settings.model_context_window
        - settings.max_output_tokens
        - settings.max_user_input_tokens
        - agent_peak
        - fixed
    )
    history = min(settings.keep_turns * settings.turn_steady_tokens, window_side)
    if history <= 0:
        return Budget(
            window=settings.model_context_window, output=settings.max_output_tokens,
            user_input=settings.max_user_input_tokens, agent_peak=agent_peak,
            fixed=fixed, window_side=window_side, history=0, layer1=0, layer2=0, ok=False,
        )
    layer2 = int(history * 0.3)
    layer1 = history - layer2 - settings.boundary_reserve_tokens
    return Budget(
        window=settings.model_context_window, output=settings.max_output_tokens,
        user_input=settings.max_user_input_tokens, agent_peak=agent_peak,
        fixed=fixed, window_side=window_side, history=history,
        layer1=max(layer1, 0), layer2=layer2, ok=layer1 > 0,
    )


def budget_line(budget: Budget) -> str:
    return (
        f"[ctx] 预算:window={budget.window} history={budget.history} "
        f"layer1={budget.layer1} layer2={budget.layer2}"
    )


def self_check_lines(budget: Budget, turn_steady: int) -> list[str]:
    """启动自检:预算归零 → 报警;层 1 装不下一整轮 → 告警。"""
    if not budget.ok:
        return [
            f"[ctx] 上下文预算不足:history_budget={budget.history} layer1={budget.layer1}"
            "(请调大 MODEL_CONTEXT_WINDOW 或调小固定开销)"
        ]
    if budget.layer1 < turn_steady:
        return [f"[ctx] 预算告警:layer1={budget.layer1} 装不下完整一轮(约 {turn_steady} token)"]
    return []
```

- [ ] **Step 4: 在 `config.py` 增加默认常量、字段与解析**

在 `_DEFAULT_WORKFLOW_CHECKPOINT_PATH` 之后追加:

```python
# Ch06:上下文预算/三层截短默认值(与 Settings 共用,单一来源)
_DEFAULT_MODEL_CONTEXT_WINDOW = 64000
_DEFAULT_MAX_OUTPUT_TOKENS = 4000
_DEFAULT_MAX_USER_INPUT_TOKENS = 2000
_DEFAULT_TOOL_RESULT_MAX_TOKENS = 1200
_DEFAULT_RERANK_TOP_K = 5
_DEFAULT_SYSTEM_RESERVE_TOKENS = 1500
_DEFAULT_EVIDENCE_PER_CHUNK_TOKENS = 250
_DEFAULT_SUMMARY_RESERVE_TOKENS = 500
_DEFAULT_SAFETY_RESERVE_TOKENS = 1500
_DEFAULT_KEEP_TURNS = 40
_DEFAULT_TURN_STEADY_TOKENS = 400
_DEFAULT_BOUNDARY_RESERVE_TOKENS = 1
_DEFAULT_SUMMARY_BATCH_MAX_TOKENS = 3000
_DEFAULT_HISTORY_CTX_MAX_TOKENS = 2000
_DEFAULT_LAYER2_ASSISTANT_PREFIX_CHARS = 40
_DEFAULT_LAYER2_BLOB_CHARS = 400
```

`Settings` 增加字段(放在 `workflow_checkpoint_path` 之后):

```python
    model_context_window: int = _DEFAULT_MODEL_CONTEXT_WINDOW
    max_output_tokens: int = _DEFAULT_MAX_OUTPUT_TOKENS
    max_user_input_tokens: int = _DEFAULT_MAX_USER_INPUT_TOKENS
    max_agent_steps: int = _DEFAULT_WORKFLOW_MAX_ITER
    tool_result_max_tokens: int = _DEFAULT_TOOL_RESULT_MAX_TOKENS
    rerank_top_k: int = _DEFAULT_RERANK_TOP_K
    system_reserve_tokens: int = _DEFAULT_SYSTEM_RESERVE_TOKENS
    evidence_per_chunk_tokens: int = _DEFAULT_EVIDENCE_PER_CHUNK_TOKENS
    summary_reserve_tokens: int = _DEFAULT_SUMMARY_RESERVE_TOKENS
    safety_reserve_tokens: int = _DEFAULT_SAFETY_RESERVE_TOKENS
    keep_turns: int = _DEFAULT_KEEP_TURNS
    turn_steady_tokens: int = _DEFAULT_TURN_STEADY_TOKENS
    boundary_reserve_tokens: int = _DEFAULT_BOUNDARY_RESERVE_TOKENS
    summary_batch_max_tokens: int = _DEFAULT_SUMMARY_BATCH_MAX_TOKENS
    history_ctx_max_tokens: int = _DEFAULT_HISTORY_CTX_MAX_TOKENS
    layer2_assistant_prefix_chars: int = _DEFAULT_LAYER2_ASSISTANT_PREFIX_CHARS
    layer2_blob_chars: int = _DEFAULT_LAYER2_BLOB_CHARS
```

在 `load_settings` 的 `try` 里追加(注意 `max_agent_steps` 在 `workflow_max_iter` 之后解析):

```python
        model_context_window = int(os.getenv("MODEL_CONTEXT_WINDOW") or str(_DEFAULT_MODEL_CONTEXT_WINDOW))
        max_output_tokens = int(os.getenv("MAX_OUTPUT_TOKENS") or str(_DEFAULT_MAX_OUTPUT_TOKENS))
        max_user_input_tokens = int(os.getenv("MAX_USER_INPUT_TOKENS") or str(_DEFAULT_MAX_USER_INPUT_TOKENS))
        max_agent_steps = int(os.getenv("MAX_AGENT_STEPS") or str(workflow_max_iter))
        tool_result_max_tokens = int(os.getenv("TOOL_RESULT_MAX_TOKENS") or str(_DEFAULT_TOOL_RESULT_MAX_TOKENS))
        rerank_top_k = int(os.getenv("RERANK_TOP_K") or str(_DEFAULT_RERANK_TOP_K))
        system_reserve_tokens = int(os.getenv("SYSTEM_RESERVE_TOKENS") or str(_DEFAULT_SYSTEM_RESERVE_TOKENS))
        evidence_per_chunk_tokens = int(os.getenv("EVIDENCE_PER_CHUNK_TOKENS") or str(_DEFAULT_EVIDENCE_PER_CHUNK_TOKENS))
        summary_reserve_tokens = int(os.getenv("SUMMARY_RESERVE_TOKENS") or str(_DEFAULT_SUMMARY_RESERVE_TOKENS))
        safety_reserve_tokens = int(os.getenv("SAFETY_RESERVE_TOKENS") or str(_DEFAULT_SAFETY_RESERVE_TOKENS))
        keep_turns = int(os.getenv("KEEP_TURNS") or str(_DEFAULT_KEEP_TURNS))
        turn_steady_tokens = int(os.getenv("TURN_STEADY_TOKENS") or str(_DEFAULT_TURN_STEADY_TOKENS))
        boundary_reserve_tokens = int(os.getenv("BOUNDARY_RESERVE_TOKENS") or str(_DEFAULT_BOUNDARY_RESERVE_TOKENS))
        summary_batch_max_tokens = int(os.getenv("SUMMARY_BATCH_MAX_TOKENS") or str(_DEFAULT_SUMMARY_BATCH_MAX_TOKENS))
        history_ctx_max_tokens = int(os.getenv("HISTORY_CTX_MAX_TOKENS") or str(_DEFAULT_HISTORY_CTX_MAX_TOKENS))
        layer2_assistant_prefix_chars = int(os.getenv("LAYER2_ASSISTANT_PREFIX_CHARS") or str(_DEFAULT_LAYER2_ASSISTANT_PREFIX_CHARS))
        layer2_blob_chars = int(os.getenv("LAYER2_BLOB_CHARS") or str(_DEFAULT_LAYER2_BLOB_CHARS))
```

在既有 fail-fast 校验之后追加:

```python
    for name, value in (
        ("MODEL_CONTEXT_WINDOW", model_context_window),
        ("MAX_OUTPUT_TOKENS", max_output_tokens),
        ("MAX_USER_INPUT_TOKENS", max_user_input_tokens),
        ("MAX_AGENT_STEPS", max_agent_steps),
        ("TOOL_RESULT_MAX_TOKENS", tool_result_max_tokens),
        ("RERANK_TOP_K", rerank_top_k),
        ("KEEP_TURNS", keep_turns),
        ("TURN_STEADY_TOKENS", turn_steady_tokens),
        ("SUMMARY_BATCH_MAX_TOKENS", summary_batch_max_tokens),
        ("HISTORY_CTX_MAX_TOKENS", history_ctx_max_tokens),
        ("LAYER2_ASSISTANT_PREFIX_CHARS", layer2_assistant_prefix_chars),
        ("LAYER2_BLOB_CHARS", layer2_blob_chars),
    ):
        if value <= 0:
            raise RuntimeError(f"{name} 必须为正整数(当前: {value})")
    for name, value in (
        ("SYSTEM_RESERVE_TOKENS", system_reserve_tokens),
        ("EVIDENCE_PER_CHUNK_TOKENS", evidence_per_chunk_tokens),
        ("SUMMARY_RESERVE_TOKENS", summary_reserve_tokens),
        ("SAFETY_RESERVE_TOKENS", safety_reserve_tokens),
        ("BOUNDARY_RESERVE_TOKENS", boundary_reserve_tokens),
    ):
        if value < 0:
            raise RuntimeError(f"{name} 不得为负数(当前: {value})")
```

在 `return Settings(...)` 里补上所有新字段:

```python
        model_context_window=model_context_window,
        max_output_tokens=max_output_tokens,
        max_user_input_tokens=max_user_input_tokens,
        max_agent_steps=max_agent_steps,
        tool_result_max_tokens=tool_result_max_tokens,
        rerank_top_k=rerank_top_k,
        system_reserve_tokens=system_reserve_tokens,
        evidence_per_chunk_tokens=evidence_per_chunk_tokens,
        summary_reserve_tokens=summary_reserve_tokens,
        safety_reserve_tokens=safety_reserve_tokens,
        keep_turns=keep_turns,
        turn_steady_tokens=turn_steady_tokens,
        boundary_reserve_tokens=boundary_reserve_tokens,
        summary_batch_max_tokens=summary_batch_max_tokens,
        history_ctx_max_tokens=history_ctx_max_tokens,
        layer2_assistant_prefix_chars=layer2_assistant_prefix_chars,
        layer2_blob_chars=layer2_blob_chars,
```

- [ ] **Step 5: 跑测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_context_budget.py tests\test_config.py -q`
Expected: PASS(预算三组数字逐位一致)

- [ ] **Step 6: 提交**

```bash
git add potry-ai-agent/config.py potry-ai-agent/context_budget.py potry-ai-agent/tests/test_context_budget.py
git commit -m "feat(ch06): add window-derived token budget and estimation"
```

---

### Task 2: 存储层:加列、摘要表、两段式落库、会话查询

**Files:**
- Modify: `potry-ai-agent/storage.py`
- Modify: `potry-ai-agent/chat_service.py:136-141`
- Modify: `potry-ai-agent/workflow/nodes.py:189-219`
- Test: `potry-ai-agent/tests/test_storage.py`(重写)、`tests/test_chat_service.py:151-153,234-236`

- [ ] **Step 1: 写失败测试(重写 `test_storage.py`)**

```python
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from storage import (
    ChatBase,
    ChatStorage,
    Conversation,
    ConversationSummary,
    Message,
    ensure_schema,
)


def make_storage():
    engine = create_engine("sqlite:///:memory:")
    ChatBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    return ChatStorage(factory), factory


def test_persist_turn_writes_two_rows_and_returns_ids():
    st, _ = make_storage()
    cid, uid, aid = st.persist_turn("s1", "《静夜思》是谁写的", "是李白", userid="u1")
    assert uid is not None and aid is not None and uid < aid
    rows = st.load_messages(cid)
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert rows[0]["content"] == "《静夜思》是谁写的"
    assert rows[1]["content"] == "是李白"


def test_resume_turn_skips_empty_user_row():
    st, _ = make_storage()
    _, uid, aid = st.persist_turn("s1", "", "判定结果")
    assert uid is None
    assert [r["role"] for r in st.load_messages(1)] == ["assistant"]


def test_conversation_reused_and_userid_kept():
    st, _ = make_storage()
    cid1, _, _ = st.persist_turn("s1", "第一句", "答一", userid="u1")
    cid2, _, _ = st.persist_turn("s1", "第二句", "答二", userid="u1")
    assert cid1 == cid2
    assert len(st.load_messages(cid1)) == 4


def test_load_context_returns_rows_anchors_and_summaries():
    st, _ = make_storage()
    st.persist_turn("s1", "第一问", "第一答")
    st.persist_turn("s1", "第二问", "第二答")
    snapshot = st.load_context("s1")
    assert [r["role"] for r in snapshot["rows"]] == ["user", "assistant", "user", "assistant"]
    assert snapshot["summaryUpto"] == 0 and snapshot["layer1From"] == 0
    assert snapshot["conversationId"] == 1


def test_add_summary_appends_seq_and_advances_anchor():
    st, _ = make_storage()
    st.persist_turn("s1", "问", "答")
    assert st.add_summary(1, "用户问了《静夜思》。", upto_msg_id=2) == 1
    assert st.add_summary(1, "用户又问了李白。", upto_msg_id=4) == 2
    snapshot = st.load_context("s1")
    assert snapshot["summaryUpto"] == 4
    assert [s["seq"] for s in snapshot["summaries"]] == [1, 2]


def test_summary_unique_key_enforced():
    _, factory = make_storage()
    with factory() as session:
        session.add(Conversation(session_id="s1"))
        session.flush()
        session.add(ConversationSummary(conversation_id=1, seq=1, upto_msg_id=2, content="a"))
        session.commit()
    with pytest.raises(IntegrityError):
        with factory() as session:
            session.add(ConversationSummary(conversation_id=1, seq=1, upto_msg_id=3, content="b"))
            session.commit()


def test_list_conversations_sorted_preview_and_summarized():
    st, _ = make_storage()
    st.persist_turn("old", "《静夜思》是谁写的", "李白", userid="u1")
    _, _, _ = st.persist_turn("new", "找一首写月亮的诗", "《静夜思》", userid="u1")
    st.add_summary(1, "梗概", upto_msg_id=2)
    convs = st.list_conversations("u1")
    assert [c["sessionId"] for c in convs] == ["new", "old"]
    assert convs[0]["preview"].startswith("找一首写月亮的诗")
    assert convs[1]["summarized"] is True
    assert st.list_conversations("u2") == []


def test_load_conversation_messages_filters_tool_and_checks_user():
    st, factory = make_storage()
    st.persist_turn("s1", "问", "答", userid="u1")
    with factory() as session:
        session.add(Message(conversation_id=1, role="tool", content='{"ok": true}'))
        session.commit()
    rows = st.load_conversation_messages("s1", "u1")
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert st.load_conversation_messages("s1", "u2") is None
    assert st.load_conversation_messages("nope", "u1") is None


def test_ensure_schema_adds_missing_columns(tmp_path):
    db = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE conversations (id INTEGER PRIMARY KEY, session_id VARCHAR(64), created_at DATETIME)"
        ))
    ensure_schema(engine)
    names = {c["name"] for c in inspect(engine).get_columns("conversations")}
    assert {"userid", "summary_upto_msg_id", "layer1_from_msg_id", "updated_at"} <= names
```

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_storage.py -q`
Expected: FAIL — `ImportError: cannot import name 'ConversationSummary'`

- [ ] **Step 3: 重写 `storage.py`**

```python
"""对话落库:conversations / messages / conversation_summaries(ChatBase 独立于诗词表)。"""
import json
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    inspect,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

# 主键/外键列类型:MySQL 用 BIGINT;SQLite 仅 INTEGER PRIMARY KEY 才自增
_ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class ChatBase(DeclarativeBase):
    pass


class Conversation(ChatBase):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    userid: Mapped[str | None] = mapped_column(String(64), index=True)
    summary_upto_msg_id: Mapped[int] = mapped_column(_ID_TYPE, default=0)
    layer1_from_msg_id: Mapped[int] = mapped_column(_ID_TYPE, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.now)


class Message(ChatBase):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(_ID_TYPE, ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(String(64))
    tool_call_id: Mapped[str | None] = mapped_column(String(64))
    tool_args: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ConversationSummary(ChatBase):
    __tablename__ = "conversation_summaries"
    __table_args__ = (UniqueConstraint("conversation_id", "seq", name="uq_summary_conv_seq"),)

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(_ID_TYPE, ForeignKey("conversations.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    upto_msg_id: Mapped[int] = mapped_column(_ID_TYPE)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


def ensure_schema(engine) -> None:
    """给已存在的 conversations 表补列(create_all 不会加列);失败逐列告警不阻断。"""
    inspector = inspect(engine)
    if "conversations" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("conversations")}
    ddl = {
        "userid": "VARCHAR(64) NULL",
        "summary_upto_msg_id": "BIGINT NOT NULL DEFAULT 0",
        "layer1_from_msg_id": "BIGINT NOT NULL DEFAULT 0",
        "updated_at": "DATETIME NULL",
    }
    for name, column_type in ddl.items():
        if name in existing:
            continue
        try:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE conversations ADD COLUMN {name} {column_type}"))
            print(f"[db] 迁移:conversations 新增列 {name}")
        except Exception as exc:  # noqa: BLE001 - 单列失败不影响其他列与服务启动
            print(f"[db] 迁移失败 col={name}: {str(exc)[:200]}")


class ChatStorage:
    """每轮只落 user + 最终 assistant;完整工具历史由 LangGraph checkpoint 保留。"""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._factory = session_factory

    def _conversation(self, session, session_id: str) -> Conversation | None:
        return (
            session.query(Conversation)
            .filter_by(session_id=session_id)
            .order_by(Conversation.id)
            .first()
        )

    def persist_turn(
        self, session_id: str, user_text: str, answer: str, userid: str | None = None
    ) -> tuple[int, int | None, int]:
        """写一条 user(非空时)与一条 assistant,返回 (conversation_id, user_msg_id, assistant_msg_id)。"""
        with self._factory() as session:
            conv = self._conversation(session, session_id)
            if conv is None:
                conv = Conversation(session_id=session_id, userid=userid)
                session.add(conv)
                session.flush()
            elif userid and not conv.userid:
                conv.userid = userid
            conv.updated_at = datetime.now()
            user_id = None
            if (user_text or "").strip():
                row = Message(conversation_id=conv.id, role="user", content=user_text)
                session.add(row)
                session.flush()
                user_id = row.id
            answer_row = Message(conversation_id=conv.id, role="assistant", content=answer or "")
            session.add(answer_row)
            session.flush()
            session.commit()
            return conv.id, user_id, answer_row.id

    def load_messages(self, conversation_id: int) -> list[dict]:
        with self._factory() as session:
            msgs = (
                session.query(Message)
                .filter_by(conversation_id=conversation_id)
                .order_by(Message.id)
                .all()
            )
            return [
                {
                    "role": m.role,
                    "content": m.content,
                    "tool_name": m.tool_name,
                    "tool_call_id": m.tool_call_id,
                    "tool_args": m.tool_args,
                }
                for m in msgs
            ]

    def load_context(self, session_id: str) -> dict:
        """一次取齐锚点、逐条消息(user/assistant)与摘要段落,供三层拼装。"""
        with self._factory() as session:
            conv = self._conversation(session, session_id)
            if conv is None:
                return {"conversationId": None, "summaryUpto": 0, "layer1From": 0,
                        "rows": [], "summaries": []}
            rows = (
                session.query(Message)
                .filter(Message.conversation_id == conv.id, Message.role.in_(("user", "assistant")))
                .order_by(Message.id)
                .all()
            )
            summaries = (
                session.query(ConversationSummary)
                .filter_by(conversation_id=conv.id)
                .order_by(ConversationSummary.seq)
                .all()
            )
            return {
                "conversationId": conv.id,
                "summaryUpto": conv.summary_upto_msg_id or 0,
                "layer1From": conv.layer1_from_msg_id or 0,
                "rows": [{"id": m.id, "role": m.role, "content": m.content} for m in rows],
                "summaries": [
                    {"seq": s.seq, "uptoMsgId": s.upto_msg_id, "content": s.content}
                    for s in summaries
                ],
            }

    def advance_layer1_anchor(self, conversation_id: int, msg_id: int) -> None:
        with self._factory() as session:
            conv = session.get(Conversation, conversation_id)
            if conv is not None:
                conv.layer1_from_msg_id = max(conv.layer1_from_msg_id or 0, msg_id)
                session.commit()

    def add_summary(self, conversation_id: int, content: str, upto_msg_id: int) -> int | None:
        """追加一段梗概并推进摘要锚点;唯一键冲突返回 None(视为已有同段)。"""
        with self._factory() as session:
            conv = session.get(Conversation, conversation_id)
            if conv is None:
                return None
            seq = (
                session.query(func.max(ConversationSummary.seq))
                .filter_by(conversation_id=conversation_id)
                .scalar()
                or 0
            ) + 1
            session.add(
                ConversationSummary(
                    conversation_id=conversation_id, seq=seq,
                    upto_msg_id=upto_msg_id, content=content,
                )
            )
            conv.summary_upto_msg_id = max(conv.summary_upto_msg_id or 0, upto_msg_id)
            conv.updated_at = datetime.now()
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return None
            return seq

    def list_conversations(self, userid: str | None = None) -> list[dict]:
        with self._factory() as session:
            query = session.query(Conversation)
            if userid:
                query = query.filter(Conversation.userid == userid)
            conversations = query.order_by(
                func.coalesce(Conversation.updated_at, Conversation.created_at).desc(),
                Conversation.id.desc(),
            ).all()
            out = []
            for conv in conversations:
                first = (
                    session.query(Message)
                    .filter_by(conversation_id=conv.id, role="user")
                    .order_by(Message.id)
                    .first()
                )
                stamp = conv.updated_at or conv.created_at
                out.append(
                    {
                        "sessionId": conv.session_id,
                        "preview": (first.content or "")[:30] if first else "",
                        "updatedAt": stamp.strftime("%Y-%m-%d %H:%M") if stamp else "",
                        "summarized": (conv.summary_upto_msg_id or 0) > 0,
                    }
                )
            return out

    def load_conversation_messages(self, session_id: str, userid: str | None = None) -> list[dict] | None:
        """只读回载:只返回 user/assistant;会话不存在或 userId 不匹配返回 None(→404)。"""
        with self._factory() as session:
            conv = self._conversation(session, session_id)
            if conv is None:
                return None
            if userid and conv.userid and conv.userid != userid:
                return None
            rows = (
                session.query(Message)
                .filter(Message.conversation_id == conv.id, Message.role.in_(("user", "assistant")))
                .order_by(Message.id)
                .all()
            )
            return [
                {
                    "role": m.role,
                    "content": m.content,
                    "createdAt": m.created_at.strftime("%Y-%m-%d %H:%M") if m.created_at else "",
                }
                for m in rows
            ]
```

- [ ] **Step 4: 适配 `chat_service.py`(Ch01 单轮路径也只落两行)**

删除 `tool_records` 变量及全部 `tool_records.append(...)`(不再落库,留着是死代码);`finally` 改为:

```python
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
```

- [ ] **Step 5: 适配 `workflow/nodes.py::_persist_turn` 到新签名(暂只返回三 id,Task 9 再用)**

```python
def _persist_turn(state: dict):
    """把本轮 user(非空时)+ 最终 assistant 落库,返回 (conversation_id, user_msg_id, assistant_msg_id)。"""
    deps = get_deps()
    if deps.chat_storage is None:
        return None
    try:
        return deps.chat_storage.persist_turn(
            state.get("session_id", ""),
            state.get("user_input", ""),
            state.get("answer", ""),
            state.get("userid"),
        )
    except Exception as exc:  # noqa: BLE001 - 落库失败不打断对话
        print(f"[wf] storage fail: {str(exc)[:200]}")
        return None
```

- [ ] **Step 6: 更新既有测试中的落库断言**

`tests/test_chat_service.py` 两处:

```python
    # 落库:只落 user + 最终 assistant(工具结果不落消息表)
    rows = storage.load_messages(1)
    assert [r["role"] for r in rows] == ["user", "assistant"]
```

`tests/test_mining.py` 的落库种子改为两段式:

```python
    chat.persist_turn("s1", "月亮那首叫啥", "静夜思")
```

(第 57、69、93、107 行四处同改)

工具中间态那条用例保留原意,改为直接写库构造遗留四行:

```python
def test_mine_pairs_final_answer_not_tool_intermediate(env):
    """工具轮的最终答案必须配对到用户问题,不能配到 content 为空的中间态 assistant。"""
    from storage import Conversation, Message

    storage, chat = env
    with chat._factory() as session:
        session.add(Conversation(session_id="s1"))
        session.flush()
        session.add(Message(conversation_id=1, role="user", content="静夜思谁写的"))
        session.add(Message(conversation_id=1, role="assistant", content="", tool_call_id="call_1"))
        session.add(Message(conversation_id=1, role="tool", content='{"ok": true}'))
        session.add(Message(conversation_id=1, role="assistant", content="李白。"))
        session.commit()
    transcripts = mining._load_transcripts(chat, 0)
    assert transcripts[0]["pairs"] == [{"user": "静夜思谁写的", "assistant": "李白。"}]
```

`tests/test_workflow_nodes.py::FakeChatStorage` 与 `tests/test_workflow_graph.py::FakeChatStorage` 暂时改成:

```python
class FakeChatStorage:
    def __init__(self):
        self.turns = []

    def persist_turn(self, session_id, user_text, answer, userid=None):
        self.turns.append((session_id, user_text, answer))
        return 1, 100, 101
```

对应断言 `chat.turns[0]` 的解包改为 `(session_id, user_text, answer) = chat.turns[0]`。

- [ ] **Step 7: 跑测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_storage.py tests\test_chat_service.py tests\test_mining.py tests\test_workflow_nodes.py tests\test_workflow_graph.py -q`
Expected: PASS(节点/图测试可能因 history 语义仍绿——本任务未改 resolve)

- [ ] **Step 8: 提交**

```bash
git add potry-ai-agent/storage.py potry-ai-agent/chat_service.py potry-ai-agent/workflow/nodes.py potry-ai-agent/tests/test_storage.py potry-ai-agent/tests/test_chat_service.py potry-ai-agent/tests/test_mining.py potry-ai-agent/tests/test_workflow_nodes.py potry-ai-agent/tests/test_workflow_graph.py
git commit -m "feat(ch06): persist two rows per turn and add conversation summaries storage"
```

---

### Task 3: 三层切分、层 2 截短、降级锚点

**Files:**
- Create: `potry-ai-agent/context_layers.py`
- Test: `potry-ai-agent/tests/test_context_layers.py`

- [ ] **Step 1: 写失败测试**

```python
from context_layers import downgrade_anchor, split_layers, truncate_layer2, turn_groups


ROWS = [
    {"id": 1, "role": "user", "content": "问一"},
    {"id": 2, "role": "assistant", "content": "答一"},
    {"id": 3, "role": "user", "content": "问二"},
    {"id": 4, "role": "assistant", "content": "答二"},
    {"id": 5, "role": "user", "content": "问三"},
    {"id": 6, "role": "assistant", "content": "答三"},
]


def test_split_layers_respects_both_anchors():
    layers = split_layers(ROWS, summary_upto_msg_id=2, layer1_from_msg_id=4)
    assert [r["id"] for r in layers.layer2] == [3, 4]
    assert [r["id"] for r in layers.layer1] == [5, 6]


def test_split_layers_all_in_layer1_when_anchors_zero():
    layers = split_layers(ROWS, 0, 0)
    assert layers.layer2 == []
    assert [r["id"] for r in layers.layer1] == [1, 2, 3, 4, 5, 6]


def test_truncate_keeps_user_verbatim_and_cuts_assistant_and_blob():
    rows = [
        {"id": 1, "role": "user", "content": "用" * 500},
        {"id": 2, "role": "assistant", "content": "答" * 41},
        {"id": 3, "role": "assistant", "content": "答" * 500},
    ]
    out = truncate_layer2(rows, prefix_chars=40, blob_chars=400)
    assert out[0]["content"] == "用" * 500
    assert out[1]["content"] == "答" * 40 + "…"
    assert out[2]["content"] == "[工具结果:500字]"


def test_turn_groups_split_on_user_boundary():
    groups = turn_groups(ROWS)
    assert [[r["id"] for r in g] for g in groups] == [[1, 2], [3, 4], [5, 6]]


def test_downgrade_returns_none_when_within_budget():
    assert downgrade_anchor(ROWS, budget_tokens=10_000) is None


def test_downgrade_moves_complete_turns_until_under_budget():
    # 每轮约 2 条 × (1 字中文=1 token)+4 开销 = 10 token
    assert downgrade_anchor(ROWS, budget_tokens=25) == 4
```

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_context_layers.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'context_layers'`

- [ ] **Step 3: 实现 `context_layers.py`**

```python
"""三层切分与层 2 确定性截短(spec §4)。锚点只比对 messages.id,降级不搬数据。"""
from dataclasses import dataclass

from context_budget import estimate_rows_tokens


@dataclass
class Layers:
    layer2: list[dict]
    layer1: list[dict]


def split_layers(rows: list[dict], summary_upto_msg_id: int, layer1_from_msg_id: int) -> Layers:
    """层 3: id ≤ summaryUpto;层 2: summaryUpto < id ≤ layer1From;层 1: id > layer1From。"""
    up_to = summary_upto_msg_id or 0
    from_id = layer1_from_msg_id or 0
    layer2: list[dict] = []
    layer1: list[dict] = []
    for row in rows or []:
        msg_id = row.get("id") or 0
        if msg_id <= up_to:
            continue
        if msg_id <= from_id:
            layer2.append(row)
        else:
            layer1.append(row)
    return Layers(layer2=layer2, layer1=layer1)


def truncate_content(role: str, content: str, prefix_chars: int, blob_chars: int) -> str:
    text = content or ""
    if role == "user":
        return text                                    # 用户原话一个字不动
    if len(text) > blob_chars:
        return f"[工具结果:{len(text)}字]"              # 大块内容换一行标识(含遗留 tool 行)
    if role == "assistant" and len(text) > prefix_chars:
        return text[:prefix_chars] + "…"
    return text


def truncate_layer2(rows: list[dict], prefix_chars: int, blob_chars: int) -> list[dict]:
    return [
        {**row, "content": truncate_content(row.get("role", ""), row.get("content", ""), prefix_chars, blob_chars)}
        for row in rows or []
    ]


def turn_groups(rows: list[dict]) -> list[list[dict]]:
    """按 user 边界切完整轮;开头的 assistant(续跑轮)自成一组。"""
    groups: list[list[dict]] = []
    current: list[dict] = []
    for row in rows or []:
        if row.get("role") == "user" and current:
            groups.append(current)
            current = [row]
        else:
            current.append(row)
    if current:
        groups.append(current)
    return groups


def downgrade_anchor(layer1_rows: list[dict], budget_tokens: int) -> int | None:
    """层 1 超预算 → 返回新锚点(被搬走批次的最末消息 id);无需降级返回 None。"""
    if estimate_rows_tokens(layer1_rows) <= budget_tokens:
        return None
    dropped: list[dict] = []
    for group in turn_groups(layer1_rows):
        dropped.extend(group)
        remaining = layer1_rows[len(dropped):]
        if estimate_rows_tokens(remaining) <= budget_tokens:
            break
    return dropped[-1]["id"] if dropped else None
```

- [ ] **Step 4: 跑测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_context_layers.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add potry-ai-agent/context_layers.py potry-ai-agent/tests/test_context_layers.py
git commit -m "feat(ch06): add three-layer split and deterministic layer2 truncation"
```

---

### Task 4: 上下文日志(`log/app.log`)

**Files:**
- Create: `potry-ai-agent/context_log.py`
- Test: `potry-ai-agent/tests/test_context_log.py`

- [ ] **Step 1: 写失败测试**

```python
from dataclasses import dataclass

import context_log
from context_budget import Budget


@dataclass
class FakeHistory:
    summary: str
    layer2: list
    layer1: list
    tokens: int


@dataclass
class FakeAgent:
    messages: list
    summary: str
    layer2: list
    layer1: list
    current: str
    evidence: str
    combined: str
    system: str
    tokens: int
    turn: int


def _hc():
    return FakeHistory(
        summary="用户问过《静夜思》,诉求是核对作者。",
        layer2=[{"id": 3, "role": "user", "content": "问二"}],
        layer1=[{"id": 5, "role": "assistant", "content": "答三"}],
        tokens=42,
    )


def test_history_ctx_block_is_written_and_terminated(tmp_path, monkeypatch, capsys):
    log_file = tmp_path / "app.log"
    monkeypatch.setattr(context_log, "LOG_PATH", log_file)
    monkeypatch.setattr(context_log, "_DISABLE_FILE", False)
    context_log.log_history_ctx("s1", 2, _hc())
    text = log_file.read_text(encoding="utf-8")
    assert "[ctx] history_ctx 会话=s1 轮=2 摘要=用户问过《静夜思》" in text
    assert "  [层2] user: 问二" in text and "  [层1] assistant: 答三" in text
    assert text.rstrip().endswith("[ctx] end history_ctx")
    assert "history_ctx" in capsys.readouterr().out


def test_history_ctx_empty_still_prints_placeholder(tmp_path, monkeypatch):
    log_file = tmp_path / "app.log"
    monkeypatch.setattr(context_log, "LOG_PATH", log_file)
    monkeypatch.setattr(context_log, "_DISABLE_FILE", False)
    context_log.log_history_ctx("s1", 1, FakeHistory("", [], [], 0))
    text = log_file.read_text(encoding="utf-8")
    assert "  (无)" in text and "[ctx] end history_ctx" in text


def test_model_ctx_contains_summary_window_and_ends(tmp_path, monkeypatch):
    log_file = tmp_path / "app.log"
    monkeypatch.setattr(context_log, "LOG_PATH", log_file)
    monkeypatch.setattr(context_log, "_DISABLE_FILE", False)
    ctx = FakeAgent(
        messages=[], summary="用户问过《静夜思》。", layer2=[{"role": "user", "content": "问二"}],
        layer1=[{"role": "assistant", "content": "答三"}], current="问四",
        evidence="【检索资料】床前明月光", combined="【早期梗概】\n用户问过《静夜思》。",
        system="你是青莲", tokens=99, turn=3,
    )
    context_log.log_model_ctx("s2", 3, ctx)
    text = log_file.read_text(encoding="utf-8")
    assert "[ctx] model_ctx 会话=s2 轮=3 摘要=用户问过《静夜思》。 窗口=2条 估算=99token" in text
    assert "  [层2] user: 问二" in text and "  [层1] assistant: 答三" in text
    assert "  [当前] user: 问四" in text and "  [梗概+证据]" in text
    assert text.rstrip().endswith("[ctx] end model_ctx")


def test_log_write_failure_is_tolerated(monkeypatch):
    # 指向不存在的路径:写失败只告警,不抛异常
    monkeypatch.setattr(context_log, "LOG_PATH", "/dev/null/never/app.log")
    monkeypatch.setattr(context_log, "_DISABLE_FILE", False)
    context_log.log_history_ctx("s1", 1, FakeHistory("", [], [], 0))   # 不抛即通过


def test_budget_line_and_self_check(tmp_path, monkeypatch):
    log_file = tmp_path / "app.log"
    monkeypatch.setattr(context_log, "LOG_PATH", log_file)
    monkeypatch.setattr(context_log, "_DISABLE_FILE", False)
    budget = Budget(64000, 4000, 2000, 4800, 4750, 48450, 16000, 11199, 4800, True)
    context_log.log_budget(budget, turn_steady=400)
    text = log_file.read_text(encoding="utf-8")
    assert "[ctx] 预算:window=64000 history=16000 layer1=11199 layer2=4800" in text
    assert "预算告警" not in text
```

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_context_log.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'context_log'`

- [ ] **Step 3: 实现 `context_log.py`**

```python
"""上下文可观测:统一追加写 log/app.log 并同步 stdout(spec §9)。"""
import os
from pathlib import Path

from context_budget import Budget, budget_line, self_check_lines

LOG_PATH = Path(__file__).resolve().parent / "log" / "app.log"
_DISABLE_FILE = os.getenv("CTX_LOG_DISABLE", "").strip().lower() in ("1", "true")


def _write(line: str) -> None:
    print(line)
    if _DISABLE_FILE:
        return
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception as exc:  # noqa: BLE001 - 日志失败不影响对话
        print(f"[ctx] 日志写入失败: {str(exc)[:200]}")


def _clip(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "…"


def log_history_ctx(session_id: str, turn: int, hc) -> None:
    """消解/意图共用的历史:摘要一行 + 滑窗;每轮必打,空历史也打 (无)。"""
    summary = _clip((hc.summary or "").replace("\n", " "), 80) if hc.summary else "(无)"
    lines = [
        f"[ctx] history_ctx 会话={session_id or '-'} 轮={turn} 摘要={summary} "
        f"滑窗={len(hc.layer2) + len(hc.layer1)}条 估算={hc.tokens}token"
    ]
    for row in hc.layer2:
        lines.append(f"  [层2] {row.get('role')}: {row.get('content')}")
    for row in hc.layer1:
        lines.append(f"  [层1] {row.get('role')}: {row.get('content')}")
    if len(lines) == 1:
        lines.append("  (无)")
    lines.append("[ctx] end history_ctx")
    _write("\n".join(lines))


def log_model_ctx(session_id: str, turn: int, ctx) -> None:
    """主力 Agent 实际发出的上下文:摘要全文 + 滑窗逐条 + 条数 + 估算。"""
    summary = ctx.summary or "(无)"
    lines = [
        f"[ctx] model_ctx 会话={session_id or '-'} 轮={turn} 摘要={summary} "
        f"窗口={len(ctx.layer2) + len(ctx.layer1)}条 估算={ctx.tokens}token",
        f"  [system] {_clip(ctx.system, 80)}",
    ]
    for row in ctx.layer2:
        lines.append(f"  [层2] {row.get('role')}: {row.get('content')}")
    for row in ctx.layer1:
        lines.append(f"  [层1] {row.get('role')}: {row.get('content')}")
    lines.append(f"  [当前] user: {ctx.current}")
    lines.append(f"  [梗概+证据] {ctx.combined or '(无)'}")
    lines.append("[ctx] end model_ctx")
    _write("\n".join(lines))


def log_budget(budget: Budget, turn_steady: int) -> None:
    _write(budget_line(budget))
    for line in self_check_lines(budget, turn_steady):
        _write(line)
```

> 说明:日志函数只按属性读取上下文对象(duck typing),因此本任务的测试用本地 `FakeHistory` / `FakeAgent`,不依赖 Task 5 的实现。

`tests/conftest.py` 追加一行,避免测试往仓库里写 `log/app.log`(stdout 照常输出):

```python
os.environ.setdefault("CTX_LOG_DISABLE", "1")
```

`test_context_log.py` 中需要落盘的两个用例用 `monkeypatch.setattr(context_log, "_DISABLE_FILE", False)` 打开文件写。

- [ ] **Step 4: 跑测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_context_log.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add potry-ai-agent/context_log.py potry-ai-agent/tests/test_context_log.py
git commit -m "feat(ch06): add model_ctx/history_ctx file logging"
```

---

### Task 5: 上下文拼装(固定顺序)

**Files:**
- Create: `potry-ai-agent/context_builder.py`
- Test: `potry-ai-agent/tests/test_context_builder.py`

- [ ] **Step 1: 写失败测试**

```python
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config import Settings
from context_budget import derive_budget
from context_builder import build_agent_context, build_history_context


def make_settings(**over):
    base = dict(
        llm_base_url="http://fake", llm_api_key="CONFIGURE_LOCALLY", llm_model="fake",
        history_max_tokens=2000, llm_temperature=0.7,
        mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
    )
    base.update(over)
    return Settings(**base)


class FakeStorage:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def load_context(self, session_id):
        return self.snapshot


class FakeDeps:
    def __init__(self, snapshot, settings=None):
        self.chat_storage = FakeStorage(snapshot)
        self.settings = settings or make_settings()
        self.budget = derive_budget(self.settings)


SNAPSHOT = {
    "conversationId": 1, "summaryUpto": 2, "layer1From": 4,
    "rows": [
        {"id": 1, "role": "user", "content": "问一"},
        {"id": 2, "role": "assistant", "content": "答一"},
        {"id": 3, "role": "user", "content": "问二"},
        {"id": 4, "role": "assistant", "content": "答二"},
        {"id": 5, "role": "user", "content": "问三"},
        {"id": 6, "role": "assistant", "content": "答三"},
    ],
    "summaries": [{"seq": 1, "uptoMsgId": 2, "content": "早期梗概正文"}],
}


def test_agent_context_order_and_no_summary_system():
    deps = FakeDeps(SNAPSHOT)
    state = {
        "session_id": "s1", "user_input": "问四", "turn_message_start": 0,
        "messages": [HumanMessage(content="问四")],
        "retrieved": [{"source_type": "poem", "title": "静夜思", "text": "床前明月光"}],
    }
    ctx = build_agent_context(state, deps)
    roles = [type(m).__name__ for m in ctx.messages]
    assert roles[0] == "SystemMessage" and roles.count("SystemMessage") == 1
    assert isinstance(ctx.messages[1], HumanMessage) and ctx.messages[1].content == "问二"
    assert isinstance(ctx.messages[2], AIMessage) and ctx.messages[2].content.startswith("答二")
    assert ctx.messages[3].content == "问三"
    assert ctx.messages[4].content == "答三"
    assert ctx.messages[5].content == "问四"                    # 当前句
    combined = ctx.messages[6]
    assert "【早期梗概】" in combined.content and "【检索资料】" in combined.content
    assert "床前明月光" in combined.content
    assert ctx.summary == "早期梗概正文"


def test_agent_context_ruling_evidence_is_one_message_after_question():
    deps = FakeDeps({**SNAPSHOT, "summaryUpto": 0, "summaries": []})
    state = {
        "session_id": "s1", "user_input": "这首合律吗", "turn_message_start": 0,
        "messages": [HumanMessage(content="这首合律吗")],
        "subflow_kind": "meter",
        "slot_target": {"title": "静夜思", "writer": "李白", "content": "床前明月光"},
        "policy_hits": [{"raw_text": "偶句押韵"}],
    }
    ctx = build_agent_context(state, deps)
    combined = ctx.messages[-1]
    assert isinstance(combined, HumanMessage)
    assert "【待判定的诗作" in combined.content and "偶句押韵" in combined.content
    assert combined.content.index("【待判定的诗作") < combined.content.index("【任务】")


def test_agent_context_appends_this_turn_react_messages():
    deps = FakeDeps({**SNAPSHOT, "rows": [], "summaryUpto": 0, "layer1From": 0, "summaries": []})
    state = {
        "session_id": "s1", "user_input": "问", "turn_message_start": 0,
        "messages": [HumanMessage(content="问"), AIMessage(content="", tool_calls=[{"id": "c1", "name": "x", "args": {}}])],
    }
    ctx = build_agent_context(state, deps)
    assert isinstance(ctx.messages[-1], AIMessage) and ctx.messages[-1].tool_calls


def test_history_context_is_summary_line_plus_window():
    deps = FakeDeps(SNAPSHOT)
    hc = build_history_context(SNAPSHOT, deps.settings)
    llm_rows = hc.for_llm()
    assert llm_rows[0] == {"role": "summary", "content": "早期梗概正文"}
    assert [r["role"] for r in llm_rows[1:]] == ["user", "assistant", "user", "assistant"]
    assert hc.tokens > 0


def test_history_context_trimmed_to_budget_keeps_latest_turn():
    snapshot = {"conversationId": 1, "summaryUpto": 0, "layer1From": 0,
                "rows": [
                    {"id": 1, "role": "user", "content": "旧" * 100},
                    {"id": 2, "role": "assistant", "content": "旧答" * 100},
                    {"id": 3, "role": "user", "content": "新问"},
                    {"id": 4, "role": "assistant", "content": "新答"},
                ], "summaries": []}
    settings = make_settings(history_ctx_max_tokens=30)
    hc = build_history_context(snapshot, settings)
    assert [r["id"] for r in hc.layer2 + hc.layer1] == [3, 4]
```

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_context_builder.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'context_builder'`

- [ ] **Step 3: 实现 `context_builder.py`**

```python
"""调模型的上下文拼装(spec §5):固定顺序,梗概绝不单独占 system。"""
from dataclasses import dataclass

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from context_budget import (
    estimate_message_tokens,
    estimate_messages_tokens,
    estimate_rows_tokens,
    estimate_tokens,
)
from context_layers import split_layers, truncate_layer2, turn_groups
from prompts import RULING_JUDGE_INSTRUCTION, SYSTEM_PROMPT_TEMPLATE


@dataclass
class HistoryContext:
    summary: str
    layer2: list[dict]
    layer1: list[dict]
    tokens: int

    def for_llm(self) -> list[dict]:
        rows = []
        if self.summary:
            rows.append({"role": "summary", "content": self.summary})
        rows += [{"role": r["role"], "content": r["content"]} for r in self.layer2 + self.layer1]
        return rows


@dataclass
class AgentContext:
    messages: list
    summary: str
    layer2: list[dict]
    layer1: list[dict]
    current: str
    evidence: str
    combined: str
    system: str
    tokens: int
    turn: int


def empty_snapshot() -> dict:
    return {"conversationId": None, "summaryUpto": 0, "layer1From": 0, "rows": [], "summaries": []}


def load_snapshot(deps, session_id: str) -> dict:
    if deps.chat_storage is None or not session_id:
        return empty_snapshot()
    try:
        return deps.chat_storage.load_context(session_id)
    except Exception as exc:  # noqa: BLE001 - 读历史失败按首轮处理,不阻断对话
        print(f"[ctx] load_context fail: {str(exc)[:200]}")
        return empty_snapshot()


def summary_text(snapshot: dict) -> str:
    parts = [
        (s.get("content") or "").strip()
        for s in snapshot.get("summaries") or []
        if (s.get("content") or "").strip()
    ]
    return "\n".join(parts)


def turn_number(snapshot: dict, state: dict) -> int:
    users = sum(1 for row in snapshot.get("rows") or [] if row.get("role") == "user")
    return users + (1 if (state.get("user_input") or "").strip() else 0)


def _trim_window(rows: list[dict], max_tokens: int) -> list[dict]:
    """从最旧处按完整轮次裁;至少保留最新一轮。"""
    if estimate_rows_tokens(rows) <= max_tokens:
        return rows
    kept_groups: list[list[dict]] = []
    total = 0
    for group in reversed(turn_groups(rows)):
        group_tokens = estimate_rows_tokens(group)
        if kept_groups and total + group_tokens > max_tokens:
            break
        kept_groups.insert(0, group)
        total += group_tokens
    return [row for group in kept_groups for row in group]


def build_history_context(snapshot: dict, settings) -> HistoryContext:
    """消解/意图共用:摘要一行 + 按 HISTORY_CTX_MAX_TOKENS 裁过的滑窗。"""
    layers = split_layers(snapshot.get("rows") or [], snapshot.get("summaryUpto", 0), snapshot.get("layer1From", 0))
    layer2 = truncate_layer2(
        layers.layer2, settings.layer2_assistant_prefix_chars, settings.layer2_blob_chars
    )
    summary = summary_text(snapshot)
    window = _trim_window(layer2 + layers.layer1, settings.history_ctx_max_tokens)
    layer2_ids = {row.get("id") for row in layer2}
    return HistoryContext(
        summary=summary,
        layer2=[row for row in window if row.get("id") in layer2_ids],
        layer1=[row for row in window if row.get("id") not in layer2_ids],
        tokens=estimate_rows_tokens(window) + estimate_tokens(summary),
    )


def _as_message(row: dict):
    if row.get("role") == "assistant":
        return AIMessage(content=row.get("content") or "")
    return HumanMessage(content=row.get("content") or "")


def _ruling_evidence(state: dict) -> str:
    target = state.get("slot_target") or {}
    lines = [
        "【待判定的诗作(权威数据)】",
        f"标题:{target.get('title') or '-'}",
        f"作者:{target.get('writer') or '-'}",
        f"朝代:{target.get('dynasty') or '-'}",
        f"体裁:{target.get('type') or '-'}",
        f"原文:{(target.get('content') or '').strip()}",
        f"译文:{(target.get('translation') or '').strip()}",
        "",
        "【适用规则条款】",
    ]
    hits = state.get("policy_hits") or []
    for hit in hits:
        clause = (hit.get("raw_text") or hit.get("chunk_text") or "").strip()
        if clause:
            lines.append(f"- {clause}")
    if not hits:
        lines.append("(未检索到相关规则条款:依据不足时请如实说明不确定)")
    lines += ["", RULING_JUDGE_INSTRUCTION]
    return "\n".join(lines)


def evidence_text(state: dict) -> str:
    """判定子流程 = 权威数据 + 条款;知识类 = 检索片段;其余为空。"""
    if state.get("subflow_kind"):
        return _ruling_evidence(state)
    retrieved = state.get("retrieved") or []
    if not retrieved:
        return ""
    lines = ["【检索资料】"]
    for hit in retrieved:
        lines.append(
            f"[{hit.get('source_type', '')}|{hit.get('title') or ''}] {hit.get('text') or ''}".strip()
        )
    return "\n".join(lines)


def _cap_layer2(layer2: list[dict], layer1: list[dict], history_budget: int) -> list[dict]:
    """摘要尚未完成时层 2 可能仍超预算:拼装时从最旧处临时不喂,数据仍留在库里等梗概。"""
    total = estimate_rows_tokens(layer2) + estimate_rows_tokens(layer1)
    capped = list(layer2)
    while capped and total > history_budget:
        groups = turn_groups(capped)
        if not groups:
            break
        dropped = groups[0]
        capped = capped[len(dropped):]
        total -= estimate_rows_tokens(dropped)
    return capped


def build_agent_context(state: dict, deps) -> AgentContext:
    """固定顺序:system → 层 2 → 层 1 → 当前句 → 梗概+证据 → 本轮 ReAct 消息。"""
    snapshot = load_snapshot(deps, state.get("session_id") or "")
    layers = split_layers(snapshot.get("rows") or [], snapshot.get("summaryUpto", 0), snapshot.get("layer1From", 0))
    layer2 = truncate_layer2(
        layers.layer2, deps.settings.layer2_assistant_prefix_chars, deps.settings.layer2_blob_chars
    )
    layer2 = _cap_layer2(layer2, layers.layer1, deps.budget.history)
    layer1 = layers.layer1
    summary = summary_text(snapshot)
    evidence = evidence_text(state)
    combined_parts = []
    if summary:
        combined_parts.append(f"【早期梗概】\n{summary}")
    if evidence:
        combined_parts.append(evidence)
    combined = "\n\n".join(combined_parts)
    current = (state.get("user_input") or "").strip() or (state.get("resolved_input") or "")
    system = SYSTEM_PROMPT_TEMPLATE.format()

    messages = [SystemMessage(content=system)]
    messages += [_as_message(row) for row in layer2]
    messages += [_as_message(row) for row in layer1]
    if current:
        messages.append(HumanMessage(content=current))
    if combined:
        messages.append(HumanMessage(content=combined))
    start = state.get("turn_message_start")
    if isinstance(start, int):
        messages += list(state.get("messages") or [])[start + 1:]
    return AgentContext(
        messages=messages, summary=summary, layer2=layer2, layer1=layer1,
        current=current, evidence=evidence, combined=combined, system=system,
        tokens=estimate_messages_tokens(messages), turn=turn_number(snapshot, state),
    )
```

- [ ] **Step 4: 跑测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_context_builder.py tests\test_context_log.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add potry-ai-agent/context_builder.py potry-ai-agent/context_log.py potry-ai-agent/tests/test_context_builder.py tests/test_context_log.py
git commit -m "feat(ch06): assemble model context in fixed order with summary and evidence"
```

---

### Task 6: 异步摘要任务与摘要 prompt

**Files:**
- Modify: `potry-ai-agent/prompts.py`
- Create: `potry-ai-agent/summarizer.py`
- Test: `potry-ai-agent/tests/test_summarizer.py`

- [ ] **Step 1: 写失败测试**

```python
import asyncio

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import summarizer
from config import Settings
from context_budget import derive_budget
from storage import ChatBase, ChatStorage


class FakeLLM:
    def __init__(self, reply="用户问过《静夜思》并核对作者,尚未确认朝代。", boom=False):
        self.reply = reply
        self.boom = boom
        self.prompts = []

    async def ainvoke(self, messages):
        self.prompts.append(messages)
        if self.boom:
            raise ConnectionError("upstream down")
        return AIMessage(content=self.reply)


class FakeDeps:
    def __init__(self, storage, llm, **over):
        base = dict(
            llm_base_url="http://fake", llm_api_key="CONFIGURE_LOCALLY", llm_model="fake",
            history_max_tokens=2000, llm_temperature=0.7,
            mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
        )
        base.update(over)
        self.settings = Settings(**base)
        self.chat_storage = storage
        self.llm = llm
        self.budget = derive_budget(self.settings)


def make_storage():
    engine = create_engine("sqlite:///:memory:")
    ChatBase.metadata.create_all(engine)
    return ChatStorage(sessionmaker(bind=engine))


def seed_two_turns(storage):
    storage.persist_turn("s1", "《静夜思》是谁写的", "是李白")
    storage.persist_turn("s1", "他是什么朝代的", "唐代")
    return storage.load_context("s1")


@pytest.fixture(autouse=True)
def _reset_state():
    summarizer.reset_for_tests()
    yield
    summarizer.reset_for_tests()


@pytest.mark.asyncio
async def test_summary_appends_paragraph_and_moves_anchor(capsys):
    storage = make_storage()
    seed_two_turns(storage)
    deps = FakeDeps(storage, FakeLLM())
    summarizer.schedule_summary(deps, "s1", 1, from_id=0, to_id=4, layer2_tokens=5000)
    await summarizer.wait_all()
    snapshot = storage.load_context("s1")
    assert snapshot["summaryUpto"] == 4
    assert snapshot["summaries"][0]["content"].startswith("用户问过")
    out = capsys.readouterr().out
    assert "summary trigger 会话=s1 层2 约 5000 token > 预算" in out
    assert "summary start 会话=s1 覆盖 1..4(4 条)" in out
    assert "summary done 会话=s1 第 1 段 覆盖到 4 耗时" in out


@pytest.mark.asyncio
async def test_summary_failure_keeps_anchor(capsys):
    storage = make_storage()
    seed_two_turns(storage)
    deps = FakeDeps(storage, FakeLLM(boom=True))
    summarizer.schedule_summary(deps, "s1", 1, from_id=0, to_id=4, layer2_tokens=5000)
    await summarizer.wait_all()
    snapshot = storage.load_context("s1")
    assert snapshot["summaryUpto"] == 0 and snapshot["summaries"] == []
    assert "summary fail 会话=s1" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_summary_skips_when_task_already_running(capsys):
    storage = make_storage()
    seed_two_turns(storage)
    deps = FakeDeps(storage, FakeLLM())
    lock = summarizer.lock_for("s1")
    await lock.acquire()
    try:
        summarizer.schedule_summary(deps, "s1", 1, from_id=0, to_id=4, layer2_tokens=5000)
        assert "summary skip 会话=s1(已有任务)" in capsys.readouterr().out
    finally:
        lock.release()
    await summarizer.wait_all()


@pytest.mark.asyncio
async def test_summary_skips_when_no_rows(capsys):
    storage = make_storage()
    storage.persist_turn("s1", "问", "答")
    deps = FakeDeps(storage, FakeLLM())
    summarizer.schedule_summary(deps, "s1", 1, from_id=0, to_id=0, layer2_tokens=5000)
    await summarizer.wait_all()
    assert "summary skip 会话=s1(无内容)" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_batch_cap_advances_only_to_compressed_position(capsys):
    storage = make_storage()
    for i in range(4):
        storage.persist_turn("s1", f"问题{i}" * 20, f"回答{i}" * 20)
    deps = FakeDeps(storage, FakeLLM(), summary_batch_max_tokens=60)
    summarizer.schedule_summary(deps, "s1", 1, from_id=0, to_id=8, layer2_tokens=5000)
    await summarizer.wait_all()
    snapshot = storage.load_context("s1")
    assert 0 < snapshot["summaryUpto"] < 8
    assert "summary done" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_schedule_returns_without_waiting_for_model():
    storage = make_storage()
    seed_two_turns(storage)

    class SlowLLM(FakeLLM):
        async def ainvoke(self, messages):
            await asyncio.sleep(0.2)
            return AIMessage(content="慢梗概")

    deps = FakeDeps(storage, SlowLLM())
    started = asyncio.get_event_loop().time()
    summarizer.schedule_summary(deps, "s1", 1, from_id=0, to_id=4, layer2_tokens=5000)
    elapsed = asyncio.get_event_loop().time() - started
    assert elapsed < 0.1                      # 投递即返回,不阻塞当前轮
    await summarizer.wait_all()
```

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_summarizer.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'summarizer'`

- [ ] **Step 3: 在 `prompts.py` 末尾追加摘要 prompt**

```python
# Ch06:会话梗概只提炼事实与诉求,对话里没有的一个字不许编
SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是会话摘要助手。把对话记录压缩成一段中文梗概,**只保留事实与诉求**:
1. 用户问过哪首诗 / 哪位诗人 / 哪句诗(诗题、作者、朝代);
2. 用户报过的线索:诗题、诗句片段、诗人名、判定结论;
3. 用户明确表达过的诉求(想找什么样的诗、想判合不合律、想核对作者/原文/朝代);
4. 还没解决的问题(尚未得到结论的判定、没找到的诗、待补充的线索)。

硬约束:
- 只写对话里确实出现过的内容,**一个字都不许编**(不得补全诗题、作者、朝代、结论);
- 寒暄、客套、感谢、重复表述一律不写;
- 长度 40–200 字;
- 只输出梗概正文,不要标题、不要解释。""",
        ),
        ("human", "对话记录:\n{history}"),
    ]
)
```

- [ ] **Step 4: 实现 `summarizer.py`**

```python
"""后台异步摘要(spec §7):层 2 超预算 → 整批压一段 → 追加摘要表并推进锚点。"""
import asyncio
import time

from context_budget import estimate_rows_tokens
from context_layers import turn_groups
from prompts import SUMMARY_PROMPT

_tasks: set[asyncio.Task] = set()
_locks: dict[str, asyncio.Lock] = {}

_ROLE_NAMES = {"user": "用户", "assistant": "青莲"}


def lock_for(session_id: str) -> asyncio.Lock:
    return _locks.setdefault(session_id, asyncio.Lock())


def reset_for_tests() -> None:
    _tasks.clear()
    _locks.clear()


def format_transcript(rows: list[dict]) -> str:
    return "\n".join(
        f"{_ROLE_NAMES.get(row.get('role'), row.get('role') or '-')}: {row.get('content') or ''}"
        for row in rows
    )


def schedule_summary(
    deps, session_id: str, conversation_id: int, from_id: int, to_id: int, layer2_tokens: int
) -> None:
    """投递后台任务后立即返回;同一会话已有任务在跑则跳过。"""
    print(
        f"summary trigger 会话={session_id} 层2 约 {layer2_tokens} token > 预算 {deps.budget.layer2}"
    )
    lock = lock_for(session_id)
    if lock.locked():
        print(f"summary skip 会话={session_id}(已有任务)")
        return
    task = asyncio.create_task(_run(deps, session_id, conversation_id, from_id, to_id, lock))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def _cap_batch(rows: list[dict], max_tokens: int) -> list[dict]:
    """超 SUMMARY_BATCH_MAX_TOKENS 时只取最旧的完整轮;至少压一轮。"""
    kept: list[dict] = []
    total = 0
    for group in turn_groups(rows):
        group_tokens = estimate_rows_tokens(group)
        if kept and total + group_tokens > max_tokens:
            break
        kept.extend(group)
        total += group_tokens
    return kept or turn_groups(rows)[0]


async def _run(deps, session_id: str, conversation_id: int, from_id: int, to_id: int, lock) -> None:
    async with lock:
        started = time.monotonic()
        try:
            snapshot = deps.chat_storage.load_context(session_id)
            rows = [
                row for row in snapshot.get("rows") or []
                if from_id < (row.get("id") or 0) <= to_id
            ]
            if not rows:
                print(f"summary skip 会话={session_id}(无内容)")
                return
            batch = _cap_batch(rows, deps.settings.summary_batch_max_tokens)
            upto = batch[-1]["id"]
            print(
                f"summary start 会话={session_id} 覆盖 {batch[0]['id']}..{upto}({len(batch)} 条)"
            )
            reply = await deps.llm.ainvoke(
                SUMMARY_PROMPT.invoke({"history": format_transcript(batch)})
            )
            content = (reply.content or "").strip()
            if not content:
                raise RuntimeError("空梗概")
            seq = deps.chat_storage.add_summary(conversation_id, content, upto)
            if seq is None:
                print(f"summary skip 会话={session_id}(已有同段)")
                return
            elapsed = int((time.monotonic() - started) * 1000)
            print(f"summary done 会话={session_id} 第 {seq} 段 覆盖到 {upto} 耗时 {elapsed}ms")
        except asyncio.CancelledError:
            print(f"summary skip 会话={session_id}(服务关闭)")
            raise
        except Exception as exc:  # noqa: BLE001 - 失败锚点不动,下一轮可重试
            print(f"summary fail 会话={session_id}: {str(exc)[:200]}")


async def wait_all() -> None:
    """测试用:等待当前所有摘要任务结束。"""
    tasks = list(_tasks)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def shutdown() -> None:
    for task in list(_tasks):
        task.cancel()
```

- [ ] **Step 5: 跑测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_summarizer.py -q`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add potry-ai-agent/prompts.py potry-ai-agent/summarizer.py potry-ai-agent/tests/test_summarizer.py
git commit -m "feat(ch06): add background async summarizer with batch cap and anchors"
```

---

### Task 7: State 换 `add_messages`、依赖装预算、resolve 追加用户消息

**Files:**
- Modify: `potry-ai-agent/workflow/state.py`
- Modify: `potry-ai-agent/workflow/deps.py`
- Modify: `potry-ai-agent/workflow/resolve.py`
- Modify: `potry-ai-agent/workflow/nodes.py`(`resolve_node`)
- Test: `potry-ai-agent/tests/test_workflow_nodes.py`、`tests/test_workflow_resolve.py`

- [ ] **Step 1: `workflow/state.py` 改为**

```python
"""Ch04–Ch06 编排状态:贯穿图全流程的 WorkflowState(TypedDict)。

`messages` 用 LangGraph 官方 `add_messages` reducer:节点只吐新增消息,框架按 id 并入;
完整历史(含 tool_calls / ToolMessage)由 checkpointer 落盘。调模型前另由
`context_builder` 现算精简版,两条路径互不影响。
"""
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages

# 每轮开始时必须归零的"本轮字段":State 经 checkpointer 跨轮持久化
PER_TURN_RESET = {
    "intent": "",
    "confidence": 0.0,
    "route": "",
    "retrieved": [],
    "evidence_score": None,
    "gate_status": "skip",
    "answer": "",
    "actions": [],
    "tool_trace": [],
    "iterations": 0,
    "tokens_used": 0,
    "fallback_reason": "",
    # ---------- Ch05 ----------
    "query_changed": False,
    "slot_target": None,
    "expanded_queries": [],
    "policy_hits": [],
    "correction_categories": [],
}


class WorkflowState(TypedDict, total=False):
    session_id: str
    userid: str | None            # Ch06:匿名用户标识(侧栏过滤)
    user_input: str
    selected_poem_id: int | None
    resolved_input: str
    intent: str
    confidence: float
    route: str
    retrieved: list[dict]
    evidence_score: float | None
    gate_status: str
    messages: Annotated[list, add_messages]   # 完整历史(累积)
    turn_message_start: int       # Ch06:本轮用户消息在 messages 中的下标
    tool_trace: list
    answer: str
    actions: list[str]
    iterations: int
    tokens_used: int
    fallback_reason: str
    started_at: float
    # ---------- Ch05 ----------
    query_changed: bool
    subflow_kind: str
    slot_target: dict | None
    candidates: list[dict]
    pending_subflow: bool
    expanded_queries: list[str]
    policy_hits: list[dict]
    correction_categories: list[str]
```

- [ ] **Step 2: `workflow/deps.py` 装预算**

```python
from context_budget import derive_budget


class WorkflowDeps:
    def __init__(self, settings, llm, registry, knowledge_storage, chat_storage) -> None:
        self.settings = settings
        self.llm = llm
        self.registry = registry
        self.knowledge_storage = knowledge_storage
        self.chat_storage = chat_storage
        self.budget = derive_budget(settings)          # Ch06:窗口倒推,单一来源
        self.max_iter = settings.max_agent_steps       # MAX_AGENT_STEPS 优先,未配置回退 WORKFLOW_MAX_ITER
        self.max_tokens = settings.workflow_max_tokens
```

- [ ] **Step 3: `workflow/resolve.py::format_history` 支持梗概行**

```python
_ROLE_NAMES = {"user": "用户", "assistant": "青莲"}


def format_history(history: list[dict]) -> str:
    """把历史渲染成「用户:/青莲:/【早期梗概】」纯文本,供 prompt 注入。"""
    lines = []
    for row in history or []:
        role = row.get("role")
        if role == "summary":
            lines.append(f"【早期梗概】{row.get('content') or ''}")
            continue
        lines.append(f"{_ROLE_NAMES.get(role, role or '-')}:{row.get('content') or ''}")
    return "\n".join(lines) if lines else "(无)"
```

- [ ] **Step 4: 重写 `nodes.py::resolve_node`(append 用户消息 + history_ctx)**

```python
async def resolve_node(state: dict) -> dict:
    """指代消解 + Query 改写:历史由 context_builder 现算;同时记录本轮 user 消息下标。"""
    deps = get_deps()
    session_id = state.get("session_id") or ""
    snapshot = load_snapshot(deps, session_id)
    history_ctx = build_history_context(snapshot, deps.settings)
    log_history_ctx(session_id, turn_number(snapshot, state), history_ctx)

    selected = state.get("selected_poem_id")
    resume = bool(selected) and bool(state.get("pending_subflow"))
    out: dict = {
        **PER_TURN_RESET,
        "resolved_input": state.get("resolved_input", ""),
        "selected_poem_id": selected if resume else None,
        "candidates": [],
        "pending_subflow": resume,
        "turn_message_start": len(state.get("messages") or []),
    }
    user_text = (state.get("user_input") or "").strip()
    if not resume and user_text:
        out["messages"] = [HumanMessage(content=user_text)]
    if resume:
        print("[wf] resolve resume=续跑(沿用上一轮消解结果)")
        return out
    resolved, changed = await resolve_input(deps.llm, user_text, history_ctx.for_llm())
    out["resolved_input"] = resolved
    out["query_changed"] = changed
    print(f"[wf] resolve changed={str(changed).lower()} query={resolved}")
    return out
```

`nodes.py` 顶部 import 增加:

```python
from langchain_core.messages import AIMessage, HumanMessage

from context_builder import build_history_context, load_snapshot, turn_number
from context_layers import downgrade_anchor, split_layers, truncate_layer2
from context_log import log_history_ctx
from summarizer import schedule_summary
```

删除 `from workflow.state import HISTORY_TURNS, PER_TURN_RESET` 中的 `HISTORY_TURNS`,改为:

```python
from workflow.state import PER_TURN_RESET
```

删除 `_next_history` 函数,`log_node` 暂时改为:

```python
async def log_node(state: dict) -> dict:
    """日志记录:结构化日志 + 落库(摘要/降级在 Task 9 接入)。"""
    elapsed = int((time.monotonic() - state.get("started_at", time.monotonic())) * 1000)
    print(
        f"[wf] intent={state.get('intent', '-')} conf={_fmt(state.get('confidence'), 2)} "
        f"route={state.get('route', '-')} gate={state.get('gate_status', 'skip')} "
        f"score={_fmt(state.get('evidence_score'), 4)} "
        f"iters={state.get('iterations', 0)} tokens={state.get('tokens_used', 0)} elapsed={elapsed}"
    )
    _persist_turn(state)
    return {}
```

并新增小工具:

```python
def _fmt(value, digits: int) -> str:
    return f"{value:.{digits}f}" if isinstance(value, (int, float)) else "-"
```

- [ ] **Step 5: 更新 `tests/test_workflow_nodes.py` 的 resolve 用例**

`test_resolve_node_passes_through_and_resets_turn_fields` 增加断言:

```python
    assert out["turn_message_start"] == 0
    assert [m.content for m in out["messages"]] == ["那首讲月亮的叫啥"]
```

`test_resolve_node_rewrites_with_history` 改为通过 FakeChatStorage 提供历史(`FakeChatStorage` 在 Task 11 完整升级;本任务先加 `load_context`):

```python
class FakeChatStorage:
    def __init__(self):
        self.turns = []
        self.rows = []
        self._id = 0

    def persist_turn(self, session_id, user_text, answer, userid=None):
        self.turns.append((session_id, user_text, answer))
        self._id += 1
        user_id = self._id
        self.rows.append({"id": user_id, "role": "user", "content": user_text})
        self._id += 1
        self.rows.append({"id": self._id, "role": "assistant", "content": answer})
        return 1, user_id, self._id

    def load_context(self, session_id):
        return {"conversationId": 1, "summaryUpto": 0, "layer1From": 0,
                "rows": list(self.rows), "summaries": []}

    def advance_layer1_anchor(self, conversation_id, msg_id):
        pass

    def add_summary(self, conversation_id, content, upto_msg_id):
        return None
```

用例:

```python
@pytest.mark.asyncio
async def test_resolve_node_rewrites_with_history(monkeypatch):
    import workflow.nodes as nodes_module

    async def fake_resolve(llm, question, history):
        return ("《静夜思》这首诗合不合律", True)

    monkeypatch.setattr(nodes_module, "resolve_input", fake_resolve)
    chat = FakeChatStorage()
    chat.persist_turn("s1", "《静夜思》是谁写的", "李白")
    _deps(chat=chat)
    out = await resolve_node({"session_id": "s1", "user_input": "它合不合律"})
    assert out["resolved_input"] == "《静夜思》这首诗合不合律"
    assert out["query_changed"] is True
    assert out["turn_message_start"] == 0
```

`test_resolve_node_resumes_without_calling_model` 的 state 增加 `"messages": []`,断言 `out.get("messages") is None`(续跑不追加)。

`test_log_node_prints_confidence_and_updates_history` / `test_log_node_replaces_last_answer_on_resume` 删除(history 通道已不存在),由 `test_context_builder.py` 与 Task 9 的日志节点用例替代。

- [ ] **Step 6: `tests/test_workflow_resolve.py` 增加**

```python
def test_format_history_renders_summary_line():
    text = format_history([{"role": "summary", "content": "问过《静夜思》"}])
    assert text == "【早期梗概】问过《静夜思》"
```

- [ ] **Step 7: 跑测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_workflow_nodes.py tests\test_workflow_resolve.py -q`
Expected: PASS;`test_workflow_graph.py` 暂红(Task 11 收口)

- [ ] **Step 8: 提交**

```bash
git add potry-ai-agent/workflow/state.py potry-ai-agent/workflow/deps.py potry-ai-agent/workflow/resolve.py potry-ai-agent/workflow/nodes.py potry-ai-agent/tests/test_workflow_nodes.py potry-ai-agent/tests/test_workflow_resolve.py
git commit -m "feat(ch06): switch state to add_messages and build resolve history from storage"
```

---

### Task 8: Agent 用精简上下文,替换 seed

**Files:**
- Modify: `potry-ai-agent/workflow/agent_react.py`
- Test: `potry-ai-agent/tests/test_workflow_agent_react.py`

- [ ] **Step 1: 改 `agent_react.py`**

删除 `_seed_messages` 与 `_ruling_seed`(逻辑已迁到 `context_builder._ruling_evidence`),`agent_node` 改为:

```python
async def agent_node(state: dict) -> dict:
    """主力 Agent:按固定顺序拼精简上下文后调 LLM,产出 tool_calls 或收敛答案。"""
    deps = get_deps()
    ctx = build_agent_context(state, deps)
    if state.get("iterations", 0) == 0:
        log_model_ctx(state.get("session_id") or "", ctx.turn, ctx)
    msgs = list(ctx.messages)
    iterations = state.get("iterations", 0) + 1
    try:
        ai = await deps.llm.bind_tools(deps.registry.get_tools()).ainvoke(msgs)
    except Exception as exc:  # noqa: BLE001 - 模型失败降级兜底,不阻断整图
        print(f"[wf] agent fail: {str(exc)[:200]}")
        return {"messages": [], "iterations": iterations,
                "answer": _AGENT_ERROR_REPLY, "fallback_reason": "agent_error"}
    msgs.append(ai)
    # WORKFLOW_MAX_TOKENS 只约束**本轮 ReAct 增量**(历史已由预算单独管),
    # 否则长历史一进上下文就超过 8000,任何工具轮都会被立刻强制收敛。
    start = state.get("turn_message_start")
    turn_msgs = list(state.get("messages") or [])[start + 1:] + [ai] if isinstance(start, int) else msgs
    tokens_used = count_tokens_approximately(turn_msgs)
    if ai.tool_calls and (iterations >= deps.max_iter or tokens_used >= deps.max_tokens):
        reason = "max_iter" if iterations >= deps.max_iter else "max_tokens"
        return {
            "messages": [],
            "iterations": iterations,
            "tokens_used": tokens_used,
            "answer": await _force_answer(deps, msgs[:-1]),
            "fallback_reason": reason,
        }
    out: dict = {"messages": [ai], "iterations": iterations, "tokens_used": tokens_used}
    if not ai.tool_calls:
        out["answer"] = ai.content or ""
    return out
```

顶部 import 改为:

```python
from langchain_core.messages import HumanMessage

from context_builder import build_agent_context
from context_log import log_model_ctx
from tools.registry import make_tool_message
from workflow.deps import get_deps
```

> 说明:`RULING_JUDGE_INSTRUCTION` 已迁到 `context_builder._ruling_evidence`,本文件删除其 import。

- [ ] **Step 2: 更新 `test_workflow_agent_react.py`**

`ScriptedLLM` 记录实际收到的消息:

```python
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.last_messages = []

    async def ainvoke(self, messages):
        self.calls += 1
        self.last_messages = list(messages)
        ...
```

`test_agent_converges_in_one_iteration_without_tools`:

```python
    llm = ScriptedLLM([AIMessage(content="《静夜思》写的是思乡")])
    _deps(llm, registry)
    out = await agent_node({"resolved_input": "《静夜思》表达了什么", "messages": [], "iterations": 0})
    assert out["answer"] == "《静夜思》写的是思乡"
    assert out["iterations"] == 1
    assert len(out["messages"]) == 1                # 只回吐本轮 AI,seed 不再进 state
    assert isinstance(out["messages"][0], AIMessage)
    assert isinstance(llm.last_messages[0], SystemMessage)
    assert llm.last_messages[-1].content == "《静夜思》表达了什么"
```

`test_agent_keeps_seed_when_retrieved_present` 改为断言模型输入:

```python
    llm = ScriptedLLM([AIMessage(content="答")])
    _deps(llm, registry)
    state = {
        "resolved_input": "这首诗什么意思", "messages": [], "iterations": 0,
        "retrieved": [{"source_type": "poem", "title": "静夜思", "text": "床前明月光", "score": 0.9, "id": 1}],
    }
    await agent_node(state)
    combined = llm.last_messages[-1]
    assert "床前明月光" in combined.content and "【检索资料】" in combined.content
```

`test_agent_force_converges_at_iteration_limit`:

```python
    assert out["messages"] == []
    assert out["answer"] == "强制作答"
```

`test_agent_degrades_when_model_fails` 增加:

```python
    assert out["messages"] == []
```

- [ ] **Step 3: 跑测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_workflow_agent_react.py -q`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add potry-ai-agent/workflow/agent_react.py potry-ai-agent/tests/test_workflow_agent_react.py
git commit -m "feat(ch06): feed agent the trimmed context instead of seeding state"
```

---

### Task 9: 日志节点接降级与摘要触发

**Files:**
- Modify: `potry-ai-agent/workflow/nodes.py`
- Test: `potry-ai-agent/tests/test_workflow_nodes.py`

- [ ] **Step 1: 写失败测试(追加到 `test_workflow_nodes.py`)**

```python
class AnchoredFakeStorage:
    """可配置锚点/消息的假存储,专门验证降级与摘要触发。"""

    def __init__(self, rows, summary_upto=0, layer1_from=0):
        self.rows = rows
        self.summary_upto = summary_upto
        self.layer1_from = layer1_from
        self.summaries = []
        self.advanced = []

    def persist_turn(self, session_id, user_text, answer, userid=None):
        return 1, 100, 101

    def load_context(self, session_id):
        return {"conversationId": 1, "summaryUpto": self.summary_upto,
                "layer1From": self.layer1_from, "rows": list(self.rows),
                "summaries": list(self.summaries)}

    def advance_layer1_anchor(self, conversation_id, msg_id):
        self.advanced.append(msg_id)
        self.layer1_from = msg_id

    def add_summary(self, conversation_id, content, upto_msg_id):
        self.summaries.append({"seq": len(self.summaries) + 1, "uptoMsgId": upto_msg_id, "content": content})
        self.summary_upto = upto_msg_id
        return len(self.summaries)


@pytest.mark.asyncio
async def test_log_node_downgrades_layer1_when_over_budget(capsys, monkeypatch):
    import workflow.nodes as nodes_module

    monkeypatch.setattr(nodes_module, "schedule_summary", lambda *a, **k: None)
    rows = [
        {"id": 1, "role": "user", "content": "问" * 100},
        {"id": 2, "role": "assistant", "content": "答" * 100},
        {"id": 3, "role": "user", "content": "问" * 100},
        {"id": 4, "role": "assistant", "content": "答" * 100},
    ]
    chat = AnchoredFakeStorage(rows)
    _deps(chat=chat, keep_turns=1, turn_steady_tokens=50)
    await log_node({"session_id": "s1", "user_input": "x", "answer": "y"})
    assert chat.advanced                                  # 至少前移一次
    assert "layer1 降级 0→" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_log_node_skips_summary_when_layer2_within_budget(capsys, monkeypatch):
    import workflow.nodes as nodes_module

    monkeypatch.setattr(nodes_module, "schedule_summary", lambda *a, **k: None)
    rows = [{"id": i, "role": "user" if i % 2 else "assistant", "content": "短"} for i in range(1, 5)]
    chat = AnchoredFakeStorage(rows, summary_upto=0, layer1_from=2)
    _deps(chat=chat)
    await log_node({"session_id": "s1", "user_input": "x", "answer": "y"})
    assert "summary trigger" not in capsys.readouterr().out


@pytest.mark.asyncio
async def test_log_node_triggers_summary_when_layer2_over_budget(capsys, monkeypatch):
    import workflow.nodes as nodes_module

    called = {}
    monkeypatch.setattr(
        nodes_module, "schedule_summary",
        lambda deps, sid, cid, from_id, to_id, layer2_tokens: called.update(
            sid=sid, from_id=from_id, to_id=to_id, tokens=layer2_tokens
        ),
    )
    rows = [
        {"id": 1, "role": "user", "content": "问" * 300},
        {"id": 2, "role": "assistant", "content": "答" * 300},
    ]
    chat = AnchoredFakeStorage(rows, summary_upto=0, layer1_from=2)
    _deps(chat=chat, keep_turns=1, turn_steady_tokens=50)
    await log_node({"session_id": "s1", "user_input": "x", "answer": "y"})
    out = capsys.readouterr().out
    assert "summary trigger 会话=s1 层2 约" in out and "> 预算" in out
    assert called == {"sid": "s1", "from_id": 0, "to_id": 2, "tokens": called["tokens"]}
    assert called["tokens"] > 0
```

> 上述用例只验证“降级/投递”与日志;真正的摘要执行在 `test_summarizer.py` 覆盖。

- [ ] **Step 2: 实现 `log_node` 与降级/触发**

```python
async def log_node(state: dict) -> dict:
    """日志记录:补 AI 消息、两段式落库、层 1 降级、层 2 超预算投递摘要。"""
    elapsed = int((time.monotonic() - state.get("started_at", time.monotonic())) * 1000)
    print(
        f"[wf] intent={state.get('intent', '-')} conf={_fmt(state.get('confidence'), 2)} "
        f"route={state.get('route', '-')} gate={state.get('gate_status', 'skip')} "
        f"score={_fmt(state.get('evidence_score'), 4)} "
        f"iters={state.get('iterations', 0)} tokens={state.get('tokens_used', 0)} elapsed={elapsed}"
    )
    out: dict = {}
    answer = state.get("answer", "")
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if not (
        isinstance(last, AIMessage)
        and not getattr(last, "tool_calls", None)
        and (last.content or "") == answer
    ):
        out["messages"] = [AIMessage(content=answer)]
    ids = _persist_turn(state)
    if ids is not None:
        _after_persist(state, ids)
    return out


def _after_persist(state: dict, ids: tuple[int, int | None, int]) -> None:
    """锚点推进只在落库后做:层 1 超预算只挪 layer1_from;层 2 超预算投递后台摘要。"""
    deps = get_deps()
    storage = deps.chat_storage
    session_id = state.get("session_id") or ""
    conversation_id = ids[0]
    snapshot = storage.load_context(session_id)
    layers = split_layers(snapshot["rows"], snapshot["summaryUpto"], snapshot["layer1From"])
    if estimate_rows_tokens(layers.layer1) > deps.budget.layer1:
        new_anchor = downgrade_anchor(layers.layer1, deps.budget.layer1)
        if new_anchor:
            old_anchor = snapshot["layer1From"]
            storage.advance_layer1_anchor(conversation_id, new_anchor)
            print(f"[ctx] layer1 降级 {old_anchor}→{new_anchor}")
            snapshot = storage.load_context(session_id)
            layers = split_layers(snapshot["rows"], snapshot["summaryUpto"], snapshot["layer1From"])
    layer2 = truncate_layer2(
        layers.layer2, deps.settings.layer2_assistant_prefix_chars, deps.settings.layer2_blob_chars
    )
    layer2_tokens = estimate_rows_tokens(layer2)
    if layer2_tokens > deps.budget.layer2:
        schedule_summary(
            deps, session_id, conversation_id,
            from_id=snapshot["summaryUpto"], to_id=snapshot["layer1From"],
            layer2_tokens=layer2_tokens,
        )
```

`nodes.py` 还需 import `estimate_rows_tokens`(来自 `context_budget`)。

> 关键点:`log_node` 必须是 `async def`,否则 `asyncio.create_task` 没有运行中的事件循环。图对 async 节点原生支持。

- [ ] **Step 3: 更新既有节点测试为 `await log_node(...)`**

`test_log_node_prints_structured_line_and_persists`、`test_log_node_prints_score_when_retrieval_happened`、`test_log_node_survives_storage_failure`、`test_log_node_skips_user_row_on_resume` 中所有 `log_node(` 前加 `await`,并给测试函数加 `@pytest.mark.asyncio`;断言改为:

```python
    session_id, user_text, answer = chat.turns[0]
    assert session_id == "s1"
    assert user_text == "《静夜思》是谁写的"
    assert answer == "是李白"
```

以及:

```python
    _, user_text, _ = chat.turns[0]
    assert user_text == ""                 # 续跑轮不写空 user 行(由 storage 判空)
```

- [ ] **Step 4: 跑测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_workflow_nodes.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add potry-ai-agent/workflow/nodes.py potry-ai-agent/tests/test_workflow_nodes.py
git commit -m "feat(ch06): degrade layer1 and schedule background summary from log node"
```

---

### Task 10: 启动装配、两个只读接口

**Files:**
- Modify: `potry-ai-agent/main.py`
- Test: `potry-ai-agent/tests/test_conversations_api.py`

- [ ] **Step 1: 写失败测试**

```python
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main
from storage import ChatBase, ChatStorage


def _storage(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'chat.db'}")
    ChatBase.metadata.create_all(engine)
    return ChatStorage(sessionmaker(bind=engine))


def _client(monkeypatch, storage):
    monkeypatch.setattr(main, "storage", storage)
    return TestClient(main.app)


def test_list_conversations_filters_by_user_and_orders_desc(tmp_path, monkeypatch):
    st = _storage(tmp_path)
    st.persist_turn("old", "《静夜思》是谁写的", "李白", userid="u1")
    st.persist_turn("new", "找一首写月亮的诗", "《静夜思》", userid="u1")
    st.persist_turn("other", "别人的会话", "答", userid="u2")
    st.add_summary(1, "梗概", upto_msg_id=2)
    client = _client(monkeypatch, st)
    resp = client.get("/api/conversations", params={"userId": "u1"})
    assert resp.status_code == 200
    data = resp.json()
    assert [c["sessionId"] for c in data] == ["new", "old"]
    assert data[0]["preview"] == "找一首写月亮的诗"
    assert data[1]["summarized"] is True


def test_list_conversations_without_user_returns_all(tmp_path, monkeypatch):
    st = _storage(tmp_path)
    st.persist_turn("a", "问", "答", userid="u1")
    st.persist_turn("b", "问", "答", userid="u2")
    client = _client(monkeypatch, st)
    assert len(client.get("/api/conversations").json()) == 2


def test_messages_endpoint_returns_user_and_assistant_only(tmp_path, monkeypatch):
    st = _storage(tmp_path)
    st.persist_turn("s1", "问", "答", userid="u1")
    client = _client(monkeypatch, st)
    resp = client.get("/api/conversations/s1/messages", params={"userId": "u1"})
    assert resp.status_code == 200
    assert [r["role"] for r in resp.json()] == ["user", "assistant"]


def test_messages_endpoint_404_on_user_mismatch(tmp_path, monkeypatch):
    st = _storage(tmp_path)
    st.persist_turn("s1", "问", "答", userid="u1")
    client = _client(monkeypatch, st)
    assert client.get("/api/conversations/s1/messages", params={"userId": "u2"}).status_code == 404


def test_messages_endpoint_404_on_missing(tmp_path, monkeypatch):
    client = _client(monkeypatch, _storage(tmp_path))
    assert client.get("/api/conversations/nope/messages").status_code == 404


def test_list_conversations_500_on_storage_error(monkeypatch):
    class Boom:
        def list_conversations(self, userid=None):
            raise RuntimeError("mysql down")

    monkeypatch.setattr(main, "storage", Boom())
    resp = TestClient(main.app).get("/api/conversations")
    assert resp.status_code == 500
```

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_conversations_api.py -q`
Expected: FAIL — 404(路由不存在)

- [ ] **Step 3: 改 `main.py`**

顶部 import:

```python
from context_log import log_budget
from storage import ChatBase, ChatStorage, ensure_schema
from summarizer import shutdown as shutdown_summaries
```

`lifespan` 启动段,在 `init_db(engine)` 之后:

```python
    ensure_schema(engine)
```

关闭段追加:

```python
    shutdown_summaries()
    print("[summary] 后台摘要任务已取消")
```

模块级装配改为保留 deps 引用:

```python
workflow_deps = WorkflowDeps(settings, workflow_llm, workflow_registry, knowledge_storage, storage)
configure_workflow(workflow_deps)
```

`lifespan` 启动段打印预算自检:

```python
    log_budget(workflow_deps.budget, settings.turn_steady_tokens)
```

`/agent/workflow` 的输入增加 `"userid": req.userId`:

```python
            final = await _workflow.ainvoke(
                {
                    "session_id": session_id,
                    "userid": req.userId,
                    "user_input": req.message,
                    ...
                },
```

新增两个只读接口(放在 `/agent/workflow` 之前):

```python
@app.get("/api/conversations")
def list_conversations(userId: str | None = None) -> list[dict]:
    """会话侧栏:按 userId 过滤、新在前、首问预览、已摘要标记(只读)。"""
    try:
        return storage.list_conversations(userId)
    except Exception as exc:  # noqa: BLE001 - 查询失败让前端静默降级
        raise HTTPException(status_code=500, detail={"message": str(exc)[:200]})


@app.get("/api/conversations/{session_id}/messages")
def conversation_messages(session_id: str, userId: str | None = None) -> list[dict]:
    """切回旧会话时回载原文;只返回 user/assistant,userId 不匹配视同不存在。"""
    try:
        rows = storage.load_conversation_messages(session_id, userId)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"message": str(exc)[:200]})
    if rows is None:
        raise HTTPException(status_code=404, detail={"message": "会话不存在"})
    return rows
```

`ChatRequest` 已有 `userId`,无需改动;注释补一句 Ch06 用途。

- [ ] **Step 4: 跑测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_conversations_api.py tests\test_workflow_endpoint.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add potry-ai-agent/main.py potry-ai-agent/tests/test_conversations_api.py
git commit -m "feat(ch06): expose read-only conversation APIs and startup budget/migration"
```

---

### Task 11: 既有图测试收口(历史来源改为存储)

**Files:**
- Modify: `potry-ai-agent/tests/test_workflow_graph.py`

- [ ] **Step 1: 升级 `ScriptedLLM` 记录输入,升级 `FakeChatStorage`**

```python
class ScriptedLLM:
    def __init__(self, script=None, default="默认收敛"):
        self.script = list(script or [])
        self.default = default
        self.calls = []                     # 每次 ainvoke 收到的消息

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        if self.script:
            return self.script.pop(0)
        return AIMessage(content=self.default)


class FakeChatStorage:
    def __init__(self):
        self.turns = []
        self.rows = []
        self._id = 0
        self.summary_upto = 0
        self.layer1_from = 0

    def persist_turn(self, session_id, user_text, answer, userid=None):
        self.turns.append((session_id, user_text, answer))
        user_id = None
        if (user_text or "").strip():
            self._id += 1
            user_id = self._id
            self.rows.append({"id": user_id, "role": "user", "content": user_text})
        self._id += 1
        self.rows.append({"id": self._id, "role": "assistant", "content": answer})
        return 1, user_id, self._id

    def load_context(self, session_id):
        return {"conversationId": 1, "summaryUpto": self.summary_upto,
                "layer1From": self.layer1_from, "rows": list(self.rows), "summaries": []}

    def advance_layer1_anchor(self, conversation_id, msg_id):
        self.layer1_from = msg_id

    def add_summary(self, conversation_id, content, upto_msg_id):
        return None
```

- [ ] **Step 2: 把「注入证据」的两条断言从 state 改为模型输入**

`test_knowledge_evidence_injected_on_second_turn`:

```python
    final = await _run(graph, "《静夜思》表达了什么感情", session_id="rag2")
    assert final["gate_status"] == "pass"
    injected = [
        m for m in llm.calls[-1]
        if isinstance(m, HumanMessage) and "床前明月光" in m.content
    ]
    assert injected, "第二轮知识类必须把检索片段注入模型输入"
```

`test_ruling_resume_after_card_pick_judges`:

```python
    injected = [m for m in llm.calls[-1]
                if isinstance(m, HumanMessage) and "床前明月光" in m.content]
    assert injected, "判定子流程必须把诗作权威数据注入模型输入"
```

`test_checkpointer_persists_state_across_turns` 仍检查 `state.values["user_input"]` / `route`,无需改。

`_run` 保持每轮 `"messages": []`(add_messages 下无副作用)。

- [ ] **Step 3: 跑全量**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: 全部 PASS(此时代码与测试契约已对齐)

> 若仍有红灯,按“实现错误 / 测试断言过时”二分处理:实现错误改实现;仅因 `history` 通道消失或四段式落库而失败的断言改成新契约。不得删测试凑数。

- [ ] **Step 4: 提交**

```bash
git add potry-ai-agent/tests/test_workflow_graph.py
git commit -m "test(ch06): assert agent context instead of state seed injection"
```

---

### Task 12: 前端多会话侧栏

**Files:**
- Modify: `potry-ai-agent/static/chat.html`

- [ ] **Step 1: 调整布局与样式**

在 `<style>` 末尾追加:

```css
  #app { display: flex; flex: 1; min-height: 0; }
  #main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  #sidebar {
    width: 240px; flex: 0 0 240px; display: flex; flex-direction: column;
    border-right: 1px solid var(--line); background: rgba(243, 236, 223, .72);
  }
  .side-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 14px 12px; border-bottom: 1px solid var(--line);
  }
  .side-head span { font-size: 14px; letter-spacing: 4px; color: var(--ink-soft); }
  #newChat {
    padding: 6px 12px; font-size: 12px; letter-spacing: 2px;
    border: 1px solid var(--gold); background: transparent; color: var(--gold);
    border-radius: 8px;
  }
  .conv-list { flex: 1; overflow-y: auto; padding: 8px; }
  .conv-item {
    padding: 9px 10px; border-radius: 8px; cursor: pointer;
    border-left: 2px solid transparent; margin-bottom: 4px;
  }
  .conv-item:hover { background: rgba(217, 185, 120, .12); }
  .conv-item.active { border-left-color: var(--gold); background: rgba(217, 185, 120, .16); }
  .conv-preview {
    font-size: 13px; line-height: 1.6; color: var(--ink);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .conv-meta {
    display: flex; justify-content: space-between; align-items: center;
    margin-top: 3px; font-size: 11px; color: var(--ink-soft);
  }
  .conv-tag {
    padding: 1px 6px; border: 1px solid var(--gold-soft); border-radius: 4px;
    color: var(--gold); letter-spacing: 1px;
  }
  .conv-empty { padding: 18px 10px; font-size: 12px; color: var(--ink-soft); text-align: center; }
  .side-toggle {
    display: none; position: absolute; left: 12px; top: 16px;
    padding: 4px 10px; background: transparent; color: var(--ink-soft); font-size: 16px;
  }
  header { position: relative; }
  @media (max-width: 900px) {
    #sidebar { position: absolute; z-index: 5; height: 100%; left: 0; top: 0; background: var(--paper); }
    #sidebar.hidden { display: none; }
    .side-toggle { display: inline-block; }
  }
```

把 `<body>` 内部整体改为:

```html
<div id="app">
  <aside id="sidebar">
    <div class="side-head"><span>对话</span><button id="newChat">新对话</button></div>
    <div id="convList" class="conv-list"><div class="conv-empty">载入中…</div></div>
  </aside>
  <main id="main">
    <header>
      <button id="toggleSidebar" class="side-toggle">☰</button>
      <h1><span class="seal">青</span>莲伴读</h1>
      <p>以诗人之眼 · 陪你读千年诗心</p>
    </header>
    <div id="messages">
      <div class="row assistant">
        <div><div class="who">青莲</div><div class="bubble">你好,我是青莲。想读哪首诗,或聊哪句词,我都在。</div></div>
      </div>
    </div>
    <footer>
      <div class="composer">
        <textarea id="input" rows="1" placeholder="问我一首诗,或说说你最近读到的句子……"></textarea>
        <button id="send">寄 出</button>
      </div>
      <div class="hint">Enter 发送 · Shift+Enter 换行 · 对话按会话续接</div>
    </footer>
  </main>
</div>
```

把 `body` 原 `display:flex; flex-direction:column;` 改为 `display:flex;` 即可。

- [ ] **Step 2: 增加 JS:匿名 userId、侧栏、切换、新对话**

在 `<script>` 顶部追加:

```js
  const GREETING = "你好,我是青莲。想读哪首诗,或聊哪句词,我都在。";
  const userId = (() => {
    let value = localStorage.getItem("poetryUserId");
    if (!value) {
      value = crypto.randomUUID();
      localStorage.setItem("poetryUserId", value);
    }
    return value;
  })();
  let sessionId = crypto.randomUUID().replace(/-/g, "");
  let conversations = [];
  let switching = false;
  const sidebarEl = document.getElementById("sidebar");
  const convListEl = document.getElementById("convList");
```

并替换原 `let sessionId = null;`(避免重复声明)。

新增函数:

```js
  function escapeHtml(text) {
    return String(text || "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function renderConversations() {
    convListEl.innerHTML = "";
    if (!conversations.length) {
      convListEl.innerHTML = '<div class="conv-empty">还没有对话</div>';
      return;
    }
    conversations.forEach((conv) => {
      const item = document.createElement("div");
      item.className = "conv-item" + (conv.sessionId === sessionId ? " active" : "");
      item.innerHTML =
        '<div class="conv-preview">' + escapeHtml(conv.preview || "新对话") + "</div>" +
        '<div class="conv-meta"><span>' + escapeHtml(conv.updatedAt || "") + "</span>" +
        (conv.summarized ? '<span class="conv-tag">已摘要</span>' : "") + "</div>";
      item.addEventListener("click", () => switchConversation(conv.sessionId));
      convListEl.appendChild(item);
    });
  }

  async function loadConversations() {
    try {
      const resp = await fetch("/api/conversations?userId=" + encodeURIComponent(userId));
      if (!resp.ok) throw new Error("status " + resp.status);
      conversations = await resp.json();
      renderConversations();
    } catch (e) {
      console.warn("会话侧栏加载失败,静默降级:", e.message);
      if (convListEl.querySelector(".conv-empty")) convListEl.innerHTML = "";
    }
  }

  async function switchConversation(id) {
    if (sending || switching || id === sessionId) return;
    switching = true;
    try {
      const resp = await fetch(
        "/api/conversations/" + encodeURIComponent(id) + "/messages?userId=" + encodeURIComponent(userId)
      );
      if (!resp.ok) throw new Error("status " + resp.status);
      const rows = await resp.json();
      sessionId = id;
      lastTrace = null;
      messagesEl.innerHTML = "";
      if (!rows.length) addRow("assistant", GREETING);
      rows.forEach((row) => addRow(row.role, row.content));
      renderConversations();
    } catch (e) {
      console.warn("会话回载失败,保持当前会话:", e.message);
    } finally {
      switching = false;
    }
  }

  function newConversation() {
    if (sending) return;
    sessionId = crypto.randomUUID().replace(/-/g, "");
    lastTrace = null;
    messagesEl.innerHTML = "";
    addRow("assistant", GREETING);
    conversations.unshift({ sessionId, preview: "新对话", updatedAt: "", summarized: false });
    renderConversations();
    inputEl.focus();
  }
```

绑定事件:

```js
  document.getElementById("newChat").addEventListener("click", newConversation);
  document.getElementById("toggleSidebar").addEventListener("click", () => {
    sidebarEl.classList.toggle("hidden");
  });
```

「发送中禁止切换」由 `switchConversation` 的 `sending` 守卫实现。

- [ ] **Step 3: 请求携带 userId,发送后刷新侧栏**

`streamReply`:

```js
    const body = Object.assign({ sessionId: sessionId, userId: userId, message: userText }, extra || {});
```

`send` 的 `finally` 改为:

```js
    } finally {
      sending = false;
      sendBtn.disabled = false;
      inputEl.focus();
      loadConversations();
    }
```

`pickPoem` 的 `finally` 同样追加 `loadConversations();`。

页面初始化(脚本末尾):

```js
  loadConversations();
```

- [ ] **Step 4: 前端人工验证**

1. 启动 API(见 Task 14 命令),浏览器打开 `http://127.0.0.1:8000/chat`;
2. 发两轮后点「新对话」,再发一轮;侧栏出现两个会话(新在前、首问预览);
3. 点击旧会话 → 消息区完整回载 user/assistant 原文 → 继续提问可正常回答;
4. 缩窄窗口到 <900px → 页头 ☰ 可收起侧栏;
5. 断网/停后端刷新 → 侧栏 `console.warn`,输入框仍可发送(发送时按后端错误提示)。

- [ ] **Step 5: 提交**

```bash
git add potry-ai-agent/static/chat.html
git commit -m "feat(ch06): add multi-conversation sidebar with history reload"
```

---

### Task 13: 摘要质量评估集(纯 Prompt 任务,替代 TDD)

**Files:**
- Create: `potry-ai-agent/eval_summary.py`

- [ ] **Step 1: 写评估脚本**

```python
"""Ch06 摘要质量评估集:真实模型跑批,断言事实保留 / 不编造 / 长度 / 去寒暄。

纯 Prompt 任务按用户工作要求用**标注样例替代 TDD**(见 dev-notes/ch06.md)。
用法(在 potry-ai-agent 下执行,需 .env 可用):
    .\.venv\Scripts\python.exe eval_summary.py
"""
import asyncio

from chat_service import build_llm
from config import load_settings
from prompts import SUMMARY_PROMPT
from summarizer import format_transcript

# (名称, 对话行, 必须出现的关键词, 不得出现的编造词)
SAMPLES = [
    ("核对静夜思作者",
     [("user", "《静夜思》是谁写的"), ("assistant", "《静夜思》是李白写的。"),
      ("user", "李白是什么朝代的"), ("assistant", "李白是唐代诗人。")],
     ["静夜思", "李白"], ["杜甫", "王维"]),
    ("找写月亮的诗",
     [("user", "帮我找一首写月亮的诗"), ("assistant", "可以看《静夜思》。"),
      ("user", "还有别的吗"), ("assistant", "《水调歌头》也写月。")],
     ["月亮", "静夜思"], ["李清照", "王之涣"]),
    ("判定七律",
     [("user", "《春望》是不是五律"), ("assistant", "《春望》是五言律诗。"),
      ("user", "那它对仗吗"), ("assistant", "中间两联对仗。")],
     ["春望", "五律"], ["七律", "苏轼"]),
    ("核对作者",
     [("user", "《登鹳雀楼》作者是谁"), ("assistant", "王之涣。"),
      ("user", "朝代呢"), ("assistant", "唐代。")],
     ["登鹳雀楼", "王之涣"], ["李白", "杜甫"]),
    ("报诗句问出处",
     [("user", "床前明月光出自哪首"), ("assistant", "出自《静夜思》。"),
      ("user", "谁写的"), ("assistant", "李白。")],
     ["床前明月光", "静夜思"], ["杜甫", "白居易"]),
    ("校勘原文",
     [("user", "《声声慢》原文有没有讹字"), ("assistant", "我核对了首句,暂未发现讹字。"),
      ("user", "作者是谁"), ("assistant", "李清照。")],
     ["声声慢", "李清照"], ["苏轼", "柳永"]),
    ("未解决线索",
     [("user", "我记得有句写孤舟的,想不起来哪首"), ("assistant", "能再给一个字或作者吗"),
      ("user", "好像是柳宗元的"), ("assistant", "那可能是《江雪》。")],
     ["孤舟", "柳宗元"], ["李白", "王维"]),
    ("寒暄要剔除",
     [("user", "你好呀"), ("assistant", "你好,想读哪首诗?"),
      ("user", "谢谢,我想问《静夜思》"), ("assistant", "《静夜思》写思乡。")],
     ["静夜思"], ["杜甫", "王维"]),
    ("明确诉求",
     [("user", "我想找一首写思乡的五言诗"), ("assistant", "可以先看《静夜思》。"),
      ("user", "要短一点的"), ("assistant", "《静夜思》四句,很短。")],
     ["思乡", "静夜思"], ["七律", "苏轼"]),
    ("诗人风格",
     [("user", "王维是什么风格"), ("assistant", "王维诗中有画,清幽淡远。"),
      ("user", "推荐一首"), ("assistant", "《山居秋暝》。")],
     ["王维", "山居秋暝"], ["杜甫", "李清照"]),
]

_GREETINGS = ("你好", "谢谢", "请问", "好的", "不客气")


def check(sample, content):
    name, rows, keywords, forbidden = sample
    problems = []
    for keyword in keywords:
        if keyword not in content:
            problems.append(f"缺事实:{keyword}")
    for word in forbidden:
        if word in content:
            problems.append(f"编造:{word}")
    if not (40 <= len(content) <= 200):
        problems.append(f"长度越界:{len(content)}")
    for greeting in _GREETINGS:
        if greeting in content:
            problems.append(f"残留寒暄:{greeting}")
    return problems


async def main() -> None:
    settings = load_settings()
    llm = build_llm(settings)
    passed = 0
    for sample in SAMPLES:
        rows = [{"role": role, "content": text} for role, text in sample[1]]
        reply = await llm.ainvoke(SUMMARY_PROMPT.invoke({"history": format_transcript(rows)}))
        content = (reply.content or "").strip()
        problems = check(sample, content)
        status = "PASS" if not problems else "FAIL"
        if not problems:
            passed += 1
        print(f"[eval] {status} {sample[0]} len={len(content)} :: {content}")
        for problem in problems:
            print(f"        - {problem}")
    total = len(SAMPLES)
    print(f"[eval] 摘要通过 {passed}/{total}({passed / total:.0%})")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 真实模型跑批**

Run: `.\.venv\Scripts\python.exe eval_summary.py`
Expected: `[eval] 摘要通过 10/10(100%)`。若个别样例因长度/寒暄不达标,调整 `SUMMARY_PROMPT`(不改断言),重跑至 ≥9/10,并把结果记入 dev-notes。

- [ ] **Step 3: 提交**

```bash
git add potry-ai-agent/eval_summary.py
git commit -m "test(ch06): add summary quality evaluation set"
```

---

### Task 14: 演示脚本与五条验收真跑

**Files:**
- Create: `potry-ai-agent/evals/demo_ch06.py`
- Modify: `dev-notes/ch06.md`

- [ ] **Step 1: 写多轮演示脚本**

```python
"""Ch06 多轮演示/验收:连续对话、触发降级与摘要、最后追问早期事实。

用法(API 已启动):
    .\.venv\Scripts\python.exe evals\demo_ch06.py --turns 20
    .\.venv\Scripts\python.exe evals\demo_ch06.py --turns 22 --recall
"""
import argparse
import asyncio
import json
import uuid

import httpx

BASE = "http://127.0.0.1:8000"

QUESTIONS = [
    "《静夜思》是谁写的", "李白是什么朝代的", "《春望》是不是五律", "帮我找一首写月亮的诗",
    "《登鹳雀楼》作者是谁", "《声声慢》原文有没有讹字", "王维是什么风格", "举头望明月出自哪首诗",
    "《江雪》写的是冬天吗", "杜甫写过哪些名篇", "这首合不合律", "《山居秋暝》好在哪里",
    "《水调歌头》是谁写的", "苏轼是什么朝代的", "帮我找一首写思乡的诗", "《咏鹅》的作者是谁",
    "《悯农》表达了什么", "唐诗和宋词有什么区别", "《静夜思》押什么韵", "推荐一首五言绝句",
]


async def ask(client, session_id, user_id, message):
    payload = {"sessionId": session_id, "userId": user_id, "message": message}
    answer = []
    async with client.stream("POST", BASE + "/agent/workflow", json=payload) as resp:
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:]
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            if "content" in event:
                answer.append(event["content"])
    return "".join(answer)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=int, default=20)
    parser.add_argument("--recall", action="store_true", help="最后追问最开始那首诗")
    args = parser.parse_args()
    session_id = uuid.uuid4().hex
    user_id = "demo-" + uuid.uuid4().hex[:8]
    async with httpx.AsyncClient(timeout=120) as client:
        for i in range(args.turns):
            question = QUESTIONS[i % len(QUESTIONS)]
            answer = await ask(client, session_id, user_id, question)
            print(f"[{i + 1}] Q: {question}\n    A: {answer[:80]}")
        if args.recall:
            answer = await ask(client, session_id, user_id, "最开始问的那首诗后来怎么说")
            print(f"[recall] {answer}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 拉起 MySQL 与 API(默认配置)并跑验收 1/3**

```powershell
# 终端 A:MySQL 8.4(若未运行)
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe" --datadir="C:\Users\fuze\mysql-data" --basedir="C:\Program Files\MySQL\MySQL Server 8.4" --port=3306

# 终端 B:API(默认窗口 64000)
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000

# 终端 C:默认配置 20 轮
.\.venv\Scripts\python.exe evals\demo_ch06.py --turns 20
Select-String -Path log\app.log -Pattern "layer1 降级|summary trigger|上下文预算不足"
```

Expected:
- 20 轮全部有答、进程不崩;
- 上面的 grep **无匹配**(验收 3:默认窗口装得下就不压);
- `log\app.log` 有 20 组 `model_ctx` / `history_ctx`,每组以 `end` 收尾。

- [ ] **Step 3: 演示配置跑验收 2/4**

停掉 API,用演示配置重启:

```powershell
$env:MODEL_CONTEXT_WINDOW="18000"
$env:MAX_OUTPUT_TOKENS="2000"
$env:MAX_USER_INPUT_TOKENS="2000"
$env:MAX_AGENT_STEPS="3"
$env:TOOL_RESULT_MAX_TOKENS="1200"
$env:RERANK_TOP_K="5"
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

启动日志 Expected:`[ctx] 预算:window=18000 history=5650 layer1=3954 layer2=1695`。

另开终端跑:

```powershell
.\.venv\Scripts\python.exe evals\demo_ch06.py --turns 22 --recall
Select-String -Path log\app.log -Pattern "layer1 降级|summary trigger|summary start|summary done|summary skip|summary fail"
Select-String -Path log\app.log -Pattern "model_ctx|history_ctx" | Measure-Object
```

Expected:
- 先出现 `layer1 降级 0→…`,再出现 `summary trigger 会话=… 层2 约 N token > 预算 1695`,随后 `summary start …` / `summary done … 第1段 …`;
- recall 回答中出现「静夜思」/「李白」(来自梗概,而非原文窗口);
- `summary done` 的时间戳晚于该轮 `[wf] intent=… elapsed=` 行,证明未阻塞回复;
- model_ctx / history_ctx 计数 ≥ 22×2。

- [ ] **Step 4: 验收 5(前端)**

按 Task 12 Step 4 的人工验证清单执行,记录结果。

- [ ] **Step 5: 追记 dev-notes**

在 `dev-notes/ch06.md` 追加「阶段 2:计划评审通过」「阶段 3:逐任务实现」「阶段 4:评估集」「阶段 5:验收与 finish」,每段按要求记四样(用户关键原话 / 关键产出 / 拒绝或纠偏 / 翻车与返工),并写入:
- spec 路径、plan 路径、每个任务提交 hash;
- 验收 5 条结果(默认 20 轮无降级、演示配置级联日志片段、recall 回答、grep 计数、前端结论);
- 摘要评估集通过率;
- 演示命令(`uvicorn` 与环境变量、`demo_ch06.py`)。

- [ ] **Step 6: 提交**

```bash
git add potry-ai-agent/evals/demo_ch06.py dev-notes/ch06.md
git commit -m "docs(ch06): record acceptance runs and add multi-turn demo script"
```

---

## 计划自审(spec 覆盖核对)

| spec 条目 | 落点 |
|---|---|
| §3.1 加 4 列 | Task 2 `Conversation` + `ensure_schema` |
| §3.2 摘要表 + 唯一键 | Task 2 `ConversationSummary` |
| §3.3 只落 user/assistant、回载过滤 tool | Task 2 storage/chat_service + Task 10 API |
| §4 三层 + 两个锚点 + 只挪 id | Task 3 `split_layers` / `downgrade_anchor`;Task 9 `_after_persist` |
| §4 层 2 截短三条规则 | Task 3 `truncate_content` |
| §5 固定顺序 + 梗概不占 system + 工具定义打头 | Task 5 `build_agent_context`(system 只有人设红线) |
| §5 层 1/层 2 从 DB 取、本轮从 State 取 | Task 5 `load_snapshot` + `turn_message_start+1` |
| §5.1 每轮时序 | Task 7 resolve、Task 8 agent、Task 9 log |
| §6 token 估算 + 预算公式 + 自检 | Task 1 |
| §7 异步摘要触发/锁/批次/边界/失败 | Task 6、Task 9 |
| §7.3 摘要 prompt 四类事实 | Task 6 `SUMMARY_PROMPT` + Task 13 评估集 |
| §8 add_messages / turn_message_start / log 补 AI | Task 7、Task 9 |
| §9 model_ctx / history_ctx / 预算 / 降级 / 摘要日志 | Task 4、Task 9 |
| §10 落库返回三 id + 两个只读接口 | Task 2、Task 10 |
| §11 侧栏 / 切换回载 / 新对话 / 静默降级 / 五种状态 | Task 12 |
| §12 错误降级 | Task 6 fail、Task 9 落库失败、Task 10 API 500、Task 12 console.warn |
| §13 单测 + 评估集 + 端到端 | Task 1–11、13、14 |
| 验收 1–5 | Task 14 |
