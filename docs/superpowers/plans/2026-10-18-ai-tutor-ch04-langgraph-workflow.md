# Ch04 · LangGraph Workflow 确定性编排 · 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Ch02 的单轮 Function Calling 升级为以 LangGraph 图骨架为核心的确定性 Workflow 编排,主力 Agent 作为骨架内的 ReAct 执行节点。

**Architecture:** 先用手写无框架循环(`naive_agent.py`)证明 Agent 本质是"带工具调用的循环",再用 LangGraph 重构为固定节点顺序的图(指代消解 → 意图识别 → 意图分流 → 知识检索 → 置信度闸 → 主力 Agent → 日志记录),意图分流规则硬编码,会话状态经 LangGraph 原生 State 贯穿并用自带 checkpointer 持久化。

**Tech Stack:** Python 3.11 · FastAPI · LangChain 1.6.10 · **LangGraph 1.2.16 + langgraph-checkpoint-sqlite 3.1.2(`AsyncSqliteSaver`)** · MySQL 8.4 · Milvus Lite + BGE-M3(复用 Ch03)· 原生 HTML/CSS/JS 前端。

**权威 spec:** [2026-10-18-ai-tutor-ch04-langgraph-workflow-design.md](file:///e:/javatexts/poetry-spring2/docs/superpowers/specs/2026-10-18-ai-tutor-ch04-langgraph-workflow-design.md)

---

## 计划期已核实的事实(执行时直接用,不必重查)

| 项 | 结论 | 来源 |
|---|---|---|
| 同步/异步冲突 | 官方 `SqliteSaver` 是**同步专用**,`await graph.ainvoke` 会抛 `NotImplementedError`;改用 **`AsyncSqliteSaver`**(`langgraph.checkpoint.sqlite.aio`)。**已请示用户并获批**(见 spec §12 新增留痕) | 实测 |
| 依赖版本 | `langgraph==1.2.16` + `langgraph-checkpoint-sqlite==3.1.2` 与 `langchain-core==1.6.10` **可干净解析**(连带 `langgraph-checkpoint 4.3.0` / `aiosqlite 0.22.1` / `langgraph-prebuilt 1.1.1` / `langgraph-sdk 0.4.8` / `sqlite-vec` / `ormsgpack`);安装把 `websockets` 从 17.2 降到 16.1.1(uvicorn 兼容,已实测服务可起) | 实测 |
| AsyncSqliteSaver 用法 | `conn = await aiosqlite.connect(path)` → `saver = AsyncSqliteSaver(conn)` → `await saver.setup()`;**父目录不存在会 `unable to open database file`**,必须先 `os.makedirs` | 实测 |
| 状态可序列化 | State 里放 LangChain `HumanMessage/AIMessage/ToolMessage` 由默认 serde 正常存取(往返后类型不变) | 实测 |
| 图 API | `StateGraph(TypedDict)` + `add_node` + `add_edge(START,…)` + `add_conditional_edges(node, fn, path_map)` + `.compile(checkpointer=…)`;调用需 `config={"configurable":{"thread_id": …}}` | Context7 + 实测 |
| `feedback` 表 | 已存在,5 行。列:**`id` int PK auto_increment / `userid` int NULL / `messsage` text NULL / `creatime` timestamp default CURRENT_TIMESTAMP**(列名拼写照抄,勿"纠正") | 实测 `SHOW COLUMNS` |
| `pending_questions` 表 | **尚不存在**,由本计划 T4 新建 | 实测 |

**环境备忘:** 工作目录 `e:\javatexts\poetry-spring2`,服务目录 `potry-ai-agent/`;解释器 `.\.venv\Scripts\python.exe`;**PowerShell 5 不支持 `&&`,用 `;`**;测试必须**在 `potry-ai-agent/` 下用 `python -m pytest`**(`python -m` 才会把 cwd 加入 `sys.path`,`import main` 才成立);基线 **132 passed**;git 只 add 明确文件,**严禁 `git add -A`**,提交信息单行。

---

## File Structure

**新建:**

| 文件 | 职责 |
|---|---|
| `potry-ai-agent/naive_agent.py` | 无框架原生 Agent 循环(需求第 1 条先行验证) |
| `potry-ai-agent/workflow/__init__.py` | 包标记 |
| `potry-ai-agent/workflow/deps.py` | 依赖容器 `WorkflowDeps` + 单例/测试注入钩子(仓库既有惯例) |
| `potry-ai-agent/workflow/state.py` | `WorkflowState(TypedDict)` |
| `potry-ai-agent/workflow/intent.py` | 七类意图 + **硬编码** `INTENT_TO_ROUTE` + `parse_intent` |
| `potry-ai-agent/workflow/confidence.py` | 知识检索(三源合并)+ 置信度闸判定 |
| `potry-ai-agent/workflow/agent_react.py` | ReAct 子循环:`agent_node` / `tool_node` / `should_continue` |
| `potry-ai-agent/workflow/nodes.py` | 其余六节点 + 条件边判定 `after_route` / `after_gate` |
| `potry-ai-agent/workflow/graph.py` | 图装配 + `open_checkpointer` |
| `potry-ai-agent/app_storage.py` | `AppBase` + `Feedback` 模型 + `AppStorage` |
| `potry-ai-agent/tools/feedback_tool.py` | `submit_feedback` 工具 |
| `potry-ai-agent/tests/test_naive_agent.py` | T2 测试 |
| `potry-ai-agent/tests/test_workflow_intent.py` | T3 测试 |
| `potry-ai-agent/tests/test_workflow_confidence.py` | T4 测试 |
| `potry-ai-agent/tests/test_workflow_agent_react.py` | T5 测试 |
| `potry-ai-agent/tests/test_feedback.py` | T6 测试 |
| `potry-ai-agent/tests/test_workflow_nodes.py` | T7 测试 |
| `potry-ai-agent/tests/test_workflow_graph.py` | T8 测试 |
| `potry-ai-agent/tests/test_workflow_endpoint.py` | T9 测试 |

**修改:**

| 文件 | 改动 |
|---|---|
| `potry-ai-agent/config.py` | 新增 `workflow_max_iter` / `workflow_max_tokens` / `workflow_checkpoint_path` |
| `potry-ai-agent/requirements.txt` | 追加 langgraph 两行 |
| `potry-ai-agent/.gitignore` | 追加 `checkpoints/` |
| `potry-ai-agent/tests/conftest.py` | 追加 `WORKFLOW_CHECKPOINT_PATH=:memory:`(测试不落盘) |
| `potry-ai-agent/prompts.py` | 追加 `INTENT_PROMPT` 与三条预设话术常量 |
| `potry-ai-agent/knowledge.py` | 新增 `PendingQuestion` 模型 + `add_pending_question` 方法 |
| `potry-ai-agent/main.py` | `init_db` 加 `AppBase`;模块级装配 deps;lifespan 开 checkpointer 编译图;新增 `/agent/workflow`(SSE)与 `POST /agent/feedback` |
| `potry-ai-agent/static/chat.html` | 改指 `/agent/workflow`;新增 `action` 事件渲染「转人工」「提交反馈」两独立按钮 |

**不动:** `chat_service.py`(原单轮编排保留)、`memory.py`、`storage.py`、`vector_store.py`、`embeddings.py`、`mining.py`、`build_kb.py`、Ch01–Ch03 全部既有测试。

---

## Task 1: 依赖、配置与忽略项

**Files:**
- Modify: `potry-ai-agent/requirements.txt`
- Modify: `potry-ai-agent/.gitignore`
- Modify: `potry-ai-agent/config.py`
- Modify: `potry-ai-agent/tests/conftest.py`
- Test: `potry-ai-agent/tests/test_config.py`(追加用例)

- [ ] **Step 1: 核对 Context7 与已装版本(需求工作要求 3)**

本计划编写期已过 Context7 并实测通过,执行时只需复核已装版本是否与计划一致:

```powershell
.\.venv\Scripts\python.exe -m pip show langgraph langgraph-checkpoint-sqlite langgraph-checkpoint aiosqlite | Select-String -Pattern "Name|Version"
```

Expected: `langgraph 1.2.16`、`langgraph-checkpoint-sqlite 3.1.2`、`langgraph-checkpoint 4.3.0`、`aiosqlite 0.22.1`。**若缺失或版本不符**则执行:

```powershell
.\.venv\Scripts\python.exe -m pip install langgraph==1.2.16 langgraph-checkpoint-sqlite==3.1.2
```

- [ ] **Step 2: 写配置测试(先失败)**

追加到 `potry-ai-agent/tests/test_config.py` 末尾:

```python
def test_load_settings_reads_ch04_workflow_configs(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("MYSQL_URL", "sqlite:///:memory:")
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", "fake-model-path")
    monkeypatch.setenv("WORKFLOW_MAX_ITER", "3")
    monkeypatch.setenv("WORKFLOW_MAX_TOKENS", "1234")
    s = load_settings()
    assert s.workflow_max_iter == 3
    assert s.workflow_max_tokens == 1234


def test_workflow_defaults_applied(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("MYSQL_URL", "sqlite:///:memory:")
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", "fake-model-path")
    monkeypatch.delenv("WORKFLOW_MAX_ITER", raising=False)
    monkeypatch.delenv("WORKFLOW_MAX_TOKENS", raising=False)
    s = load_settings()
    assert s.workflow_max_iter == 4      # spec §6 默认 4
    assert s.workflow_max_tokens == 8000  # spec §6 默认 8000
    assert s.workflow_checkpoint_path.endswith("graph.sqlite")


def test_rejects_non_positive_workflow_max_iter(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("MYSQL_URL", "sqlite:///:memory:")
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", "fake-model-path")
    monkeypatch.setenv("WORKFLOW_MAX_ITER", "0")
    with pytest.raises(RuntimeError, match="WORKFLOW_MAX_ITER"):
        load_settings()
```

- [ ] **Step 3: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_config.py -q
```

Expected: FAIL,`AttributeError: 'Settings' object has no attribute 'workflow_max_iter'`。

- [ ] **Step 4: 实现配置项**

`potry-ai-agent/config.py`:

(a) 在 `_DEFAULT_MINING_CRON = "0 3 * * *"` 之后追加:

```python
# Ch04:Workflow 编排默认值(与 Settings 共用,单一来源)
_DEFAULT_WORKFLOW_MAX_ITER = 4
_DEFAULT_WORKFLOW_MAX_TOKENS = 8000
_DEFAULT_WORKFLOW_CHECKPOINT_PATH = str(
    Path(__file__).resolve().parent / "checkpoints" / "graph.sqlite"
)
```

(b) 在 `Settings` 的 `mining_cron: str = _DEFAULT_MINING_CRON` 之后追加字段:

```python
    workflow_max_iter: int = _DEFAULT_WORKFLOW_MAX_ITER
    workflow_max_tokens: int = _DEFAULT_WORKFLOW_MAX_TOKENS
    workflow_checkpoint_path: str = _DEFAULT_WORKFLOW_CHECKPOINT_PATH
```

(c) 在 `load_settings` 的 `try` 块内、`warmup_on_start = ...` 之后追加:

```python
        workflow_max_iter = int(os.getenv("WORKFLOW_MAX_ITER") or str(_DEFAULT_WORKFLOW_MAX_ITER))
        workflow_max_tokens = int(os.getenv("WORKFLOW_MAX_TOKENS") or str(_DEFAULT_WORKFLOW_MAX_TOKENS))
```

(d) 在 `mining_batch_size <= 0` 的 fail-fast 之后追加:

```python
    if workflow_max_iter <= 0:
        raise RuntimeError(f"WORKFLOW_MAX_ITER 必须为正整数(当前: {workflow_max_iter})")
    if workflow_max_tokens <= 0:
        raise RuntimeError(f"WORKFLOW_MAX_TOKENS 必须为正整数(当前: {workflow_max_tokens})")
```

(e) 在 `return Settings(...)` 里 `mining_cron=os.getenv("MINING_CRON") or _DEFAULT_MINING_CRON,` 之后追加:

```python
        workflow_max_iter=workflow_max_iter,
        workflow_max_tokens=workflow_max_tokens,
        workflow_checkpoint_path=(
            os.getenv("WORKFLOW_CHECKPOINT_PATH") or _DEFAULT_WORKFLOW_CHECKPOINT_PATH
        ),
```

- [ ] **Step 5: 测试环境不落盘 + 忽略产物**

`potry-ai-agent/tests/conftest.py` 在 `WARMUP_ON_START` 那行之后追加:

```python
os.environ.setdefault("WORKFLOW_CHECKPOINT_PATH", ":memory:")  # 测试用内存库,不在仓库建 checkpoints/
```

`potry-ai-agent/.gitignore` 在 `milvus_data/` 之后追加:

```gitignore

# Ch04 本地产物(图状态 checkpointer 不入 git)
checkpoints/
```

`potry-ai-agent/requirements.txt` 在 Ch03 依赖块之前追加:

```txt
# Ch04 LangGraph 编排依赖(版本与 langchain-core 1.6.10 实测兼容)
langgraph==1.2.16
langgraph-checkpoint-sqlite==3.1.2
```

- [ ] **Step 6: 跑测试 + 全量回归**

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Expected: `138 passed`(基线 132 + 新增 3 个 config 用例……若数字不同,以"原 132 全绿 + 新用例全绿"为准)。

- [ ] **Step 7: 提交**

```powershell
git add potry-ai-agent/requirements.txt potry-ai-agent/.gitignore potry-ai-agent/config.py potry-ai-agent/tests/conftest.py potry-ai-agent/tests/test_config.py
git commit -m "feat(ch04): 引入 LangGraph 依赖与 Workflow 配置项(MAX_ITER/MAX_TOKENS/checkpoint 路径)"
```

---

## Task 2: 无框架原生 Agent 循环

**需求第 1 条:** 先不依赖任何编排框架,手写最基础循环(LLM → tool_calls → 执行 → 回灌 → 无工具调用即收敛),彻底明确 Agent 本质;完成后再基于 LangGraph 重构(Task 5/8)。

**Files:**
- Create: `potry-ai-agent/naive_agent.py`
- Test: `potry-ai-agent/tests/test_naive_agent.py`

- [ ] **Step 1: 写失败测试**

`potry-ai-agent/tests/test_naive_agent.py`:

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_naive_agent.py -q
```

Expected: FAIL,`ModuleNotFoundError: No module named 'naive_agent'`。

- [ ] **Step 3: 实现 `naive_agent.py`**

`potry-ai-agent/naive_agent.py`:

```python
"""无框架原生 Agent 循环:LLM 调用 → 工具调用 → 结果回传 → 无工具调用即收敛。

Ch04 需求第 1 条明确要求"先完成无框架原生实现,彻底明确 Agent 本质为带工具调用能力的
循环,完成后再基于 LangGraph 重构"。本模块即那份**先行验证版**,与
`workflow/agent_react.py`(LangGraph 版)互为对照;两者停止判定语义保持一致。

停止判定三条(spec §6):
1. 响应不含 tool_calls → 自然收敛;
2. iterations 达到 max_iter → 强制收敛(丢弃带 tool_calls 的裸 AI,改发纯文本请求);
3. tokens_used 达到 max_tokens → 同上。
"""
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.messages.utils import count_tokens_approximately

from tools.registry import make_tool_message

DEFAULT_MAX_ITER = 4
DEFAULT_MAX_TOKENS = 8000

_FORCE_ANSWER_HINT = "请直接根据目前已有的信息作答,不要再调用任何工具。"
_FORCE_ANSWER_FALLBACK = "信息比较多,我先说到这儿;如果你能再补充一点线索,我可以答得更准。"


async def run_naive_agent(
    llm,
    registry,
    messages: list,
    max_iter: int = DEFAULT_MAX_ITER,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict:
    """手写 Agent 循环。原地修改 `messages`(便于测试断言回灌结构)。

    返回 `{"answer": str, "iterations": int, "tokens_used": int, "stop_reason": str}`,
    `stop_reason` ∈ `no_tool_calls` / `max_iter` / `max_tokens`。
    """
    # 带上工具再问,模型才可能产出 tool_calls
    bound = llm.bind_tools(registry.get_tools())
    iterations = 0
    while iterations < max_iter:
        iterations += 1
        ai: AIMessage = await bound.ainvoke(messages)
        messages.append(ai)
        tokens_used = count_tokens_approximately(messages)
        if not ai.tool_calls:
            return _result(ai.content, iterations, tokens_used, "no_tool_calls")
        if tokens_used >= max_tokens:
            # 丢弃裸 tool_calls AI(无配对 ToolMessage 会让真实 API 400),改发纯文本
            messages.pop()
            return _result(
                await _force_answer(llm, messages), iterations, tokens_used, "max_tokens"
            )
        for tc in ai.tool_calls:
            result = await registry.execute(tc["name"], tc["args"])
            messages.append(make_tool_message(tc["id"], tc["name"], result))
    # 迭代上限:第 max_iter 轮不再执行工具,直接强制收敛(故 calls 少一次)
    if messages and isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        messages.pop()
    return _result(await _force_answer(llm, messages), iterations, tokens_used, "max_iter")


async def _force_answer(llm, messages: list) -> str:
    """不带工具再问一次,逼出一段纯文本答案(强制收敛用)。"""
    try:
        forced = await llm.ainvoke(messages + [HumanMessage(content=_FORCE_ANSWER_HINT)])
    except Exception as exc:  # noqa: BLE001 - 强制作答失败也要收敛,不让整轮崩掉
        print(f"[naive] 强制作答失败: {str(exc)[:200]}")
        return _FORCE_ANSWER_FALLBACK
    return forced.content or _FORCE_ANSWER_FALLBACK


def _result(answer: str | None, iterations: int, tokens_used: int, stop_reason: str) -> dict:
    return {
        "answer": answer or "",
        "iterations": iterations,
        "tokens_used": tokens_used,
        "stop_reason": stop_reason,
    }
```

> 注:`max_iter` 路径里 `tokens_used` 取自上一轮循环的局部变量,故需在进入 `while` 前初始化一个同名变量以免 `UnboundLocalError`——若 `max_iter<=0` 直接进不到循环,`tokens_used` 未定义。为此在函数体 `iterations = 0` 那行后补 `tokens_used = 0`,并在循环内保持赋值。

修正后的关键片段(请以此为准):

```python
    iterations = 0
    tokens_used = 0
    while iterations < max_iter:
        ...
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_naive_agent.py -q
```

Expected: `3 passed`。

- [ ] **Step 5: 提交**

```powershell
git add potry-ai-agent/naive_agent.py potry-ai-agent/tests/test_naive_agent.py
git commit -m "feat(ch04): 无框架原生 Agent 循环先行验证(LLM/tool_calls/回灌/收敛)"
```

---

## Task 3: workflow 包骨架、状态、意图与话术

**Files:**
- Create: `potry-ai-agent/workflow/__init__.py`
- Create: `potry-ai-agent/workflow/deps.py`
- Create: `potry-ai-agent/workflow/state.py`
- Create: `potry-ai-agent/workflow/intent.py`
- Modify: `potry-ai-agent/prompts.py`
- Test: `potry-ai-agent/tests/test_workflow_intent.py`

- [ ] **Step 1: 写失败测试**

`potry-ai-agent/tests/test_workflow_intent.py`:

```python
"""七类意图 → 四出口硬编码映射的完整性与解析降级。"""
from workflow import intent


def test_mapping_covers_all_seven_intents():
    assert len(intent.INTENT_LABELS) == 7
    assert set(intent.INTENT_TO_ROUTE) == set(intent.INTENT_LABELS)


def test_route_values_are_legal():
    assert set(intent.INTENT_TO_ROUTE.values()) <= set(intent.ROUTES)
    assert set(intent.ROUTES) == {
        intent.ROUTE_KNOWLEDGE,
        intent.ROUTE_BUSINESS,
        intent.ROUTE_COMPLAINT,
        intent.ROUTE_CHITCHAT,
    }


def test_knowledge_and_business_split_matches_spec():
    # spec §4:释义/典故 → 知识类;查诗词/查诗人/查朝代 → 业务类
    assert intent.INTENT_TO_ROUTE["poem_explain"] == intent.ROUTE_KNOWLEDGE
    assert intent.INTENT_TO_ROUTE["reference_lookup"] == intent.ROUTE_KNOWLEDGE
    assert intent.INTENT_TO_ROUTE["find_poem"] == intent.ROUTE_BUSINESS
    assert intent.INTENT_TO_ROUTE["find_poet"] == intent.ROUTE_BUSINESS
    assert intent.INTENT_TO_ROUTE["find_dynasty"] == intent.ROUTE_BUSINESS
    assert intent.INTENT_TO_ROUTE["complaint"] == intent.ROUTE_COMPLAINT
    assert intent.INTENT_TO_ROUTE["chitchat"] == intent.ROUTE_CHITCHAT


def test_parse_intent_accepts_plain_json():
    assert intent.parse_intent('{"intent": "find_poet"}') == "find_poet"


def test_parse_intent_tolerates_fenced_json():
    assert intent.parse_intent('```json\n{"intent": "poem_explain"}\n```') == "poem_explain"


def test_parse_intent_degrades_to_chitchat():
    assert intent.parse_intent("今天天气不错") == intent.DEFAULT_INTENT
    assert intent.parse_intent('{"intent": "no_such_label"}') == intent.DEFAULT_INTENT
    assert intent.parse_intent('{"nope": 1}') == intent.DEFAULT_INTENT
    assert intent.DEFAULT_INTENT == "chitchat"
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_intent.py -q
```

Expected: FAIL,`ModuleNotFoundError: No module named 'workflow'`。

- [ ] **Step 3: 建包与依赖容器**

`potry-ai-agent/workflow/__init__.py`(空文件):

```python
```

`potry-ai-agent/workflow/deps.py`:

```python
"""Workflow 编排依赖容器:节点通过 get_deps() 取用。

采用"模块级单例 + 测试注入钩子"的写法,与 Ch03 的 embeddings.set_embedder /
vector_store.set_store 保持同一仓库惯例(避免把依赖一路穿参进每个节点)。
"""
from config import Settings


class WorkflowDeps:
    def __init__(self, settings, llm, registry, knowledge_storage, chat_storage) -> None:
        self.settings = settings
        self.llm = llm
        self.registry = registry
        self.knowledge_storage = knowledge_storage
        self.chat_storage = chat_storage
        # 停止判定上限(spec §6),来自配置便于单测覆盖
        self.max_iter = settings.workflow_max_iter
        self.max_tokens = settings.workflow_max_tokens


_deps: WorkflowDeps | None = None


def configure(deps: WorkflowDeps | None) -> None:
    """装配/复位编排依赖(传 None 复位;测试注入 stub 亦走此口)。"""
    global _deps
    _deps = deps


def get_deps() -> WorkflowDeps:
    if _deps is None:
        raise RuntimeError("workflow 依赖未装配,请先在 main.py 调用 workflow.deps.configure()")
    return _deps
```

- [ ] **Step 4: 实现状态与意图**

`potry-ai-agent/workflow/state.py`:

```python
"""Ch04 编排状态:贯穿图全流程的 WorkflowState(TypedDict)。

`messages` / `tool_trace` 用 `operator.add` 做累积(LangGraph 官方 reducer 写法);
其余字段为单值覆盖语义。`total=False` 使所有键可选,便于分支出口只写自己那几个键。
"""
import operator
from typing import Annotated, TypedDict


class WorkflowState(TypedDict, total=False):
    session_id: str              # 会话标识,同时作为 checkpointer 的 thread_id
    user_input: str              # 用户原始输入
    resolved_input: str          # 指代消解后输入(本章最简版:与原始输入相同)
    intent: str                  # 七类意图标签
    route: str                   # 四个出口之一
    retrieved: list[dict]        # 检索证据(hit + 回查到的原文片段)
    evidence_score: float        # 证据强度(合并后 top1 相似度)
    gate_status: str             # pass / insufficient;未走检索的出口保持缺省(日志记 skip)
    messages: Annotated[list, operator.add]     # ReAct 子循环消息序列(累积)
    tool_trace: Annotated[list, operator.add]   # 工具调用轨迹(供 SSE 与落库)
    answer: str                  # 最终回答
    actions: list[str]           # 可选操作标识(投诉类为 ["handoff", "feedback"])
    iterations: int              # ReAct 迭代数
    tokens_used: int             # token 累计
    fallback_reason: str         # 兜底/强制收敛原因
    started_at: float            # 本轮起始 monotonic 时间戳(日志耗时用)
```

`potry-ai-agent/workflow/intent.py`:

```python
"""七类意图定义 + **硬编码**分流映射(七类 → 四出口)。

分流规则不交给模型决策:意图识别节点只负责产出标签,出口由本模块常量表决定(spec §4)。
"""
import json

# 四个出口
ROUTE_KNOWLEDGE = "knowledge"
ROUTE_BUSINESS = "business"
ROUTE_COMPLAINT = "complaint"
ROUTE_CHITCHAT = "chitchat"
ROUTES = (ROUTE_KNOWLEDGE, ROUTE_BUSINESS, ROUTE_COMPLAINT, ROUTE_CHITCHAT)

# 七类意图标签
INTENT_POEM_EXPLAIN = "poem_explain"
INTENT_REFERENCE_LOOKUP = "reference_lookup"
INTENT_FIND_POEM = "find_poem"
INTENT_FIND_POET = "find_poet"
INTENT_FIND_DYNASTY = "find_dynasty"
INTENT_COMPLAINT = "complaint"
INTENT_CHITCHAT = "chitchat"

INTENT_LABELS = (
    INTENT_POEM_EXPLAIN,
    INTENT_REFERENCE_LOOKUP,
    INTENT_FIND_POEM,
    INTENT_FIND_POET,
    INTENT_FIND_DYNASTY,
    INTENT_COMPLAINT,
    INTENT_CHITCHAT,
)

# 七类 → 四出口(硬编码,不得改为模型决策)
INTENT_TO_ROUTE = {
    INTENT_POEM_EXPLAIN: ROUTE_KNOWLEDGE,
    INTENT_REFERENCE_LOOKUP: ROUTE_KNOWLEDGE,
    INTENT_FIND_POEM: ROUTE_BUSINESS,
    INTENT_FIND_POET: ROUTE_BUSINESS,
    INTENT_FIND_DYNASTY: ROUTE_BUSINESS,
    INTENT_COMPLAINT: ROUTE_COMPLAINT,
    INTENT_CHITCHAT: ROUTE_CHITCHAT,
}

DEFAULT_INTENT = INTENT_CHITCHAT


def parse_intent(text: str) -> str:
    """从模型输出中取出 `intent` 字段。

    模型可能包 ```json 围栏或加解释文字,故按首 `{` / 末 `}` 截取再解析;
    任何解析失败或标签非法 → 降级 `chitchat`(spec §4/§10:不抛异常、不阻断)。
    """
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
        label = str(data.get("intent", "")).strip()
    except (ValueError, json.JSONDecodeError, AttributeError):
        return DEFAULT_INTENT
    return label if label in INTENT_LABELS else DEFAULT_INTENT
```

- [ ] **Step 5: 追加意图 Prompt 与预设话术**

`potry-ai-agent/prompts.py` 末尾追加:

```python
# ---------- Ch04:意图识别与预设话术 ----------

INTENT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是意图分类器。把用户问题归入下列七类之一,只输出一行 JSON,不要任何解释与多余文字:
{{"intent": "<标签>"}}

七类标签:
- poem_explain: 诗词释义/赏析(如"某首诗表达了什么感情""这首诗什么意思")
- reference_lookup: 典故/出处查询(如"某句出自哪首诗""某个典故的来历")
- find_poem: 查诗词(想找某首具体的诗,如"那首讲月亮的叫啥")
- find_poet: 查诗人(问某位诗人的生平/信息)
- find_dynasty: 查朝代(问某朝代有哪些诗或朝代相关信息)
- complaint: 纠错或表达不满(说答得不对、不满意、搞错了)
- chitchat: 其它闲聊""",
        ),
        ("human", "{question}"),
    ]
)

# spec §4/§8:投诉与闲聊走**预设固定话术**,不调模型、不调工具
COMPLAINT_REPLY = (
    "抱歉,让你有不好的体验了。这轮问题我记下来了,"
    "你可以选择转人工,或提交反馈告诉我具体哪里不对。"
)
CHITCHAT_REPLY = "我是青莲,只陪你聊诗词文史。想读哪首诗,或问哪句词的出处,随时招呼我。"

# spec §7:知识类证据不足时的兜底话术
FALLBACK_REPLY = "这块我暂时没查到确切的资料,不敢乱讲。要不换个问法,或告诉我更具体的线索?"
```

- [ ] **Step 6: 跑测试确认通过**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_intent.py tests/test_prompts.py -q
```

Expected: 全绿。

- [ ] **Step 7: 提交**

```powershell
git add potry-ai-agent/workflow/__init__.py potry-ai-agent/workflow/deps.py potry-ai-agent/workflow/state.py potry-ai-agent/workflow/intent.py potry-ai-agent/prompts.py potry-ai-agent/tests/test_workflow_intent.py
git commit -m "feat(ch04): workflow 状态/依赖容器与七类意图硬编码分流映射"
```

---

## Task 4: 知识检索 + 置信度闸 + 待处理问题表

**Files:**
- Create: `potry-ai-agent/workflow/confidence.py`
- Modify: `potry-ai-agent/knowledge.py`
- Test: `potry-ai-agent/tests/test_workflow_confidence.py`

- [ ] **Step 1: 写失败测试**

`potry-ai-agent/tests/test_workflow_confidence.py`:

```python
"""知识检索(三源合并)与置信度闸判定;待处理问题落库。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import Settings
from embeddings import set_embedder
from knowledge import KnowledgeBase, KnowledgeStorage, PendingQuestion
from vector_store import set_store
from workflow.confidence import is_evidence_sufficient, retrieve_evidence

_DIM = 1024


def make_settings(**over):
    base = dict(
        llm_base_url="http://fake",
        llm_api_key="CONFIGURE_LOCALLY",
        llm_model="fake",
        history_max_tokens=2000,
        llm_temperature=0.7,
        mysql_url="sqlite:///:memory:",
        embedding_model_path="fake-model-path",
    )
    base.update(over)
    return Settings(**base)


class FakeEmbedder:
    def embed(self, texts):
        return [[0.0] * _DIM for _ in texts]


class FakeStore:
    """按 source_type 返回不同分数,验证三源合并与降序。"""

    def __init__(self, scores=None, boom=False):
        self.scores = scores or {"poem": 0.9, "poet": 0.3, "qa": 0.6}
        self.boom = boom
        self.calls = []

    def search(self, vector, topk, source_type):
        self.calls.append(source_type)
        if self.boom:
            raise RuntimeError("milvus 不可用")
        return [
            {
                "id": abs(hash(source_type)) % 1000,
                "score": self.scores[source_type],
                "source_type": source_type,
                "title": "静夜思",
                "writer": "李白",
                "dynasty": "唐",
            }
        ]


@pytest.fixture
def inject():
    """注入 fake 嵌入器/向量库,测试后务必复位(否则污染其它用例)。"""
    def _inject(store):
        set_embedder(FakeEmbedder())
        set_store(store)
    yield _inject
    set_embedder(None)
    set_store(None)


def test_is_evidence_sufficient_boundary():
    assert is_evidence_sufficient(0.5, 0.5) is True    # >= 阈值即通过
    assert is_evidence_sufficient(0.4999, 0.5) is False


def test_retrieve_merges_three_sources_and_sorts(inject):
    store = FakeStore()
    inject(store)
    hits, score = retrieve_evidence("那首讲月亮的", make_settings())
    assert store.calls == ["poem", "poet", "qa"]       # 三类各查一次
    assert score == 0.9                                # top1 相似度
    assert [h["score"] for h in hits] == [0.9, 0.6, 0.3]  # 合并后降序


def test_retrieve_degrades_to_empty_on_store_failure(inject):
    inject(FakeStore(boom=True))
    hits, score = retrieve_evidence("随便问问", make_settings())
    assert hits == [] and score == 0.0                 # 检索失败视为证据不足(spec §10)


def test_retrieve_degrades_when_embedder_missing():
    set_embedder(None)  # 未注入 → 走真实懒加载,必然失败
    hits, score = retrieve_evidence("随便问问", make_settings(embedding_model_path="不存在的目录"))
    assert hits == [] and score == 0.0


def test_add_pending_question_persists():
    engine = create_engine("sqlite:///:memory:")
    KnowledgeBase.metadata.create_all(engine)
    storage = KnowledgeStorage(sessionmaker(bind=engine))
    qid = storage.add_pending_question("一个没查到资料的问题", "s1")
    assert qid is not None
    with sessionmaker(bind=engine)() as session:
        row = session.get(PendingQuestion, qid)
        assert row.question == "一个没查到资料的问题"
        assert row.session_id == "s1"
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_confidence.py -q
```

Expected: FAIL(缺 `workflow.confidence`、`PendingQuestion`、`add_pending_question`)。

- [ ] **Step 3: 实现 `workflow/confidence.py`**

`potry-ai-agent/workflow/confidence.py`:

```python
"""置信度闸:知识类检索与"证据是否够进 Agent"的判定。

仅作用于知识类意图**检索完成后、进 Agent 之前**(spec §7):
- 检索范围 = 全库,`poem` / `poet` / `qa` 三类各取 top-k 后合并降序(最简实现;
  `vector_store.search` 单次只吃一个 source_type,故需三次调用);
- 阈值**复用 Ch03 已有配置** `settings.similarity_threshold`,不新增环境变量;
- 检索失败(模型/向量库不可用)一律视为**证据不足**(spec §10)。
"""
from config import Settings

SOURCE_TYPES = ("poem", "poet", "qa")


def retrieve_evidence(question: str, settings: Settings) -> tuple[list[dict], float]:
    """返回 `(合并降序后的命中列表, top1 相似度)`;任何失败都退化为 `([], 0.0)`。"""
    try:
        from embeddings import embed
        from vector_store import search

        vector = embed([question])[0]
        hits: list[dict] = []
        for source_type in SOURCE_TYPES:
            try:
                hits.extend(search(vector, settings.milvus_topk, source_type))
            except Exception as exc:  # noqa: BLE001 - 单类失败不拖垮其余两类
                print(f"[wf] retrieve fail source_type={source_type}: {str(exc)[:200]}")
        hits.sort(key=lambda h: h.get("score", 0.0), reverse=True)
        return hits, (hits[0]["score"] if hits else 0.0)
    except Exception as exc:  # noqa: BLE001 - 嵌入失败整段降级为证据不足
        print(f"[wf] retrieve fail: {str(exc)[:200]}")
        return [], 0.0


def is_evidence_sufficient(score: float, threshold: float) -> bool:
    """`evidence_score >= 阈值` 即判定证据充足(spec §7)。"""
    return score >= threshold
```

- [ ] **Step 4: 给 `knowledge.py` 加待处理问题表**

`potry-ai-agent/knowledge.py`:

(a) 在 `KnowledgeMiningCursor` 类之后、`_FIELDS = (...)` 之前插入:

```python
class PendingQuestion(KnowledgeBase):
    """置信度不足的问题:证据不足的兜底问题在此暂存,供后续数据飞轮迭代取用。

    与知识库表同 Base,便于 main.py 的 create_all 一并建表(spec §9)。
    """

    __tablename__ = "pending_questions"

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
```

(b) 在 `KnowledgeStorage` 的 `count_by_status` 方法之后追加:

```python
    # ---------- pending questions ----------
    def add_pending_question(self, question: str, session_id: str | None = None) -> int:
        """把证据不足的问题写入 pending_questions,返回新行 id。"""
        with self._factory() as session:
            row = PendingQuestion(question=question, session_id=session_id)
            session.add(row)
            session.commit()
            return row.id
```

- [ ] **Step 5: 跑测试确认通过**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_confidence.py tests/test_knowledge.py tests/test_embeddings.py tests/test_vector_store.py -q
```

Expected: 全绿。

- [ ] **Step 6: 提交**

```powershell
git add potry-ai-agent/workflow/confidence.py potry-ai-agent/knowledge.py potry-ai-agent/tests/test_workflow_confidence.py
git commit -m "feat(ch04): 知识检索三源合并与置信度闸 + pending_questions 表"
```

---

## Task 5: 主力 Agent 的 ReAct 子循环

**Files:**
- Create: `potry-ai-agent/workflow/agent_react.py`
- Test: `potry-ai-agent/tests/test_workflow_agent_react.py`

- [ ] **Step 1: 写失败测试**

`potry-ai-agent/tests/test_workflow_agent_react.py`:

```python
"""ReAct 子循环:agent 节点收敛 / tool 节点执行回灌 / should_continue 停止判定三条。"""
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from config import Settings
from tools.registry import ToolRegistry
from workflow.agent_react import agent_node, should_continue, tool_node
from workflow.deps import WorkflowDeps, configure


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


def make_settings(**over):
    base = dict(
        llm_base_url="http://fake", llm_api_key="CONFIGURE_LOCALLY", llm_model="fake",
        history_max_tokens=2000, llm_temperature=0.7,
        mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
    )
    base.update(over)
    return Settings(**base)


def make_registry():
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


def _deps(llm, registry, **over):
    deps = WorkflowDeps(make_settings(**over), llm, registry, None, None)
    configure(deps)
    return deps


def _tc(call_id="c1"):
    return {"name": "query_poem", "args": {"keyword": "静夜思"}, "id": call_id, "type": "tool_call"}


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    configure(None)


@pytest.mark.asyncio
async def test_agent_converges_in_one_iteration_without_tools():
    registry, calls = make_registry()
    _deps(ScriptedLLM([AIMessage(content="《静夜思》写的是思乡")]), registry)
    out = await agent_node({"resolved_input": "《静夜思》表达了什么", "messages": [], "iterations": 0})
    assert out["answer"] == "《静夜思》写的是思乡"
    assert out["iterations"] == 1
    assert len(out["messages"]) == 2  # seed(Human) + AI
    assert calls == []


@pytest.mark.asyncio
async def test_agent_keeps_seed_when_retrieved_present():
    registry, _ = make_registry()
    _deps(ScriptedLLM([AIMessage(content="答")]), registry)
    state = {
        "resolved_input": "这首诗什么意思",
        "messages": [],
        "iterations": 0,
        "retrieved": [
            {"source_type": "poem", "title": "静夜思", "text": "床前明月光", "score": 0.9, "id": 1}
        ],
    }
    out = await agent_node(state)
    seed = out["messages"][0]
    assert isinstance(seed, HumanMessage)
    assert "床前明月光" in seed.content and "这首诗什么意思" in seed.content


@pytest.mark.asyncio
async def test_agent_emits_tool_calls_without_answer():
    registry, _ = make_registry()
    _deps(ScriptedLLM([AIMessage(content="", tool_calls=[_tc()])]), registry)
    out = await agent_node({"resolved_input": "查静夜思", "messages": [], "iterations": 0})
    assert "answer" not in out          # 有 tool_calls 时不收敛
    assert out["messages"][-1].tool_calls


@pytest.mark.asyncio
async def test_tool_node_executes_and_records_trace():
    registry, calls = make_registry()
    _deps(ScriptedLLM([]), registry)
    out = await tool_node({"messages": [AIMessage(content="", tool_calls=[_tc()])]})
    assert calls == ["静夜思"]
    assert isinstance(out["messages"][0], ToolMessage)
    assert out["tool_trace"][0]["tool"] == "query_poem"
    assert out["tool_trace"][0]["status"] == "done"


def test_should_continue_routes_two_ways():
    registry, _ = make_registry()
    _deps(ScriptedLLM([]), registry)
    with_tools = {"messages": [AIMessage(content="", tool_calls=[_tc()])], "iterations": 1, "tokens_used": 10}
    assert should_continue(with_tools) == "tool_node"
    assert should_continue({"messages": [AIMessage(content="答")], "iterations": 1}) == "log"
    assert should_continue({}) == "log"


def test_should_continue_stops_at_iteration_limit():
    registry, _ = make_registry()
    _deps(ScriptedLLM([]), registry, workflow_max_iter=2)
    state = {"messages": [AIMessage(content="", tool_calls=[_tc()])], "iterations": 2}
    assert should_continue(state) == "log"


def test_should_continue_stops_at_token_limit():
    registry, _ = make_registry()
    _deps(ScriptedLLM([]), registry, workflow_max_tokens=100)
    state = {"messages": [AIMessage(content="", tool_calls=[_tc()])], "iterations": 1, "tokens_used": 100}
    assert should_continue(state) == "log"


@pytest.mark.asyncio
async def test_agent_force_converges_at_iteration_limit():
    registry, _ = make_registry()
    _deps(ScriptedLLM([AIMessage(content="", tool_calls=[_tc()]), AIMessage(content="强制作答")]), registry, workflow_max_iter=1)
    out = await agent_node({"resolved_input": "hi", "messages": [], "iterations": 0})
    assert out["iterations"] == 1
    assert out["fallback_reason"] == "max_iter"
    assert out["answer"] == "强制作答"
    assert out["messages"] == []   # 裸 tool_calls AI 不入状态(否则下轮回灌 400)


@pytest.mark.asyncio
async def test_agent_degrades_when_model_fails():
    registry, _ = make_registry()

    class BoomLLM(ScriptedLLM):
        async def ainvoke(self, messages):
            raise ConnectionError("upstream down")

    _deps(BoomLLM([]), registry)
    out = await agent_node({"resolved_input": "hi", "messages": [], "iterations": 0})
    assert out["fallback_reason"] == "agent_error"
    assert out["answer"]   # 有兜底话术,不是空
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_agent_react.py -q
```

Expected: FAIL,`ModuleNotFoundError: No module named 'workflow.agent_react'`。

- [ ] **Step 3: 实现 `workflow/agent_react.py`**

```python
"""主力 Agent 的 ReAct 子循环(LangGraph 版):agent 节点 → tool_node → 回到 agent。

与 `naive_agent.py`(无框架手写版)互为对照,两者停止判定语义一致(spec §6):
1. 响应不含 tool_calls → 自然收敛;
2. iterations 达上限 / tokens 达上限 → 强制收敛(丢弃裸 tool_calls AI,改发纯文本请求)。

工具集 = Ch02 三个诗词工具 + `submit_feedback`(见 spec §12 偏差留痕),本章不新增业务工具。
"""
import time

from langchain_core.messages import HumanMessage
from langchain_core.messages.utils import count_tokens_approximately

from tools.registry import make_tool_message
from workflow.deps import get_deps

_FORCE_ANSWER_HINT = "请直接根据目前已有的信息作答,不要再调用任何工具。"
_FORCE_ANSWER_FALLBACK = "信息比较多,我先说到这儿;如果你能再补充一点线索,我可以答得更准。"
_AGENT_ERROR_REPLY = "抱歉,我这会儿组织回答时出了点状况,要不换个说法再问我一次?"


def _seed_messages(state: dict) -> list:
    """首轮消息:知识类把检索到的原文片段与问题一并传入 Agent(spec §7)。"""
    question = state.get("resolved_input", "")
    retrieved = state.get("retrieved") or []
    if not retrieved:
        return [HumanMessage(content=question)]
    evidence = "\n\n".join(
        f"[{h.get('source_type', '')}|{h.get('title') or ''}] {h.get('text') or ''}".strip()
        for h in retrieved
    )
    return [HumanMessage(content=f"参考资料:\n{evidence}\n\n用户问题:{question}")]


async def agent_node(state: dict) -> dict:
    """主力 Agent:调 LLM(带工具),产出 tool_calls 或收敛答案。"""
    deps = get_deps()
    prev = list(state.get("messages") or [])
    seed = [] if prev else _seed_messages(state)   # 仅首轮播种
    msgs = prev + seed
    iterations = state.get("iterations", 0) + 1
    try:
        ai = await deps.llm.bind_tools(deps.registry.get_tools()).ainvoke(msgs)
    except Exception as exc:  # noqa: BLE001 - 模型失败降级兜底,不阻断整图
        print(f"[wf] agent fail: {str(exc)[:200]}")
        return {
            "messages": seed,
            "iterations": iterations,
            "answer": _AGENT_ERROR_REPLY,
            "fallback_reason": "agent_error",
        }
    msgs.append(ai)
    tokens_used = count_tokens_approximately(msgs)
    if ai.tool_calls and (iterations >= deps.max_iter or tokens_used >= deps.max_tokens):
        # 触上限:丢弃带 tool_calls 的裸 AI(无配对 ToolMessage 会让真实 API 400),改纯文本作答
        reason = "max_iter" if iterations >= deps.max_iter else "max_tokens"
        return {
            "messages": seed,
            "iterations": iterations,
            "tokens_used": tokens_used,
            "answer": await _force_answer(deps, msgs[:-1]),
            "fallback_reason": reason,
        }
    out: dict = {"messages": seed + [ai], "iterations": iterations, "tokens_used": tokens_used}
    if not ai.tool_calls:
        out["answer"] = ai.content or ""
    return out


async def tool_node(state: dict) -> dict:
    """工具节点:执行上一条 AI 的 tool_calls,回灌 ToolMessage 并记录轨迹(供 SSE/落库)。"""
    deps = get_deps()
    last = (state.get("messages") or [])[-1]
    tool_messages, traces = [], []
    for tc in getattr(last, "tool_calls", None) or []:
        started = time.monotonic()
        result = await deps.registry.execute(tc["name"], tc["args"])
        duration_ms = int((time.monotonic() - started) * 1000)
        tool_messages.append(make_tool_message(tc["id"], tc["name"], result))
        traces.append(
            {
                "tool": tc["name"],
                "args": tc["args"],
                "tool_call_id": tc["id"],
                "content": tool_messages[-1].content,
                "durationMs": duration_ms,
                "status": "done" if result.get("ok") else "error",
            }
        )
    return {"messages": tool_messages, "tool_trace": traces}


def should_continue(state: dict) -> str:
    """ReAct 条件边:有 tool_calls 且未触上限 → 工具节点;否则收敛到日志节点。"""
    deps = get_deps()
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if not getattr(last, "tool_calls", None):
        return "log"
    if state.get("iterations", 0) >= deps.max_iter or state.get("tokens_used", 0) >= deps.max_tokens:
        return "log"
    return "tool_node"


async def _force_answer(deps, messages: list) -> str:
    """不带工具再问一次逼出纯文本答案;失败也给兜底话术,保证收敛。"""
    try:
        forced = await deps.llm.ainvoke(messages + [HumanMessage(content=_FORCE_ANSWER_HINT)])
    except Exception as exc:  # noqa: BLE001
        print(f"[wf] force answer fail: {str(exc)[:200]}")
        return _FORCE_ANSWER_FALLBACK
    return forced.content or _FORCE_ANSWER_FALLBACK
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_agent_react.py -q
```

Expected: `9 passed`。

- [ ] **Step 5: 提交**

```powershell
git add potry-ai-agent/workflow/agent_react.py potry-ai-agent/tests/test_workflow_agent_react.py
git commit -m "feat(ch04): 主力 Agent ReAct 子循环与停止判定三条"
```

---

## Task 6: 提交反馈工具与 feedback 落库

**Files:**
- Create: `potry-ai-agent/app_storage.py`
- Create: `potry-ai-agent/tools/feedback_tool.py`
- Test: `potry-ai-agent/tests/test_feedback.py`

- [ ] **Step 1: 写失败测试**

`potry-ai-agent/tests/test_feedback.py`:

```python
"""feedback 表落库:列名映射(注意原表拼写 messsage / creatime)与行数 +1。"""
import asyncio

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app_storage import AppBase, AppStorage, Feedback


def _factory():
    engine = create_engine("sqlite:///:memory:")
    AppBase.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_feedback_columns_match_existing_table():
    # 原表列名拼写照抄:userid / messsage / creatime
    assert {c.name for c in Feedback.__table__.columns} == {"id", "userid", "messsage", "creatime"}


def test_add_feedback_appends_row():
    factory = _factory()
    storage = AppStorage(factory)
    with factory() as session:
        before = session.execute(select(func.count()).select_from(Feedback)).scalar()
    fid = storage.add_feedback("回答不准确,希望改进")
    assert fid is not None
    with factory() as session:
        after = session.execute(select(func.count()).select_from(Feedback)).scalar()
        row = session.get(Feedback, fid)
    assert after == before + 1
    assert row.messsage == "回答不准确,希望改进"
    assert row.userid is None            # 无登录态留空
    assert row.creatime is not None


def test_submit_feedback_tool_writes_through_engine(monkeypatch):
    """工具走真实 engine:把 load_settings 的 mysql_url 指向内存 sqlite 即可。"""
    import tools.feedback_tool as ft
    import db

    factory = _factory()
    monkeypatch.setattr(ft, "_storage_factory", lambda: factory, raising=False)
    result = asyncio.run(ft.submit_feedback.ainvoke({"content": "工单测试"}))
    assert result["ok"] is True and result["submitted"] is True
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_feedback.py -q
```

Expected: FAIL,`ModuleNotFoundError: No module named 'app_storage'`。

- [ ] **Step 3: 实现 `app_storage.py`**

```python
"""应用侧业务表映射:复用 Java 既有 `feedback` 表。

列名**原样照抄**库中已有定义(实测 `SHOW COLUMNS FROM feedback`):
`id` int PK auto_increment / `userid` int NULL / `messsage` text NULL /
`creatime` timestamp DEFAULT CURRENT_TIMESTAMP。`messsage` 与 `creatime` 的拼写即原文,
不得"顺手纠正",否则与线上表结构不一致。
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class AppBase(DeclarativeBase):
    pass


class Feedback(AppBase):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userid: Mapped[int | None] = mapped_column(Integer)
    messsage: Mapped[str | None] = mapped_column(Text)
    creatime: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.now)


class AppStorage:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._factory = session_factory

    def add_feedback(self, message: str, userid: int | None = None) -> int:
        """写一条反馈,返回新行 id(表已存在,create_all 幂等不重建)。"""
        with self._factory() as session:
            row = Feedback(userid=userid, messsage=message)
            session.add(row)
            session.commit()
            return row.id
```

- [ ] **Step 4: 实现 `tools/feedback_tool.py`**

```python
"""提交反馈工具:写 feedback 表。

⚠️ spec §12 偏差留痕:本工具**按用户决定注册给主力 Agent**;为降低"Agent 自行写库"
与需求第 8 条"后端不自动触发"的张力,工具描述里**显式约束**:仅当用户明确要求
提交反馈时才调用。验收③另行显式验证"未点击按钮时 feedback 行数不变"。
"""
from langchain_core.tools import tool
from sqlalchemy.orm import sessionmaker

from app_storage import AppStorage
from config import load_settings
from db import get_engine


def _storage_factory() -> sessionmaker:
    """单一入口:测试可 monkeypatch 本函数注入内存库。"""
    return sessionmaker(bind=get_engine(load_settings().mysql_url))


@tool
def submit_feedback(content: str) -> dict:
    """提交用户反馈到反馈表。

    **仅在用户明确要求"提交反馈""建工单""帮我记下来"时才调用**;
    用户只是表达不满、抱怨答错而没有要求提交时,**不得**调用本工具。

    Args:
        content: 用户反馈的原文内容
    """
    try:
        feedback_id = AppStorage(_storage_factory()).add_feedback(content)
    except Exception as exc:  # noqa: BLE001 - 统一走契约失败分支,不抛
        return {"ok": False, "error": str(exc)[:200]}
    return {"ok": True, "submitted": True, "feedbackId": feedback_id}
```

- [ ] **Step 5: 跑测试确认通过**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_feedback.py -q
```

Expected: `3 passed`。若 Step 1 的 `monkeypatch.setattr(ft, "_storage_factory", ...)` 因该函数不在模块命名空间而失败,请确认 `feedback_tool.py` 中确有 `_storage_factory` 顶层定义(上面 Step 4 即为此设计)。

- [ ] **Step 6: 提交**

```powershell
git add potry-ai-agent/app_storage.py potry-ai-agent/tools/feedback_tool.py potry-ai-agent/tests/test_feedback.py
git commit -m "feat(ch04): submit_feedback 工具与 feedback 表落库(列名原样照抄)"
```

---

## Task 7: 其余六节点与条件边判定

**Files:**
- Create: `potry-ai-agent/workflow/nodes.py`
- Test: `potry-ai-agent/tests/test_workflow_nodes.py`

- [ ] **Step 1: 写失败测试**

`potry-ai-agent/tests/test_workflow_nodes.py`:

```python
"""六个非 Agent 节点 + 条件边判定:透传 / 分类降级 / 硬编码分流 / 检索 / 闸 / 日志。"""
import pytest
from langchain_core.messages import AIMessage

from config import Settings
from prompts import CHITCHAT_REPLY, COMPLAINT_REPLY, FALLBACK_REPLY
from workflow import intent
from workflow.deps import WorkflowDeps, configure
from workflow.nodes import (
    after_gate,
    after_route,
    classify_node,
    gate_node,
    log_node,
    resolve_node,
    retrieve_node,
    route_node,
)


class ScriptedLLM:
    def __init__(self, reply="", boom=False):
        self.reply = reply
        self.boom = boom

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        if self.boom:
            raise ConnectionError("upstream down")
        return AIMessage(content=self.reply)


class FakeKnowledgeStorage:
    def __init__(self):
        self.pending = []
        self.chunks = {}

    def get_chunk(self, chunk_id):
        return self.chunks.get(chunk_id)

    def add_pending_question(self, question, session_id=None):
        self.pending.append((question, session_id))
        return len(self.pending)


class FakeChatStorage:
    def __init__(self):
        self.turns = []

    def persist_turn(self, session_id, rows):
        self.turns.append((session_id, rows))
        return 1


def make_settings(**over):
    base = dict(
        llm_base_url="http://fake", llm_api_key="CONFIGURE_LOCALLY", llm_model="fake",
        history_max_tokens=2000, llm_temperature=0.7,
        mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
        similarity_threshold=0.5,
    )
    base.update(over)
    return Settings(**base)


def _deps(llm=None, knowledge=None, chat=None, **over):
    deps = WorkflowDeps(make_settings(**over), llm or ScriptedLLM(), None, knowledge, chat)
    configure(deps)
    return deps


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    configure(None)


def test_resolve_node_passes_through():
    assert resolve_node({"user_input": "那首讲月亮的叫啥"}) == {
        "resolved_input": "那首讲月亮的叫啥"
    }


@pytest.mark.asyncio
async def test_classify_node_parses_json():
    _deps(ScriptedLLM(reply='{"intent": "find_poem"}'))
    assert await classify_node({"resolved_input": "找那首讲月亮的"}) == {"intent": "find_poem"}


@pytest.mark.asyncio
async def test_classify_node_degrades_on_bad_json():
    _deps(ScriptedLLM(reply="我觉得这是查诗人吧"))
    assert await classify_node({"resolved_input": "x"}) == {"intent": intent.DEFAULT_INTENT}


@pytest.mark.asyncio
async def test_classify_node_degrades_on_model_failure():
    _deps(ScriptedLLM(boom=True))
    assert await classify_node({"resolved_input": "x"}) == {"intent": intent.DEFAULT_INTENT}


def test_route_node_knowledge_and_business_do_not_answer():
    _deps()
    assert route_node({"intent": "poem_explain"}) == {"route": intent.ROUTE_KNOWLEDGE}
    assert route_node({"intent": "find_poet"}) == {"route": intent.ROUTE_BUSINESS}


def test_route_node_complaint_carries_two_independent_actions():
    out = route_node({"intent": "complaint"})
    assert out["route"] == intent.ROUTE_COMPLAINT
    assert out["answer"] == COMPLAINT_REPLY
    assert out["actions"] == ["handoff", "feedback"]   # 两个独立操作标识


def test_route_node_chitchat_uses_preset_reply():
    out = route_node({"intent": "chitchat"})
    assert out["route"] == intent.ROUTE_CHITCHAT
    assert out["answer"] == CHITCHAT_REPLY


def test_route_node_degrades_unknown_intent_to_chitchat():
    assert route_node({"intent": "no_such"})["route"] == intent.ROUTE_CHITCHAT


def test_after_route_branches():
    assert after_route({"route": intent.ROUTE_KNOWLEDGE}) == "retrieve"
    assert after_route({"route": intent.ROUTE_BUSINESS}) == "agent"
    assert after_route({"route": intent.ROUTE_COMPLAINT}) == "log"
    assert after_route({"route": intent.ROUTE_CHITCHAT}) == "log"


def test_retrieve_node_enriches_hit_with_text(monkeypatch):
    knowledge = FakeKnowledgeStorage()
    knowledge.chunks[7] = {"id": 7, "raw_text": "床前明月光,疑是地上霜。"}
    _deps(knowledge=knowledge)

    import workflow.nodes as nodesModule

    monkeypatch.setattr(
        nodesModule,
        "retrieve_evidence",
        lambda question, settings: ([{"id": 7, "score": 0.8, "source_type": "poem", "title": "静夜思"}], 0.8),
    )
    out = retrieve_node({"resolved_input": "静夜思什么意思"})
    assert out["evidence_score"] == 0.8
    assert out["retrieved"][0]["text"] == "床前明月光,疑是地上霜。"


def test_gate_node_passes_when_score_meets_threshold():
    _deps(similarity_threshold=0.5)
    assert gate_node({"evidence_score": 0.5})["gate_status"] == "pass"


def test_gate_node_falls_back_and_records_pending():
    knowledge = FakeKnowledgeStorage()
    _deps(knowledge=knowledge, similarity_threshold=0.5)
    out = gate_node({"evidence_score": 0.2, "user_input": "冷门问题", "session_id": "s1"})
    assert out["gate_status"] == "insufficient"
    assert out["answer"] == FALLBACK_REPLY
    assert out["fallback_reason"] == "insufficient_evidence"
    assert knowledge.pending == [("冷门问题", "s1")]


def test_after_gate_branches():
    assert after_gate({"gate_status": "pass"}) == "agent"
    assert after_gate({"gate_status": "insufficient"}) == "log"


def test_log_node_prints_structured_line_and_persists(capsys):
    chat = FakeChatStorage()
    _deps(chat=chat)
    state = {
        "session_id": "s1", "user_input": "《静夜思》是谁写的", "intent": "find_poet",
        "route": "business", "gate_status": "skip", "iterations": 2, "tokens_used": 321,
        "answer": "是李白", "started_at": 0.0,
        "tool_trace": [{"tool": "query_poet", "args": {"name": "李白"}, "tool_call_id": "c1", "content": "{}", "durationMs": 12, "status": "done"}],
    }
    log_node(state)
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert line.startswith("[wf] intent=find_poet route=business gate=skip score=- iters=2 tokens=321 elapsed=")
    session_id, rows = chat.turns[0]
    assert session_id == "s1"
    assert [r["role"] for r in rows] == ["user", "assistant", "tool", "assistant"]


def test_log_node_prints_score_when_retrieval_happened(capsys):
    _deps()
    log_node({"user_input": "x", "intent": "poem_explain", "route": "knowledge",
              "gate_status": "pass", "evidence_score": 0.8123, "iterations": 1, "tokens_used": 5})
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert "gate=pass score=0.8123" in line


def test_log_node_survives_storage_failure(capsys):
    class BoomChat:
        def persist_turn(self, session_id, rows):
            raise RuntimeError("mysql down")

    _deps(chat=BoomChat())
    log_node({"session_id": "s1", "user_input": "x", "answer": "y"})   # 不抛即通过
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_nodes.py -q
```

Expected: FAIL,`ModuleNotFoundError: No module named 'workflow.nodes'`。

- [ ] **Step 3: 实现 `workflow/nodes.py`**

```python
"""Ch04 七个节点中的其余六个 + 条件边判定。

指代消解 / 意图识别 / 意图分流 / 知识检索 / 置信度闸 / 日志记录 在此;
主力 Agent 与工具节点在 `agent_react.py`(ReAct 子循环)。

日志记录节点输出**一行结构化日志**(spec §9),格式固定为验收观测点:
`[wf] intent=<意图> route=<出口> gate=<pass|insufficient|skip> score=<相似度或-> iters=<迭代数> tokens=<token数> elapsed=<毫秒>`
"""
import time

from prompts import CHITCHAT_REPLY, COMPLAINT_REPLY, FALLBACK_REPLY, INTENT_PROMPT
from workflow.confidence import is_evidence_sufficient, retrieve_evidence
from workflow.deps import get_deps
from workflow.intent import (
    DEFAULT_INTENT,
    INTENT_TO_ROUTE,
    ROUTE_BUSINESS,
    ROUTE_CHITCHAT,
    ROUTE_COMPLAINT,
    ROUTE_KNOWLEDGE,
    parse_intent,
)


def resolve_node(state: dict) -> dict:
    """指代消解(本章最简版:直接透传,不做额外处理;正式优化留待后续迭代)。"""
    return {"resolved_input": state["user_input"]}


async def classify_node(state: dict) -> dict:
    """意图识别(最简版):Prompt 输出严格 JSON;解析失败/模型失败 → 降级 chitchat 并告警。"""
    deps = get_deps()
    try:
        message = await deps.llm.ainvoke(INTENT_PROMPT.invoke({"question": state["resolved_input"]}))
        label = parse_intent(message.content or "")
    except Exception as exc:  # noqa: BLE001 - 分类失败不阻断流程
        print(f"[wf] classify fail, degrade to {DEFAULT_INTENT}: {str(exc)[:200]}")
        label = DEFAULT_INTENT
    return {"intent": label}


def route_node(state: dict) -> dict:
    """意图分流:硬编码查表得出口;投诉/闲聊直接落预设话术(不调模型、不调工具)。"""
    route = INTENT_TO_ROUTE.get(state.get("intent", DEFAULT_INTENT), ROUTE_CHITCHAT)
    out: dict = {"route": route}
    if route == ROUTE_COMPLAINT:
        out["answer"] = COMPLAINT_REPLY
        out["actions"] = ["handoff", "feedback"]
    elif route == ROUTE_CHITCHAT:
        out["answer"] = CHITCHAT_REPLY
    return out


def retrieve_node(state: dict) -> dict:
    """知识检索:三源各取 top-k 合并,并回查权威原文片段一并带给 Agent。"""
    deps = get_deps()
    hits, score = retrieve_evidence(state["resolved_input"], deps.settings)
    enriched = []
    for hit in hits:
        chunk = deps.knowledge_storage.get_chunk(hit["id"]) if deps.knowledge_storage else None
        text = (chunk.get("raw_text") or chunk.get("chunk_text") or "") if chunk else ""
        enriched.append({**hit, "text": text})
    print(f"[wf] retrieve n={len(hits)} top={score:.4f}")
    return {"retrieved": enriched, "evidence_score": score}


def gate_node(state: dict) -> dict:
    """置信度闸(仅知识类、进 Agent 之前):证据不足 → 兜底话术 + 记录待处理问题。"""
    deps = get_deps()
    score = state.get("evidence_score", 0.0)
    if is_evidence_sufficient(score, deps.settings.similarity_threshold):
        return {"gate_status": "pass"}
    try:
        if deps.knowledge_storage is not None:
            deps.knowledge_storage.add_pending_question(
                state.get("user_input", ""), state.get("session_id")
            )
    except Exception as exc:  # noqa: BLE001 - 记录失败只告警,不阻断兜底
        print(f"[wf] pending write fail: {str(exc)[:200]}")
    return {
        "gate_status": "insufficient",
        "answer": FALLBACK_REPLY,
        "fallback_reason": "insufficient_evidence",
    }


def log_node(state: dict) -> dict:
    """日志记录:一行结构化日志(验收观测点)+ 沿用 Ch02 把本轮落 messages 表。"""
    elapsed = int((time.monotonic() - state.get("started_at", time.monotonic())) * 1000)
    score = state.get("evidence_score")
    score_text = f"{score:.4f}" if score is not None else "-"
    print(
        f"[wf] intent={state.get('intent', '-')} route={state.get('route', '-')} "
        f"gate={state.get('gate_status', 'skip')} score={score_text} "
        f"iters={state.get('iterations', 0)} tokens={state.get('tokens_used', 0)} elapsed={elapsed}"
    )
    _persist_turn(state)
    return {}


def _persist_turn(state: dict) -> None:
    """把本轮对话落 messages 表(user / assistant(tool_calls) / tool / assistant 四段式)。"""
    deps = get_deps()
    if deps.chat_storage is None:
        return
    rows: list[dict] = [{"role": "user", "content": state.get("user_input", "")}]
    for trace in state.get("tool_trace") or []:
        rows.append(
            {
                "role": "assistant",
                "content": "",
                "tool_name": trace["tool"],
                "tool_call_id": trace.get("tool_call_id"),
                "tool_args": trace.get("args"),
            }
        )
        rows.append(
            {
                "role": "tool",
                "content": trace.get("content", ""),
                "tool_name": trace["tool"],
                "tool_call_id": trace.get("tool_call_id"),
            }
        )
    rows.append({"role": "assistant", "content": state.get("answer", "")})
    try:
        deps.chat_storage.persist_turn(state.get("session_id", ""), rows)
    except Exception as exc:  # noqa: BLE001 - 落库失败不打断对话
        print(f"[wf] storage fail: {str(exc)[:200]}")


def after_route(state: dict) -> str:
    """分流条件边:知识类→检索;业务类→Agent;投诉/闲聊→直接日志收尾(答案已就位)。"""
    route = state.get("route", ROUTE_CHITCHAT)
    if route == ROUTE_KNOWLEDGE:
        return "retrieve"
    if route == ROUTE_BUSINESS:
        return "agent"
    return "log"


def after_gate(state: dict) -> str:
    """闸后条件边:证据足→Agent;不足→日志收尾(答案已是兜底话术)。"""
    return "agent" if state.get("gate_status") == "pass" else "log"
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_nodes.py -q
```

Expected: `16 passed`。

- [ ] **Step 5: 提交**

```powershell
git add potry-ai-agent/workflow/nodes.py potry-ai-agent/tests/test_workflow_nodes.py
git commit -m "feat(ch04): 六节点实现与条件边判定(分流/闸/结构化日志落库)"
```

---

## Task 8: 图装配与 checkpointer

**Files:**
- Create: `potry-ai-agent/workflow/graph.py`
- Test: `potry-ai-agent/tests/test_workflow_graph.py`

- [ ] **Step 1: 写失败测试**

`potry-ai-agent/tests/test_workflow_graph.py`:

```python
"""图装配:可编译、节点齐备、四种出口各走对分支、ReAct 循环 > 1 轮、checkpointer 落盘。"""
import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from config import Settings
from prompts import CHITCHAT_REPLY, COMPLAINT_REPLY, FALLBACK_REPLY
from tools.registry import ToolRegistry
from workflow import intent
from workflow.deps import WorkflowDeps, configure
from workflow.graph import build_graph, open_checkpointer


class ScriptedLLM:
    """按脚本吐 AIMessage;取空后返回固定收敛文本。"""

    def __init__(self, script=None, default="默认收敛"):
        self.script = list(script or [])
        self.default = default

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        if self.script:
            return self.script.pop(0)
        return AIMessage(content=self.default)


class FakeKnowledgeStorage:
    def __init__(self, chunks=None):
        self.chunks = chunks or {}
        self.pending = []

    def get_chunk(self, chunk_id):
        return self.chunks.get(chunk_id)

    def add_pending_question(self, question, session_id=None):
        self.pending.append((question, session_id))
        return len(self.pending)


class FakeChatStorage:
    def __init__(self):
        self.turns = []

    def persist_turn(self, session_id, rows):
        self.turns.append((session_id, rows))
        return 1


def make_settings(**over):
    base = dict(
        llm_base_url="http://fake", llm_api_key="CONFIGURE_LOCALLY", llm_model="fake",
        history_max_tokens=2000, llm_temperature=0.7,
        mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
        similarity_threshold=0.5,
    )
    base.update(over)
    return Settings(**base)


def make_registry():
    calls = []

    @tool
    def query_poet(name: str) -> dict:
        """查诗人。

        Args:
            name: 诗人名
        """
        calls.append(name)
        return {"ok": True, "found": True, "poet": {"name": "李白"}}

    registry = ToolRegistry(timeout=5.0, max_retries=0)
    registry.register(query_poet)
    return registry, calls


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    configure(None)


def _wire(llm, registry, knowledge=None, chat=None, **over):
    deps = WorkflowDeps(make_settings(**over), llm, registry, knowledge, chat)
    configure(deps)
    return deps


async def _run(graph, message, session_id="s1", **extra):
    return await graph.ainvoke(
        {"session_id": session_id, "user_input": message, "started_at": 0.0,
         "messages": [], "tool_trace": [], **extra},
        config={"configurable": {"thread_id": session_id}},
    )


def test_graph_builds_and_has_all_nodes():
    registry, _ = make_registry()
    _wire(ScriptedLLM(), registry)
    graph = build_graph(InMemorySaver())
    nodes = set(graph.get_graph().nodes)
    assert {"resolve", "classify", "route", "retrieve", "gate", "agent", "tool_node", "log"} <= nodes


@pytest.mark.asyncio
async def test_chitchat_outlet_uses_preset_reply_and_no_tools():
    registry, calls = make_registry()
    _wire(ScriptedLLM([AIMessage(content='{"intent": "chitchat"}')]), registry, chat=FakeChatStorage())
    graph = build_graph(InMemorySaver())
    final = await _run(graph, "今天天气不错")
    assert final["route"] == intent.ROUTE_CHITCHAT
    assert final["answer"] == CHITCHAT_REPLY
    assert final.get("tool_trace", []) == []
    assert final.get("iterations", 0) == 0     # 未进 Agent
    assert calls == []


@pytest.mark.asyncio
async def test_complaint_outlet_carries_two_actions_and_skips_agent():
    registry, _ = make_registry()
    _wire(ScriptedLLM([AIMessage(content='{"intent": "complaint"}')]), registry, chat=FakeChatStorage())
    final = await _run(build_graph(InMemorySaver()), "答得不对,我不满意")
    assert final["route"] == intent.ROUTE_COMPLAINT
    assert final["answer"] == COMPLAINT_REPLY
    assert final["actions"] == ["handoff", "feedback"]
    assert final.get("iterations", 0) == 0


@pytest.mark.asyncio
async def test_business_outlet_agent_calls_tool():
    registry, calls = make_registry()
    llm = ScriptedLLM([
        AIMessage(content='{"intent": "find_poet"}'),
        AIMessage(content="", tool_calls=[{"name": "query_poet", "args": {"name": "李白"}, "id": "c1", "type": "tool_call"}]),
        AIMessage(content="李白是唐代诗人"),
    ])
    _wire(llm, registry, chat=FakeChatStorage())
    final = await _run(build_graph(InMemorySaver()), "李白是什么朝代的")
    assert final["route"] == intent.ROUTE_BUSINESS
    assert calls == ["李白"]                                  # Agent 自主调工具
    assert final["iterations"] == 2                           # ReAct 迭代 > 1 轮
    assert final["answer"] == "李白是唐代诗人"
    assert final["tool_trace"][0]["tool"] == "query_poet"


@pytest.mark.asyncio
async def test_knowledge_outlet_retrieves_then_agent(monkeypatch):
    registry, _ = make_registry()
    knowledge = FakeKnowledgeStorage(chunks={1: {"id": 1, "raw_text": "床前明月光"}})
    _wire(ScriptedLLM([AIMessage(content='{"intent": "poem_explain"}'), AIMessage(content="写的是思乡")]),
          registry, knowledge=knowledge, chat=FakeChatStorage())

    import workflow.nodes as nodes_module
    monkeypatch.setattr(
        nodes_module, "retrieve_evidence",
        lambda question, settings: ([{"id": 1, "score": 0.9, "source_type": "poem", "title": "静夜思"}], 0.9),
    )
    final = await _run(build_graph(InMemorySaver()), "《静夜思》表达了什么感情")
    assert final["route"] == intent.ROUTE_KNOWLEDGE
    assert final["gate_status"] == "pass"
    assert final["evidence_score"] == 0.9
    assert final["answer"] == "写的是思乡"
    assert final["retrieved"][0]["text"] == "床前明月光"


@pytest.mark.asyncio
async def test_knowledge_gate_blocks_agent_when_evidence_insufficient(monkeypatch):
    registry, calls = make_registry()
    knowledge = FakeKnowledgeStorage()
    _wire(ScriptedLLM([AIMessage(content='{"intent": "reference_lookup"}')]), registry,
          knowledge=knowledge, chat=FakeChatStorage())

    import workflow.nodes as nodes_module
    monkeypatch.setattr(
        nodes_module, "retrieve_evidence",
        lambda question, settings: ([{"id": 9, "score": 0.1, "source_type": "poem"}], 0.1),
    )
    final = await _run(build_graph(InMemorySaver()), "这句出自哪首冷门诗")
    assert final["gate_status"] == "insufficient"
    assert final["answer"] == FALLBACK_REPLY
    assert final["fallback_reason"] == "insufficient_evidence"
    assert final.get("iterations", 0) == 0                      # 未进 Agent
    assert knowledge.pending == [("这句出自哪首冷门诗", "s1")]   # 已记录待处理


@pytest.mark.asyncio
async def test_checkpointer_persists_state_across_turns():
    """同 thread_id 二轮调用:首轮状态仍在 checkpointer 里(持久化生效)。"""
    registry, _ = make_registry()
    _wire(ScriptedLLM([AIMessage(content='{"intent": "chitchat"}'), AIMessage(content='{"intent": "chitchat"}')]),
          registry, chat=FakeChatStorage())
    saver, conn = await open_checkpointer(":memory:")
    try:
        graph = build_graph(saver)
        await _run(graph, "第一轮", session_id="thread-x")
        await _run(graph, "第二轮", session_id="thread-x")
        state = await graph.aget_state(config={"configurable": {"thread_id": "thread-x"}})
        assert state.values["user_input"] == "第二轮"
        assert state.values["route"] == intent.ROUTE_CHITCHAT
    finally:
        await conn.close()
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_graph.py -q
```

Expected: FAIL,`ModuleNotFoundError: No module named 'workflow.graph'`。

- [ ] **Step 3: 实现 `workflow/graph.py`**

```python
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
    after_route,
    classify_node,
    gate_node,
    log_node,
    resolve_node,
    retrieve_node,
    route_node,
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
    saver = AsyncSqliteSaver(conn)
    await saver.setup()
    return saver, conn


def build_graph(checkpointer):
    """按固定顺序装配并编译(spec §3.1)。"""
    builder = StateGraph(WorkflowState)
    builder.add_node("resolve", resolve_node)
    builder.add_node("classify", classify_node)
    builder.add_node("route", route_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("gate", gate_node)
    builder.add_node("agent", agent_node)
    builder.add_node("tool_node", tool_node)
    builder.add_node("log", log_node)

    builder.add_edge(START, "resolve")
    builder.add_edge("resolve", "classify")
    builder.add_edge("classify", "route")
    builder.add_conditional_edges(
        "route", after_route, {"retrieve": "retrieve", "agent": "agent", "log": "log"}
    )
    builder.add_edge("retrieve", "gate")
    builder.add_conditional_edges("gate", after_gate, {"agent": "agent", "log": "log"})
    builder.add_conditional_edges(
        "agent", should_continue, {"tool_node": "tool_node", "log": "log"}
    )
    builder.add_edge("tool_node", "agent")   # ReAct 子循环:工具执行后回到 Agent
    builder.add_edge("log", END)
    return builder.compile(checkpointer=checkpointer)
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_graph.py -q
```

Expected: `8 passed`。

- [ ] **Step 5: 提交**

```powershell
git add potry-ai-agent/workflow/graph.py potry-ai-agent/tests/test_workflow_graph.py
git commit -m "feat(ch04): 图骨架装配与 AsyncSqliteSaver checkpointer"
```

---

## Task 9: main.py 接线(两个新接口 + 生命周期)

**Files:**
- Modify: `potry-ai-agent/main.py`
- Test: `potry-ai-agent/tests/test_workflow_endpoint.py`

- [ ] **Step 1: 写失败测试**

`potry-ai-agent/tests/test_workflow_endpoint.py`:

```python
"""Ch04 两个新接口的 SSE 契约与落库行为。"""
import json

from fastapi.testclient import TestClient

import main


class FakeWorkflow:
    def __init__(self, final):
        self.final = final
        self.records = []

    async def ainvoke(self, payload, config):
        self.records.append((payload, config))
        return self.final


def _client(monkeypatch, final):
    fake = FakeWorkflow(final)
    monkeypatch.setattr(main, "_workflow", fake)
    return TestClient(main.app), fake


def test_workflow_sse_sequence_with_action(monkeypatch):
    final = {
        "route": "complaint", "answer": COMPLAINT := "抱歉,让你有不好的体验了。",
        "actions": ["handoff", "feedback"],
        "tool_trace": [{"tool": "query_poet", "args": {"name": "李白"}, "tool_call_id": "c1",
                        "content": "{}", "durationMs": 12, "status": "done"}],
    }
    client, fake = _client(monkeypatch, final)
    with client.stream("POST", "/agent/workflow", json={"sessionId": "s1", "message": "我要投诉"}) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())
    order = [body.index(f"event: {e}") for e in ("meta", "tool_status", "token", "action", "done")]
    assert order == sorted(order)                # 顺序契约
    assert '"actions": ["handoff", "feedback"]' in body
    assert json.dumps({"sessionId": "s1"}, ensure_ascii=False) in body
    assert fake.records[0][1] == {"configurable": {"thread_id": "s1"}}


def test_workflow_plain_answer_has_no_action_event(monkeypatch):
    client, _ = _client(monkeypatch, {"route": "business", "answer": "是李白", "actions": []})
    with client.stream("POST", "/agent/workflow", json={"sessionId": "s2", "message": "谁写的"}) as resp:
        body = "".join(resp.iter_text())
    assert "event: token" in body and "event: action" not in body and "event: done" in body


def test_workflow_returns_503_when_not_ready(monkeypatch):
    monkeypatch.setattr(main, "_workflow", None)
    client = TestClient(main.app)
    assert client.post("/agent/workflow", json={"message": "hi"}).status_code == 503


def test_workflow_midstream_failure_emits_error_event(monkeypatch):
    class BoomWorkflow:
        async def ainvoke(self, payload, config):
            raise RuntimeError("graph exploded")

    monkeypatch.setattr(main, "_workflow", BoomWorkflow())
    client = TestClient(main.app)
    with client.stream("POST", "/agent/workflow", json={"sessionId": "s3", "message": "hi"}) as resp:
        body = "".join(resp.iter_text())
    assert "event: error" in body
    assert "event: done" in body          # 收尾仍补 done,契约不缺帧


def test_feedback_endpoint_writes_row(monkeypatch):
    captured = {}

    def fake_add_feedback(message, userid=None):
        captured["message"] = message
        captured["userid"] = userid
        return 42

    monkeypatch.setattr(main.app_storage, "add_feedback", fake_add_feedback)
    client = TestClient(main.app)
    resp = client.post("/agent/feedback", json={"sessionId": "s1", "message": "工单内容"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "feedbackId": 42}
    assert captured["message"] == "工单内容"


def test_feedback_endpoint_maps_numeric_userid(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        main.app_storage, "add_feedback",
        lambda message, userid=None: seen.setdefault("userid", userid) or 1,
    )
    client = TestClient(main.app)
    client.post("/agent/feedback", json={"userId": "1001", "message": "x"})
    assert seen["userid"] == 1001
    client.post("/agent/feedback", json={"userId": "not-a-number", "message": "x"})
    assert seen["userid"] is None
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workflow_endpoint.py -q
```

Expected: FAIL(404 / `AttributeError: module 'main' has no attribute '_workflow'`)。

- [ ] **Step 3: 改 `main.py` 导入与 `init_db`**

(a) 头部导入区追加:

```python
import time
from app_storage import AppBase, AppStorage
from chat_service import ChatService, build_llm
from knowledge import KnowledgeBase, KnowledgeStorage
from tools.feedback_tool import submit_feedback
from workflow.deps import WorkflowDeps, configure as configure_workflow
from workflow.graph import DEFAULT_CHECKPOINT_PATH, build_graph, open_checkpointer
```

(b) `init_db` 里 `ChatBase.metadata.create_all(target_engine)` 之后、`KnowledgeBase.metadata.create_all(target_engine)` 之前插入 `AppBase.metadata.create_all(target_engine)`;并把提示行改成:

```python
        print("[db] 表结构就绪(对话 + 知识库 + 应用表)")
```

- [ ] **Step 4: 模块级装配与生命周期**

在 `service = ChatService(...)` 那行之后追加:

```python
# Ch04 编排装配:LLM/工具/知识库/落库依赖注入 workflow 节点(见 spec §3.2)
app_storage = AppStorage(session_factory)
knowledge_storage = KnowledgeStorage(session_factory)
registry.register(submit_feedback)   # 用户决定:注册给主力 Agent(偏差留痕 spec §12)
workflow_llm = build_llm(settings)
configure_workflow(
    WorkflowDeps(settings, workflow_llm, registry, knowledge_storage, storage)
)
_workflow = None            # 编译产物,由 lifespan 打开 checkpointer 后填充
_checkpoint_conn = None     # aiosqlite 连接,关闭时回收
```

在 `lifespan` 的 `yield` 之前(紧接 Nacos 注册那段之后)插入:

```python
    global _workflow, _checkpoint_conn
    try:
        saver, _checkpoint_conn = await open_checkpointer(settings.workflow_checkpoint_path)
        _workflow = build_graph(saver)
        print(f"[wf] 图已编译(checkpointer=sqlite:{settings.workflow_checkpoint_path})")
    except Exception as exc:  # noqa: BLE001 - 装配失败降级:接口 503,服务照常起
        _workflow = None
        print(f"[wf] 图装配失败(接口将 503): {str(exc)[:200]}")
```

在 `lifespan` 的 `yield` 之后、`scheduler.shutdown` 那段之前插入:

```python
    if _checkpoint_conn is not None:
        try:
            await _checkpoint_conn.close()
            print("[wf] checkpointer 连接已关闭")
        except Exception as exc:  # noqa: BLE001
            print(f"[wf] checkpointer 关闭失败: {str(exc)[:200]}")
```

- [ ] **Step 5: 新增两个接口**

在 `chat` 接口之后追加:

```python
class FeedbackRequest(BaseModel):
    userId: str | None = None
    sessionId: str | None = None
    message: str


def _answer_chunks(text: str, size: int = 8):
    """把整段答案切小块作 token 帧,保留打字机观感。"""
    for start in range(0, len(text), size):
        yield text[start : start + size]


@app.post("/agent/workflow")
async def workflow_chat(req: ChatRequest) -> EventSourceResponse:
    """Ch04 确定性编排入口:meta → tool_status* → token* → action? → done。

    与原 `/agent/chat` 并行存在(原接口不动,保证 Ch01–Ch03 回归不受影响)。
    """
    if _workflow is None:
        raise HTTPException(status_code=503, detail={"message": "workflow 未就绪(装配失败)"})
    session_id = req.sessionId or uuid4().hex
    config = {"configurable": {"thread_id": session_id}}

    async def gen() -> AsyncIterator[bytes]:
        yield _sse("meta", {"sessionId": session_id})
        try:
            final = await _workflow.ainvoke(
                {
                    "session_id": session_id,
                    "user_input": req.message,
                    "started_at": time.monotonic(),
                    "messages": [],
                    "tool_trace": [],
                },
                config=config,
            )
            for trace in final.get("tool_trace") or []:
                yield _sse(
                    "tool_status",
                    {
                        "tool": trace["tool"],
                        "status": trace["status"],
                        "args": trace["args"],
                        "durationMs": trace["durationMs"],
                    },
                )
            for piece in _answer_chunks(final.get("answer") or ""):
                yield _sse("token", {"content": piece})
            actions = final.get("actions") or []
            if actions:
                yield _sse("action", {"actions": actions})
        except Exception as exc:  # noqa: BLE001 - 单请求失败不崩服务,补 error 帧
            yield _sse("error", {"message": str(exc)[:200]})
        yield _sse("done", {"sessionId": session_id, "source": _answer_source(final if "final" in dir() else {})})

    return EventSourceResponse(gen())


def _answer_source(final: dict) -> str:
    """回答来源标识别:投诉/闲聊=预设话术;兜底=未查到;有工具=查库;否则=模型知识。"""
    if final.get("route") in ("complaint", "chitchat"):
        return "preset"
    if final.get("fallback_reason"):
        return "fallback"
    return "tool" if final.get("tool_trace") else "model"


@app.post("/agent/feedback")
def agent_feedback(req: FeedbackRequest) -> dict:
    """建工单落点:写 feedback 表(前端「提交反馈」按钮调用;后端不自动触发)。"""
    userid = int(req.userId) if req.userId and req.userId.isdigit() else None
    try:
        feedback_id = app_storage.add_feedback(req.message, userid=userid)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"message": str(exc)[:200]})
    return {"ok": True, "feedbackId": feedback_id}
```

> ⚠️ `dir()` 那行是坏味道,请**改为在 `try` 前先初始化**:

```python
    async def gen() -> AsyncIterator[bytes]:
        yield _sse("meta", {"sessionId": session_id})
        final: dict = {}
        try:
            final = await _workflow.ainvoke(...)
            ...
        except Exception as exc:
            yield _sse("error", {"message": str(exc)[:200]})
        yield _sse("done", {"sessionId": session_id, "source": _answer_source(final)})
```

- [ ] **Step 6: 跑测试 + 全量回归**

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Expected: 全绿,总数 = 138(T1 后基数)+ 本项目新增用例。`test_startup.py` 必须依旧通过(lifespan 多出的 checkpointer 装配走 `:memory:`,失败也不阻断)。

- [ ] **Step 7: 提交**

```powershell
git add potry-ai-agent/main.py potry-ai-agent/tests/test_workflow_endpoint.py
git commit -m "feat(ch04): 接线 /agent/workflow 与 /agent/feedback 及图生命周期"
```

---

## Task 10: 前端两个独立按钮(Vibe Coding 例外)

**说明:** 前端属 Vibe Coding 例外(不套 brainstorm/TDD/code review),做法与原 Ch01/Ch02 一致:直接改 `static/chat.html`,人工在浏览器验证。

**Files:**
- Modify: `potry-ai-agent/static/chat.html`

- [ ] **Step 1: 补按钮样式**

在 `.source-detail .kv b { ... }` 之后追加:

```css
  .actions { display: flex; gap: 8px; margin-top: 8px; }
  .action-btn {
    border: 1px solid var(--gold);
    background: rgba(184, 134, 59, .12);
    color: var(--gold);
    padding: 6px 16px;
    border-radius: 8px;
    font-size: 13px;
    letter-spacing: 2px;
    cursor: pointer;
  }
  .action-btn:hover { opacity: .85; }
  .action-btn:disabled { opacity: .4; cursor: default; }
```

- [ ] **Step 2: 脚本改造(改端点 + action 事件 + 两按钮)**

在 `const TOOL_LABELS = {...};` 之后追加:

```js
  // 可选操作的中文名(与后端 action 标识一一对应)
  const ACTION_LABELS = { handoff: "转人工", feedback: "提交反馈" };
  let lastUserText = "";   // 供「提交反馈」落库用
```

把 `fetch("/agent/chat", {` 改为 `fetch("/agent/workflow", {`。

在 `send()` 里 `addRow("user", text);` 之后追加:

```js
    lastUserText = text;
```

在 SSE 事件循环里 `else if (event === "error")` 那一支之前插入:

```js
          } else if (event === "action") {
            renderActions(bubble.parentElement, payload.actions || []);
```

在 `send()` 之前追加两个函数:

```js
  // 「转人工」「提交反馈」两个独立按钮:互不绑定,点击结果各自独立
  function renderActions(container, actions) {
    const existing = container.querySelector(".actions");
    if (existing) existing.remove();
    const wrap = document.createElement("div");
    wrap.className = "actions";
    actions.forEach((action) => {
      const btn = document.createElement("button");
      btn.className = "action-btn";
      btn.textContent = ACTION_LABELS[action] || action;
      btn.addEventListener("click", () => handleAction(action, btn));
      wrap.appendChild(btn);
    });
    container.appendChild(wrap);
  }

  async function handleAction(action, btn) {
    btn.disabled = true;
    if (action === "handoff") {
      // 纯前端模拟:不对接真人客服,仅展示转接提示 + 青莲版问候
      addRow("assistant", "已转接人工客服\n\n您好,我是青莲,请问有什么可以帮您的");
      return;
    }
    if (action === "feedback") {
      try {
        const resp = await fetch("/agent/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sessionId: sessionId, message: lastUserText }),
        });
        if (!resp.ok) throw new Error("提交失败 " + resp.status);
        addRow("assistant", "已提交,感谢反馈。");
      } catch (e) {
        addRow("assistant", "反馈提交失败:" + e.message);
      }
    }
  }
```

在 `send()` 收尾处,把 `renderSource(bubble, toolCalls);` 之后追加按 `done` 的 `source` 定格来源标识:

```js
          } else if (event === "done") {
            renderSourceBySource(bubble, payload.source, toolCalls);
```

并在文件里新增:

```js
  // 按后端给出的来源标识定格 chip:preset/fallback/tool/model
  function renderSourceBySource(bubble, source, toolCalls) {
    if (!source) { renderSource(bubble, toolCalls); return; }
    const { chip, detail } = ensureSourceEls(bubble);
    const text = chip.querySelector(".text");
    chip.classList.remove("db", "mind", "error");
    if (source === "preset") {
      chip.classList.add("mind");
      text.textContent = "预设话术 · 未调模型";
      detail.innerHTML = '<div class="kv">这轮走的是固定话术,没有调用模型与工具。</div>';
    } else if (source === "fallback") {
      chip.classList.add("error");
      text.textContent = "资料不足 · 已转兜底";
      detail.innerHTML = '<div class="kv">检索证据不足,已给出兜底答复并记入待处理问题。</div>';
    } else if (source === "tool") {
      renderSource(bubble, toolCalls);
    } else {
      chip.classList.add("mind");
      text.textContent = "凭模型知识作答 · 未查库";
      detail.innerHTML = '<div class="kv">这轮没有调用查询工具,回答来自模型自身知识,可能不准确。</div>';
    }
  }
```

> 注意:原 `send()` 里最后那行 `renderSource(bubble, toolCalls);` 保留不动(流结束的兜底);`done` 帧若带 `source` 则以其为准覆盖。

- [ ] **Step 3: 人工验证**

启动服务(见 T12 Step 1 命令),浏览器打开 `http://127.0.0.1:8000/chat`,发送「答得不对,我不满意」:
- 回答下方出现**两个独立按钮**;
- 点「转人工」→ 出现「已转接人工客服」+「您好,我是青莲,请问有什么可以帮您的」;
- 点「提交反馈」→ 提示「已提交,感谢反馈。」,且 `SELECT COUNT(*) FROM feedback` +1;
- **不点按钮直接继续发消息 → 对话正常推进,feedback 行数不变**。

- [ ] **Step 4: 提交**

```powershell
git add potry-ai-agent/static/chat.html
git commit -m "feat(ch04): 聊天页接入 workflow 端点并渲染转人工/提交反馈两个独立按钮"
```

---

## Task 11: 意图识别评估集(纯 Prompt 类,替代 TDD)

**说明:** 按用户工作要求 1,纯 Prompt 类任务把 TDD 环节替换为**标注样例/评估集跑通验证**。七类各 3 句共 21 条人工标注样例,跑真实模型比对准确率。

- [ ] **Step 1: 跑评估集(真实模型,需 .env 可用)**

```powershell
.\.venv\Scripts\python.exe -c @"
import asyncio
from config import load_settings
from chat_service import build_llm
from prompts import INTENT_PROMPT
from workflow.intent import parse_intent

SAMPLES = [
    ('《静夜思》表达了什么感情', 'poem_explain'),
    ('这首诗是什么意思', 'poem_explain'),
    ('帮我赏析一下《春望》', 'poem_explain'),
    ('举头望明月出自哪首诗', 'reference_lookup'),
    ('这两个字出自哪个典故', 'reference_lookup'),
    ('这句诗的出处是哪里', 'reference_lookup'),
    ('那首讲月亮的叫啥', 'find_poem'),
    ('帮我找一首写思乡的诗', 'find_poem'),
    ('有没有写梅花的诗', 'find_poem'),
    ('李白是什么朝代的', 'find_poet'),
    ('介绍一下杜甫', 'find_poet'),
    ('苏轼写过哪些名篇', 'find_poet'),
    ('唐代有哪些著名的诗', 'find_dynasty'),
    ('宋朝的词人都有谁', 'find_dynasty'),
    ('元曲有哪些代表作', 'find_dynasty'),
    ('答得不对,我不满意', 'complaint'),
    ('你搞错了吧', 'complaint'),
    ('这个答案有误', 'complaint'),
    ('今天天气不错', 'chitchat'),
    ('你叫什么名字', 'chitchat'),
    ('讲个笑话吧', 'chitchat'),
]

async def main():
    settings = load_settings()
    llm = build_llm(settings)
    ok = 0
    for text, expected in SAMPLES:
        msg = await llm.ainvoke(INTENT_PROMPT.invoke({'question': text}))
        got = parse_intent(msg.content or '')
        hit = got == expected
        ok += int(hit)
        print(('  OK ' if hit else '  NG ') + f'{text} -> {got} (期望 {expected})')
    print(f'准确率 {ok}/{len(SAMPLES)} = {ok/len(SAMPLES):.1%}')

asyncio.run(main())
"@
```

Expected: 准确率 **≥ 90%**。把完整输出(每行 + 准确率)原样贴进 `dev-notes/ch04.md`。

- [ ] **Step 2: 处理偏差(若有)**

若个别样例判错且属**边界模糊**(如"元曲有哪些代表作"被判 `find_poem`),记录进 dev-notes 的"翻车与返工",**修正标注**而非改代码(标注口径问题);若**同类系统性错判**(如 3 条 `reference_lookup` 全判 `find_poem`),则回到 `prompts.INTENT_PROMPT` 补一句区分规则后重跑,并留痕。

- [ ] **Step 3: 提交(仅当 Step 1 之后有文件改动)**

本 Task 默认不产文件;若 Step 2 改了 `prompts.py`:

```powershell
git add potry-ai-agent/prompts.py
git commit -m "fix(ch04): 意图识别 Prompt 补充知识类与业务类区分规则(评估集纠偏)"
```

---

## Task 12: 验收 5 条真跑 + 整体 code review + 收尾

**Files:**
- Modify: `dev-notes/ch04.md`

- [ ] **Step 1: 启动服务**

确认 Milvus **无其它进程占用**(建库 CLI 必须处于停止状态,否则 Milvus Lite 独占锁冲突):

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

保持该终端不关,另开一个 PowerShell 窗口执行 Step 2 起各条验收。服务日志中会打印 `[wf] 图已编译(checkpointer=sqlite:...)`。

- [ ] **Step 2: 验收①——知识类强制检索可观测**

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/agent/workflow -H "Content-Type: application/json" -d '{\"sessionId\":\"acc1\",\"message\":\"《静夜思》表达了什么感情\"}'
```

Expected:
- 响应含 `event: token` 与 `event: done`;
- **服务日志出现** `[wf] retrieve n=... top=...` 与 `[wf] intent=poem_explain route=knowledge gate=pass score=... `。

- [ ] **Step 3: 验收②——业务类由 Agent 自主调工具**

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/agent/workflow -H "Content-Type: application/json" -d '{\"sessionId\":\"acc2\",\"message\":\"李白是什么朝代的\"}'
```

Expected: 响应含 `event: tool_status`(`"tool": "query_poet"`);服务日志 `[wf] intent=find_poet route=business gate=skip score=- iters=1 ...`。

- [ ] **Step 4: 验收③——投诉类两按钮 + 互不干扰 + 不点不写库**

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" -uroot -ppublication-placeholder-mysql_password -N -e "SELECT COUNT(*) FROM feedback;" poem
```

记下**前值**,然后在聊天页发送「我要投诉」→ 断言出现两个独立按钮(人工看)。再:

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/agent/workflow -H "Content-Type: application/json" -d '{\"sessionId\":\"acc3\",\"message\":\"我要投诉\"}'
```

Expected: 响应含 `event: action` 且 `data` 里有 `"actions": ["handoff", "feedback"]`;服务日志 `[wf] intent=complaint route=complaint gate=skip score=- iters=0`。

**未点击按钮时**:再发一轮普通消息(如 `{\"sessionId\":\"acc3\",\"message\":\"再讲一首诗\"}`),然后复查计数:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" -uroot -ppublication-placeholder-mysql_password -N -e "SELECT COUNT(*) FROM feedback;" poem
```

Expected: **与 Step 4 前值相同**(未点击不写库 —— 这是 spec §12 偏差缓解措施的显式验证)。

**点「提交反馈」后**:界面点按钮,再复查计数 → **+1**;`SELECT messsage FROM feedback ORDER BY id DESC LIMIT 1;` 能看到反馈原文。

**点「转人工」**:界面出现「已转接人工客服」+「您好,我是青莲,请问有什么可以帮您的」;再次复查计数 → **不变**(两操作互不干扰)。

- [ ] **Step 5: 验收④——闲聊固定话术且不调模型/工具**

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/agent/workflow -H "Content-Type: application/json" -d '{\"sessionId\":\"acc4\",\"message\":\"今天天气不错\"}'
```

Expected: 回答为**预设固定话术**(`我是青莲,只陪你聊诗词文史……`);服务日志 `[wf] intent=chitchat route=chitchat gate=skip score=- iters=0 tokens=0`;日志中**无** `[wf] retrieve`,响应**无** `tool_status`。

> 说明:同一会话第二轮的意图识别仍会调一次模型(最简版未做缓存),`tokens=0` 指 **Agent 未执行**;这条的口径是"**未进入 Agent、未调工具、未检索**"。

- [ ] **Step 6: 验收⑤——ReAct 循环多轮迭代可观测**

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/agent/workflow -H "Content-Type: application/json" -d '{\"sessionId\":\"acc5\",\"message\":\"先查李白是谁,再告诉我他写月亮的那首诗讲了什么\"}'
```

Expected: 服务日志 `iters>=2`(先查诗人/诗词,再组织答案)。

- [ ] **Step 7: 整体 code review**

按 Superpowers 两阶段评审对 Ch04 全部新代码做 spec 合规 + 质量评审;把结论(尤其**问题项与修复**)、以及"是否 Yes"写入 `dev-notes/ch04.md` 阶段 5。

- [ ] **Step 8: 追记 dev-notes 阶段 2–6**

`dev-notes/ch04.md` 逐段补齐(每段都要有:关键指令 / 产出物路径 / 拒绝或纠偏 / 翻车与返工):
- **阶段 2(计划与选型纠偏)**:Context7 核对结论;`SqliteSaver` 同步/异步冲突 → 停手请示 → 用户拍板 `AsyncSqliteSaver`;`websockets` 17.2→16.1.1;
- **阶段 3(逐任务实现)**:每任务的提交 hash、评审结论、返工记录;
- **阶段 4(评估集)**:21 条意图样例的完整输出与准确率;
- **阶段 5(验收)**:五条验收的原始命令与观测输出(含日志行、feedback 计数前后值);
- **阶段 6(交付)**:演示命令、测试总数、文档路径。

- [ ] **Step 9: 同步 spec 的选型留痕**

`docs/superpowers/specs/2026-10-18-ai-tutor-ch04-langgraph-workflow-design.md`:
- §2 技术选型表的 checkpointer 行改为:`AsyncSqliteSaver`(`langgraph-checkpoint-sqlite`,`langgraph.checkpoint.sqlite.aio`),备注"官方同步版 `SqliteSaver` 不支持异步图,经用户批准改用同类异步变体;存储后端仍为 SQLite 文件 `checkpoints/graph.sqlite`";
- §12 决策留痕表新增一行:`checkpointer 同步/异步冲突 | 原定 SqliteSaver 无法用于异步图(实测 NotImplementedError)→ 停手请示 → 用户批准改用 AsyncSqliteSaver(存储后端不变)`。

- [ ] **Step 10: 最终全量回归 + 提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

```powershell
git add dev-notes/ch04.md docs/superpowers/specs/2026-10-18-ai-tutor-ch04-langgraph-workflow-design.md
git commit -m "docs(ch04): 验收结果、评估集与 checkpointer 选型留痕"
```

- [ ] **Step 11: 交付说明**

向用户汇报:
1. **启动演示命令**:`.\.venv\Scripts\python.exe -m uvicorn main:app --port 8000` → 打开 `http://127.0.0.1:8000/chat`;
2. **测试结果**:`pytest tests -q` 全绿,总数与基线 132 的对照;
3. **dev-notes 路径**:`dev-notes/ch04.md`;
4. **已知边界**:建库停在约 50%,未嵌入的诗词检索不到(预期);闲聊轮仍会调一次意图识别模型;`/agent/workflow` 的 token 帧为整段答案切块(非 LLM 逐字流)。

---

## Self-Review

**1. Spec coverage**

| spec 章节 | 落到哪个 Task |
|---|---|
| §2 技术选型(LangGraph / AsyncSqliteSaver / 手写 ReAct / 复用工具与检索器) | T1(依赖)、T5、T8 |
| §3.1 节点顺序图骨架 | T8(装配) |
| §3.2 模块划分 | T2–T9 逐模块 |
| §3.3 数据流(SSE 帧序) | T9 |
| §4 七类意图 → 四出口硬编码 + JSON 严格输出 + 解析失败降级 | T3、T7 |
| §5 WorkflowState + checkpointer + thread_id | T3、T8 |
| §6 ReAct 停止判定三条 + 信息缺失追问 + 工具集 | T5 |
| §7 置信度闸(三源合并、复用 `similarity_threshold`、不足写 pending、业务类绕过) | T4、T7、T8 |
| §8 前端两按钮与 `action` 事件 | T10(后端在 T9) |
| §9 落库(pending_questions / feedback / 结构化日志 + messages 表) | T4、T6、T7 |
| §10 错误处理与降级 | T5、T7、T9(各节点 try/except + SSE error 帧) |
| §11 测试与验收策略 | T2–T9 单测 + T11 评估集 + T12 验收 |
| §12 决策与偏差留痕(`submit_feedback` 注册给 Agent 的缓解措施) | T6(工具描述约束 + Prompt 约束)、T12 Step 4(显式验证) |
| 需求第 1 条「先无框架原生实现」 | T2 |
| 需求第 8 条「后端不自动触发」 | T6 描述约束 + T12 Step 4 显式验证 |

**2. Placeholder scan:** 无 TBD/TODO;所有代码步骤给出完整可粘贴代码;所有命令给出期望输出。

**3. Type/名称一致性核对**

- `WorkflowState` 字段名与各节点写入键一致:`resolved_input` / `intent` / `route` / `retrieved` / `evidence_score` / `gate_status` / `messages` / `tool_trace` / `answer` / `actions` / `iterations` / `tokens_used` / `fallback_reason` / `started_at`(T3 定义,T5/T7/T8 使用)。
- 条件边目标名与 `add_node` 注册名一致:`retrieve` / `agent` / `log` / `tool_node`(T8)。
- `make_tool_message(tool_call_id, name, result)` 调用签名与 `tools/registry.py` 既有定义一致(T2/T5)。
- `KnowledgeStorage.add_pending_question(question, session_id=None)` 在 T4 定义、T7 调用,签名一致。
- `AppStorage.add_feedback(message, userid=None)` 在 T6 定义,T9 端点与 T6 工具均按此调用。
- `open_checkpointer(db_path)` 返回 `(saver, conn)`,T8 测试与 T9 lifespan 用法一致。
- `Settings` 新字段名 `workflow_max_iter` / `workflow_max_tokens` / `workflow_checkpoint_path` 在 T1 定义、T3(deps)、T5、T9 使用,一致。
- `WorkflowDeps(settings, llm, registry, knowledge_storage, chat_storage)` 五参位置参数,在 T5/T7/T8 测试与 T9 装配处一致。
