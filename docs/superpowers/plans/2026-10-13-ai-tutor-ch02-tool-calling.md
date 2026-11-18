# AI 伴学 Ch02(Function Calling 查数据)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 Ch01 的 SSE 流式聊天装上查数据能力:LangChain `@tool` 三工具(查诗词/诗人/朝代),手动单轮 Function Calling 编排,工具结果回灌后流式作答,聊天记录(含工具调用)落 conversations/messages 表,聊天页气泡带工具徽章。

**Architecture:** 工具用 `@tool` 定义在 `poetry_tools.py`,经 `ToolRegistry`(Schema 校验→超时→重试→错误包装)统一执行;`chat_service.stream_events` 产出 SSE 事件流(非流式取 tool_calls → 执行回灌 ToolMessage → 第二次 `astream` 流式收敛,只做单轮),`main.py` 负责编码推送;数据侧 Docker MySQL 导入 `poemmax-h2.sql`(复用 `potry`/`writer` 表),`storage.py` 并行落库。

**Tech Stack:** Python 3.11 + FastAPI + langchain-core 1.6.10(`@tool`/`ToolMessage`)+ langchain-openai 1.7.1(`bind_tools`/`astream`)+ SQLAlchemy 2.0 + pymysql + Docker MySQL 8。API 用法已过 Context7 官方文档核对(`@tool` 签名与 tool_calls 结构、SQLAlchemy 2.0 `DeclarativeBase`/`mapped_column`)。

**Spec:** `docs/superpowers/specs/2026-10-13-ai-tutor-ch02-tool-calling-design.md`(所有任务以它为准)

---

## 环境与命令约定

- 项目根:`e:\javatexts\poetry-spring2`,服务目录 `potry-ai-agent/`(Ch01 扁平风格延续,业务模块不进包目录,`tools/` 是唯一新包)。
- Python 用 venv:`e:\javatexts\poetry-spring2\potry-ai-agent\.venv\Scripts\python.exe`(3.11.9)。
- **Shell 是 PowerShell 5:禁止 `&&`,多命令用 `;` 分隔。**
- 测试命令(在 `potry-ai-agent/` 下):
  `.\.venv\Scripts\python.exe -m pytest tests -v`
  单文件:`.\.venv\Scripts\python.exe -m pytest tests\test_registry.py -v`
- `tests/conftest.py` 已在 import 前 setdefault 测试环境变量(`MYSQL_URL=sqlite:///...` 等),CI 无 .env 也能跑;新配置项必须同步补进 conftest。
- 日志/异常串一律截断 `[:200]`,不得打印 MySQL 密码、API key。

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `potry-ai-agent/docker-compose.yml` | Create | MySQL 8 服务(端口 3306,密码走 .env) |
| `potry-ai-agent/mysql-init/` + `poetry-mysql.sql` | Create | H2 脚本转 MySQL 的导入文件(含存量数据) |
| `potry-ai-agent/.env` | Modify | 追加 `MYSQL_URL`、`MYSQL_ROOT_PASSWORD`、`TOOL_TIMEOUT_SECONDS`、`TOOL_MAX_RETRIES` |
| `potry-ai-agent/requirements.txt` | Modify | 追加 sqlalchemy、pymysql |
| `potry-ai-agent/config.py` | Modify | `Settings` 追加 mysql_url / tool_timeout_seconds / tool_max_retries |
| `potry-ai-agent/db.py` | Create | engine/session 工厂 + `Potry`/`Writer` 只读映射 |
| `potry-ai-agent/storage.py` | Create | conversations/messages 模型 + `ChatStorage` 落库 |
| `potry-ai-agent/tools/__init__.py` | Create | 包导出 |
| `potry-ai-agent/tools/registry.py` | Create | `ToolRegistry`:校验/超时/重试/错误包装/`make_tool_message` |
| `potry-ai-agent/tools/poetry_tools.py` | Create | 三个 `@tool` 查询工具 |
| `potry-ai-agent/prompts.py` | Modify | System Prompt 追加工具使用指引 |
| `potry-ai-agent/chat_service.py` | Modify | `stream_events` 单轮编排 + 落库;`stream_reply` 变兼容包装 |
| `potry-ai-agent/main.py` | Modify | SSE 事件编码透传 + `tool_status` 帧 |
| `potry-ai-agent/static/chat.html` | Modify | 工具徽章(Vibe Coding,Task 12) |
| `potry-ai-agent/tests/*` | Create/Modify | 各任务 TDD 测试 |
| `potry-ai-agent/evals/ch02_tool_eval_cases.md` | Create | 评估样例(任务 13) |
| `dev-notes/ch02.md` | Modify | 每任务结束追记留痕 |

**测试用 SQLite 原则**:`PoetryBase`(potry/writer)与 `ChatBase`(conversations/messages)是两个独立 DeclarativeBase,测试只对 `ChatBase` 建表(SQLite 内存);poetry 工具测试直接 stub `tools.poetry_tools._fetch_*` 内部函数,不连库。`db.py`/`storage.py` 模块级只建 lazy 工厂,不在 import 时连数据库(遵循 spec §9「连接懒建」)。

---

### Task 1: 配置扩展(config.py + conftest)

**Files:**
- Modify: `potry-ai-agent/config.py`
- Modify: `potry-ai-agent/tests/conftest.py`
- Test: `potry-ai-agent/tests/test_config.py`(追加)

- [ ] **Step 1: 写失败测试**(追加到 `tests/test_config.py` 末尾;文件现有结构照旧,`monkeypatch` 是 pytest 内置 fixture):

```python
def test_load_settings_reads_tool_and_mysql_configs(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("MYSQL_URL", "mysql+pymysql://root:pw@localhost:3306/poem")
    monkeypatch.setenv("TOOL_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("TOOL_MAX_RETRIES", "2")
    s = load_settings()
    assert s.mysql_url == "mysql+pymysql://root:pw@localhost:3306/poem"
    assert s.tool_timeout_seconds == 3.0
    assert s.tool_max_retries == 2


def test_load_settings_bad_tool_number_reports_variable(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("TOOL_TIMEOUT_SECONDS", "abc")
    with pytest.raises(RuntimeError, match="TOOL_TIMEOUT_SECONDS"):
        load_settings()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_config.py -v`
Expected: 新增两条 FAIL(TypeError: unexpected keyword argument / 无 RuntimeError),原有条目 PASS

- [ ] **Step 3: 改 `config.py`**(`Settings` 字段追加三行,`load_settings` 解析逻辑并入现有 try):

```python
@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    history_max_tokens: int
    llm_temperature: float
    mysql_url: str = "mysql+pymysql://root:publication-placeholder-mysql_password@localhost:3306/poem?charset=utf8mb4"
    tool_timeout_seconds: float = 5.0
    tool_max_retries: int = 1
```

`load_settings()` 中 try 块改为(报错信息沿用 Ch01 风格指明变量名与格式):

```python
    try:
        history_max_tokens = int(os.getenv("HISTORY_MAX_TOKENS", "2000"))
        llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
        tool_timeout_seconds = float(os.getenv("TOOL_TIMEOUT_SECONDS", "5"))
        tool_max_retries = int(os.getenv("TOOL_MAX_RETRIES", "1"))
    except ValueError as exc:
        raise RuntimeError(
            f"环境变量格式错误: {exc}(HISTORY_MAX_TOKENS/TOOL_MAX_RETRIES 须为整数,"
            "LLM_TEMPERATURE/TOOL_TIMEOUT_SECONDS 须为小数)"
        )
```

return 时追加:`mysql_url=os.getenv("MYSQL_URL") or "mysql+pymysql://root:publication-placeholder-mysql_password@localhost:3306/poem?charset=utf8mb4"`、`tool_timeout_seconds=tool_timeout_seconds`、`tool_max_retries=tool_max_retries`。

- [ ] **Step 4: conftest 追加测试兜底**(import 语句后、既有 setdefault 一节里补):

```python
os.environ.setdefault("MYSQL_URL", "sqlite:///:memory:")
os.environ.setdefault("TOOL_TIMEOUT_SECONDS", "5")
os.environ.setdefault("TOOL_MAX_RETRIES", "1")
```

- [ ] **Step 5: 跑全量测试确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`
Expected: 19 passed(17 原有 + 2 新增)

- [ ] **Step 6: Commit**

```powershell
git add potry-ai-agent/config.py potry-ai-agent/tests/conftest.py potry-ai-agent/tests/test_config.py
git commit -m "feat(ai-agent): extend settings with mysql and tool infra config (ch02)"
```

---

### Task 2: SQLAlchemy 基础设施(db.py + storage.py)

**Files:**
- Create: `potry-ai-agent/db.py`
- Create: `potry-ai-agent/storage.py`
- Modify: `potry-ai-agent/requirements.txt`
- Test: `potry-ai-agent/tests/test_storage.py`

- [ ] **Step 1: 追加依赖并安装**

`requirements.txt` 主依赖区追加两行(sqlalchemy 版本按 2.0 系最新装,Context7 文档即 2.0 风格):

```
sqlalchemy==2.0.43
pymysql==1.1.1
```

Run: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
(若 pip 解析的 2.0.x 小版本不同,以实际安装版本写回 requirements.txt,不改代码写法)

- [ ] **Step 2: 写失败测试**(新建 `tests/test_storage.py`;测试只建 `ChatBase`,不碰 poetry 表):

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from storage import ChatBase, ChatStorage, Conversation, Message


def make_storage():
    engine = create_engine("sqlite:///:memory:")
    ChatBase.metadata.create_all(engine)
    return ChatStorage(sessionmaker(bind=engine))


def test_persist_round_trips_full_tool_turn():
    st = make_storage()
    cid = st.persist_turn(
        "s1",
        [
            {"role": "user", "content": "《静夜思》是谁写的"},
            {
                "role": "assistant",
                "content": "",
                "tool_name": "query_poem",
                "tool_call_id": "call_1",
                "tool_args": {"keyword": "静夜思"},
            },
            {
                "role": "tool",
                "content": '{"ok": true}',
                "tool_name": "query_poem",
                "tool_call_id": "call_1",
            },
            {"role": "assistant", "content": "是李白写的。"},
        ],
    )
    rows = st.load_messages(cid)
    assert [r["role"] for r in rows] == ["user", "assistant", "tool", "assistant"]
    assert rows[2]["tool_name"] == "query_poem"
    assert rows[2]["tool_call_id"] == "call_1"
    assert rows[1]["tool_args"] == '{"keyword": "静夜思"}'
    assert rows[3]["content"] == "是李白写的。"


def test_conversation_reused_across_turns():
    st = make_storage()
    cid1 = st.persist_turn("s1", [{"role": "user", "content": "第一句"}])
    cid2 = st.persist_turn("s1", [{"role": "user", "content": "第二句"}])
    assert cid1 == cid2  # 同 session 复用同一 conversation
    rows = st.load_messages(cid1)
    assert len(rows) == 2
```

- [ ] **Step 3: 跑测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_storage.py -v`
Expected: FAIL,ModuleNotFoundError: storage

- [ ] **Step 4: 写 `db.py`**(lazy 工厂,import 不连库;映射列名与 H2 表完全一致,`type` 是 Python 关键字用列名 "type"):

```python
"""SQLAlchemy 引擎与诗词表映射(只读,列名与 Java 侧 H2 库一致)。"""
from sqlalchemy import String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class PoetryBase(DeclarativeBase):
    pass


class Potry(PoetryBase):
    __tablename__ = "potry"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(String(255))
    dynasty: Mapped[str | None] = mapped_column(String(10))
    writer: Mapped[str | None] = mapped_column(String(100))
    type: Mapped[str | None] = mapped_column("type", String(100))
    content: Mapped[str | None] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(Text)
    shangxi: Mapped[str | None] = mapped_column(Text)
    audioUrl: Mapped[str | None] = mapped_column("audioUrl", String(255))
    translation: Mapped[str | None] = mapped_column(Text)


class Writer(PoetryBase):
    __tablename__ = "writer"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(25))
    headImageUrl: Mapped[str | None] = mapped_column("headImageUrl", String(255))
    simpleIntro: Mapped[str | None] = mapped_column("simpleIntro", Text)
    detailIntro: Mapped[str | None] = mapped_column("detailIntro", Text)


_engine = None
_session_factory = None


def get_session_factory(url: str):
    """惰性创建 engine 与 sessionmaker:首调建、后续复用(MySQL 挂了只在查询时失败)。"""
    global _engine, _session_factory
    if _session_factory is None:
        _engine = create_engine(url, pool_pre_ping=True)
        _session_factory = sessionmaker(bind=_engine)
    return _session_factory


def new_session(url: str) -> Session:
    return get_session_factory(url)()
```

- [ ] **Step 5: 写 `storage.py`**:

```python
"""对话落库:conversations/messages 表(ChatBase 独立于 PoetryBase,create_all 不碰诗词表)。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class ChatBase(DeclarativeBase):
    pass


class Conversation(ChatBase):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Message(ChatBase):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(String(64))
    tool_call_id: Mapped[str | None] = mapped_column(String(64))
    tool_args: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ChatStorage:
    """一轮对话(可含 tool 调用)整体落 messages;同 session 复用同一 conversation。"""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._factory = session_factory

    def persist_turn(self, session_id: str, rows: list[dict]) -> int:
        """rows 每项:role/content 必填,tool_name/tool_call_id/tool_args 可选。返回 conversation_id。"""
        with Session(self._factory) as session:
            conv = (
                session.query(Conversation).filter_by(session_id=session_id).order_by(Conversation.id).first()
            )
            if conv is None:
                conv = Conversation(session_id=session_id)
                session.add(conv)
                session.flush()  # 拿到 conv.id 供外键用
            for row in rows:
                session.add(
                    Message(
                        conversation_id=conv.id,
                        role=row["role"],
                        content=row["content"],
                        tool_name=row.get("tool_name"),
                        tool_call_id=row.get("tool_call_id"),
                        tool_args=row.get("tool_args"),
                    )
                )
            session.commit()
            return conv.id

    def load_messages(self, conversation_id: int) -> list[dict]:
        with Session(self._factory) as session:
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
```

- [ ] **Step 6: 跑测试确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_storage.py -v`
Expected: 2 passed

- [ ] **Step 7: 全量回归 + Commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`(21 passed)

```powershell
git add potry-ai-agent/db.py potry-ai-agent/storage.py potry-ai-agent/requirements.txt potry-ai-agent/tests/test_storage.py
git commit -m "feat(ai-agent): sqlalchemy poetry mapping and chat persistence (ch02)"
```

---

### Task 3: 工具注册表(tools/registry.py)

**Files:**
- Create: `potry-ai-agent/tools/__init__.py`
- Create: `potry-ai-agent/tools/registry.py`
- Test: `potry-ai-agent/tests/test_registry.py`

- [ ] **Step 1: 写失败测试**(`tests/test_registry.py`,全部同步函数;重试间隔打补丁为 0 防拖慢):

```python
import asyncio

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool

from tools import registry as reg_mod
from tools.registry import ToolRegistry


def make_registry():
    return ToolRegistry(timeout=5.0, max_retries=1)


def test_register_and_get_tools():
    reg = make_registry()

    @tool
    def demo(x: int) -> str:
        """演示工具。

        Args:
            x: 数字
        """
        return str(x)

    reg.register(demo)
    assert reg.get_tools() == [demo]


@pytest.mark.asyncio
async def test_unknown_tool_returns_structured_error():
    reg = make_registry()
    assert await reg.execute("nope", {}) == {"ok": False, "error": "unknown tool: nope"}


@pytest.mark.asyncio
async def test_invalid_args_returned_as_structured_error():
    reg = make_registry()

    @tool
    def need_int(x: int) -> str:
        """需要整数。

        Args:
            x: 数字
        """
        return str(x)

    reg.register(need_int)
    result = await reg.execute("need_int", {"x": "not-a-number"})
    assert result["ok"] is False
    assert "invalid arguments" in result["error"]
    # 成功路径不受影响
    assert await reg.execute("need_int", {"x": 3}) == {"ok": True, "found": True, "data": "3"}


@pytest.mark.asyncio
async def test_exception_wrapped_and_retried(monkeypatch):
    monkeypatch.setattr(reg_mod, "RETRY_INTERVAL", 0)  # 免等待
    reg = make_registry()
    calls = {"n": 0}

    @tool
    def flaky() -> str:
        """总会抛异常的工具。"""
        calls["n"] += 1
        raise ValueError("boom")

    reg.register(flaky)
    result = await reg.execute("flaky", {})
    assert result["ok"] is False
    assert "boom" in result["error"]
    assert calls["n"] == 2  # 首次 + 重试 1 次


@pytest.mark.asyncio
async def test_timeout_retried_then_wrapped(monkeypatch):
    monkeypatch.setattr(reg_mod, "RETRY_INTERVAL", 0)
    reg = make_registry()
    calls = {"n": 0}

    @tool
    def slow() -> str:
        """慢工具(直接抛超时模拟)。"""
        calls["n"] += 1
        raise asyncio.TimeoutError()

    reg.register(slow)
    result = await reg.execute("slow", {})
    assert result == {"ok": False, "error": "timeout"}
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_registry_applies_tool_time_limits():
    reg = make_registry()

    @tool
    def slow() -> str:
        """慢工具。"""
        return "done"

    reg.register(slow)
    assert await reg.execute("slow", {}) == {"ok": True, "found": True, "data": "done"}
    assert slow.time_limit is True
    assert slow.max_execution_time == 5.0


def test_make_tool_message_matches_call():
    msg = reg_mod.make_tool_message("call_1", "query_poem", {"ok": True})
    assert isinstance(msg, ToolMessage)
    assert msg.tool_call_id == "call_1"
    assert msg.name == "query_poem"
    assert msg.content == '{"ok": true}'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_registry.py -v`
Expected: FAIL,ModuleNotFoundError: tools

- [ ] **Step 3: 写 `tools/__init__.py`**:

```python
"""工具包:注册表 + 业务工具。"""
```

- [ ] **Step 4: 写 `tools/registry.py`**(`execute` 是 **async**——工具执行跑在 chat_service 的事件循环里,不能用 `asyncio.run`;注册表不管落库、不产 SSE 帧,两者都归 chat_service——落库走 `persist_turn` 整轮一次(spec §6),`calling` 帧由 chat_service 在 execute 前实时推,done/error 帧按 `result["ok"]` 生成):

```python
"""工具注册表:登记 @tool 工具,统一执行入口(Schema 校验 → 超时 → 重试 → 错误包装)。"""
import asyncio
import json
import time
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool

RETRY_INTERVAL = 0.2  # 固定间隔秒数,不搞指数退避(YAGNI);测试置 0 免等待


def make_tool_message(tool_call_id: str, name: str, result: dict) -> ToolMessage:
    """工具结果 JSON 包进 ToolMessage,tool_call_id 对齐(spec §4 结果回灌)。"""
    return ToolMessage(
        content=json.dumps(result, ensure_ascii=False),
        tool_call_id=tool_call_id,
        name=name,
    )


class ToolRegistry:
    def __init__(self, timeout: float = 5.0, max_retries: int = 1) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        # 时间上限打在工具上(Beta 属性,可能随版本变动——缺了就补,不崩)
        tool.time_limit = True
        tool.max_execution_time = self._timeout
        self._tools[tool.name] = tool

    def get_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    async def execute(self, name: str, args: dict) -> dict:
        """执行一个工具调用。返回结构化 dict;永不抛异常。

        结果约定:成功 `{"ok":true,"found":true,"data":...}`;业务查不到
        `{"ok":true,"found":false}`(由工具函数给出);执行失败 `{"ok":false,"error":...}`。
        """
        tool = self._tools.get(name)
        if tool is None:
            return {"ok": False, "error": f"unknown tool: {name}"}

        try:
            if tool.args_schema is not None:
                tool.args_schema.model_validate(args)  # 失败抛 ValidationError
        except Exception as exc:  # noqa: BLE001 - Pydantic ValidationError
            return {"ok": False, "error": f"invalid arguments: {str(exc)[:200]}"}

        result: dict[str, Any] | None = None
        attempts = self._max_retries + 1
        for attempt in range(attempts):
            try:
                raw = await asyncio.wait_for(tool.ainvoke(dict(args)), timeout=self._timeout)
                result = (
                    raw
                    if isinstance(raw, dict)
                    else {"ok": True, "found": True, "data": raw}
                )
                break
            except (asyncio.TimeoutError, TimeoutError):
                result = {"ok": False, "error": "timeout"}
            except Exception as exc:  # noqa: BLE001 - 工具异常统一包装(spec §4)
                result = {"ok": False, "error": str(exc)[:200]}
            if attempt < attempts - 1:
                await asyncio.sleep(RETRY_INTERVAL)
        return result
```

(`time` 若最终没用到就删掉,别留死 import——本实现不再计时,durationMs 由 chat_service 测。)

- [ ] **Step 5: 跑测试确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_registry.py -v`
Expected: 7 passed

- [ ] **Step 6: 全量回归 + Commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`(28 passed)

```powershell
git add potry-ai-agent/tools potry-ai-agent/tests/test_registry.py
git commit -m "feat(ai-agent): tool registry with validation, timeout and retry (ch02)"
```

---

### Task 4: 三个诗词工具(tools/poetry_tools.py)

**Files:**
- Create: `potry-ai-agent/tools/poetry_tools.py`
- Test: `potry-ai-agent/tests/test_poetry_tools.py`

- [ ] **Step 1: 写失败测试**(stub 掉 `_fetch_*` 内部函数,不连库):

```python
from tools import poetry_tools as pt


def test_query_poem_found_and_not_found(monkeypatch):
    monkeypatch.setattr(
        pt, "_fetch_poem",
        lambda session, kw: {"title": "静夜思", "dynasty": "唐", "writer": "李白",
                             "content": "床前明月光", "translation": "...", "type": "五言绝句",
                             "shangxi": "...", "remark": None},
    )
    ok = pt.query_poem.invoke({"keyword": "静夜思"})
    assert ok["ok"] is True and ok["found"] is True
    assert ok["poem"]["writer"] == "李白"

    monkeypatch.setattr(pt, "_fetch_poem", lambda session, kw: None)
    miss = pt.query_poem.invoke({"keyword": "不存在的诗"})
    assert miss == {"ok": True, "found": False}


def test_query_poet_with_representative_works(monkeypatch):
    monkeypatch.setattr(
        pt, "_fetch_poet",
        lambda session, name: {"name": "李白", "simpleIntro": "诗仙", "detailIntro": "……",
                               "headImageUrl": None},
    )
    monkeypatch.setattr(
        pt, "_fetch_works",
        lambda session, name: ["静夜思", "望庐山瀑布"],
    )
    ok = pt.query_poet.invoke({"name": "李白"})
    assert ok["found"] is True
    assert ok["poet"]["name"] == "李白"
    assert ok["works"] == ["静夜思", "望庐山瀑布"]


def test_query_dynasty_poems_capped(monkeypatch):
    monkeypatch.setattr(
        pt, "_fetch_dynasty_titles",
        lambda session, dyn: ["诗一", "诗二", "诗三"],
    )
    ok = pt.query_dynasty_poems.invoke({"dynasty": "唐"})
    assert ok["found"] is True
    assert ok["count"] == 3
    assert ok["titles"] == ["诗一", "诗二", "诗三"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_poetry_tools.py -v`
Expected: FAIL,ModuleNotFoundError(或属性缺失)

- [ ] **Step 3: 写 `tools/poetry_tools.py`**(SQL 全部只读;`content` 截 300 字防回灌爆炸):

```python
"""诗词域业务工具:查诗词 / 诗人 / 朝代(只读,复用 Java 侧 potry/writer 表)。"""
import json

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import load_settings
from db import Potry, Writer, new_session

_MAX_CONTENT = 300  # 诗文/译文回灌截断,防上下文爆炸
_MAX_TITLES = 20  # 朝代标题列表上限


def _get_session() -> Session:
    return new_session(load_settings().mysql_url)


def _truncate(text: str | None) -> str | None:
    return text[:_MAX_CONTENT] if text else text


def _fetch_poem(session: Session, keyword: str) -> dict | None:
    like = f"%{keyword}%"
    stmt = (
        select(Potry)
        .where(
            (Potry.title.like(like))
            | (Potry.writer.like(like))
            | (Potry.content.like(like))
        )
        .limit(1)
    )
    p = session.execute(stmt).scalar_one_or_none()
    if p is None:
        return None
    return {
        "title": p.title,
        "dynasty": p.dynasty,
        "writer": p.writer,
        "type": p.type,
        "content": _truncate(p.content),
        "translation": _truncate(p.translation),
        "shangxi": _truncate(p.shangxi),
        "remark": _truncate(p.remark),
    }


def _fetch_poet(session: Session, name: str) -> dict | None:
    w = session.execute(select(Writer).where(Writer.name == name)).scalar_one_or_none()
    if w is None:
        return None
    return {
        "name": w.name,
        "simpleIntro": _truncate(w.simpleIntro),
        "detailIntro": _truncate(w.detailIntro),
        "headImageUrl": w.headImageUrl,
    }


def _fetch_works(session: Session, name: str) -> list[str]:
    stmt = select(Potry.title).where(Potry.writer == name).limit(5)
    return [t for t in session.execute(stmt).scalars() if t]


def _fetch_dynasty_titles(session: Session, dynasty: str) -> list[str]:
    stmt = select(Potry.title).where(Potry.dynasty == dynasty).limit(_MAX_TITLES)
    return [t for t in session.execute(stmt).scalars() if t]


@tool
def query_poem(keyword: str) -> dict:
    """按关键词查诗词:标题、作者或诗句模糊匹配,返回一首最匹配的诗词(含朝代、作者、原文、译文)。

    Args:
        keyword: 诗词标题、作者名或诗句中的关键词,如「静夜思」「李白」「明月」
    """
    with _get_session() as session:
        poem = _fetch_poem(session, keyword)
    if poem is None:
        return {"ok": True, "found": False}
    return {"ok": True, "found": True, "poem": poem}


@tool
def query_poet(name: str) -> dict:
    """按姓名查诗人:生平简介与代表作标题列表。

    Args:
        name: 诗人姓名,如「李白」「杜甫」
    """
    with _get_session() as session:
        poet = _fetch_poet(session, name)
        works = _fetch_works(session, name) if poet else []
    if poet is None:
        return {"ok": True, "found": False}
    return {"ok": True, "found": True, "poet": poet, "works": works}


@tool
def query_dynasty_poems(dynasty: str) -> dict:
    """按朝代查诗词:返回该朝代的诗词标题列表(最多 20 条)。

    Args:
        dynasty: 朝代名,如「唐」「宋」
    """
    with _get_session() as session:
        titles = _fetch_dynasty_titles(session, dynasty)
    if not titles:
        return {"ok": True, "found": False}
    return {"ok": True, "found": True, "count": len(titles), "titles": titles}
```

(模块顶部 `import json` 若最终没用到就删掉,别留死 import。)

- [ ] **Step 4: 跑测试确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_poetry_tools.py -v`
Expected: 3 passed

- [ ] **Step 5: 全量回归 + Commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`(31 passed)

```powershell
git add potry-ai-agent/tools/poetry_tools.py potry-ai-agent/tests/test_poetry_tools.py
git commit -m "feat(ai-agent): poetry query tools via @tool (ch02)"
```

---

### Task 5: Prompt 工具指引 + 评估样例(prompts.py)

**Files:**
- Modify: `potry-ai-agent/prompts.py`
- Create: `potry-ai-agent/evals/ch02_tool_eval_cases.md`
- Test: `potry-ai-agent/tests/test_prompts.py`(追加)

- [ ] **Step 1: 写失败测试**(追加到 `tests/test_prompts.py`):

```python
def test_system_prompt_has_tool_guidance():
    text = SYSTEM_PROMPT_TEMPLATE.format()
    assert "查数据" in text  # 工具使用指引已追加
    assert "青莲" in text  # 人设不变
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_prompts.py -v`
Expected: 新增条 FAIL

- [ ] **Step 3: 改 `prompts.py`**:在 `SYSTEM_PROMPT_TEMPLATE` 的 `# 行为约束` 之后追加一节(其余内容一字不动):

```
# 查数据工具
- 遇到查数据类问题(诗词出处、作者是谁、诗人生平、某朝代有哪些诗)先调用工具查询,拿到结果再作答,不得凭记忆编造;
- 工具返回查不到或失败,如实告知用户不确定或这会儿查不了,不编造结果;
- 拿不准的指代(如「那首讲月亮的」)可先试着用关键词查一次,查不到就如实说找不到并请用户补充线索。
```

- [ ] **Step 4: 写评估样例** `evals/ch02_tool_eval_cases.md`(人工拿真实 DeepSeek 跑比对,任务 13 执行):

```markdown
# Ch02 工具调用评估样例(真实模型人工比对)

前置:服务 + Docker MySQL 已起,`curl` 打 `/agent/chat`(或浏览器聊天页)。

| # | 用户输入 | 期望工具 | 期望行为 | 通过 |
|---|---|---|---|---|
| 1 | 《静夜思》是谁写的 | query_poem | 带 tool_status 帧,回答"李白"且基于返回内容 | |
| 2 | 李白是什么样的诗人 | query_poet | 带 tool_status 帧,按 writer 表简介作答 | |
| 3 | 那首讲月亮的叫啥 | query_poem(可能) | 关键词查不到,如实说不确定并请补充线索(漏召回,预期) | |
| 4 | 今天天气真好 | (不调工具) | 无 tool_status 帧,直接流式闲聊回应并拉回诗词 | |
```

- [ ] **Step 5: 跑测试确认通过 + Commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`(32 passed)

```powershell
git add potry-ai-agent/prompts.py potry-ai-agent/tests/test_prompts.py potry-ai-agent/evals/ch02_tool_eval_cases.md
git commit -m "feat(ai-agent): tool usage guidance in system prompt + eval cases (ch02)"
```

---

### Task 6: 单轮编排改造(chat_service.py)

**Files:**
- Modify: `potry-ai-agent/chat_service.py`
- Test: `potry-ai-agent/tests/test_chat_service.py`(重写 FakeLLM 并追加)

**契约定义(后续任务都按此对齐)**:

```python
StreamEvent = tuple[str, dict]
# ("tool_status", {"tool","status","args","durationMs"}) | ("token", {"content"}) | ("done", {})

class ChatService:
    def __init__(self, settings, store, llm=None, tool_registry=None, storage=None): ...
    async def stream_events(self, session_id, user_message) -> AsyncIterator[StreamEvent]: ...
    async def stream_reply(self, session_id, user_message) -> AsyncIterator[str]: ...  # 兼容 Ch01,只 yield token 文本
```

- [ ] **Step 1: 重写 `tests/test_chat_service.py` 的 FakeLLM 并追加用例**(原有三个测试保留,`make_settings` 不变;FakeLLM 换成支持 tool_calls 的双形态;文件顶部需补 `import asyncio`,新增用例里用到 `asyncio.TimeoutError`):

```python
from langchain_core.messages import AIMessage, AIMessageChunk


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
```

新增用例(含一个断言 tool_calls 消息进了内存历史的检查):

```python
from langchain_core.messages import AIMessage, ToolMessage


@pytest.mark.asyncio
async def test_tool_call_flow_reinjects_and_converges():
    from tools.registry import ToolRegistry
    from storage import ChatBase, ChatStorage
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from langchain_core.tools import tool

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

    # 落库:整体 4 行
    rows = storage.load_messages(1)
    assert [r["role"] for r in rows] == ["user", "assistant", "tool", "assistant"]


@pytest.mark.asyncio
async def test_second_tool_call_is_not_executed():
    """单轮收敛:收敛段模型再发起 tool_calls,不执行、不循环。"""
    from tools.registry import ToolRegistry
    from storage import ChatBase, ChatStorage
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from langchain_core.tools import tool

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
```

另追加一条(完整代码):

```python
@pytest.mark.asyncio
async def test_tool_error_still_converges():
    """工具失败:tool_status 尾帧 error,流式收敛与 done 照常,落库 4 行。"""
    from tools.registry import ToolRegistry
    from storage import ChatBase, ChatStorage
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from langchain_core.tools import tool

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
    assert [r["role"] for r in rows] == ["user", "assistant", "tool", "assistant"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_chat_service.py -v`
Expected: 原 3 条因 FakeLLM 构造签名变化可能 FAIL,新增 3 条 FAIL

- [ ] **Step 3: 重写 `chat_service.py`**(完整文件,替换现内容):

```python
"""单轮 Function Calling 编排:裁剪 → 非流式取 tool_calls → 执行回灌 → 流式收敛 → 落库。"""
import json
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
        async for event, payload in self.stream_events(session_id, user_message):
            if event == "token":
                yield payload["content"]

    async def stream_events(self, session_id: str, user_message: str) -> AsyncIterator[StreamEvent]:
        history = self._store.get_history(session_id)
        messages: list[BaseMessage] = history + [HumanMessage(user_message)]
        trimmed = trim_history(messages, self._settings.history_max_tokens)

        tool_records: list[dict] = [{"role": "user", "content": user_message}]
        parts: list[str] = []
        try:
            bound = self._llm.bind_tools(self._registry.get_tools() if self._registry else [])
            first_turn = await bound.ainvoke(CHAT_PROMPT.invoke({"messages": trimmed}))
            tool_call = (first_turn.tool_calls or [None])[0]
            if tool_call is not None:
                trimmed.append(first_turn)
                tool_records.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_name": tool_call["name"],
                        "tool_call_id": tool_call["id"],
                        "tool_args": json.dumps(tool_call["args"], ensure_ascii=False),
                    }
                )
                statuses = [
                    {"tool": tool_call["name"], "status": "calling", "args": tool_call["args"], "durationMs": 0}
                ]
                started = time.monotonic()
                result = await self._registry.execute(tool_call["name"], tool_call["args"])
                duration_ms = int((time.monotonic() - started) * 1000)
                statuses.append(
                    {
                        "tool": tool_call["name"],
                        "status": "done" if result.get("ok") else "error",
                        "args": tool_call["args"],
                        "durationMs": duration_ms,
                    }
                )
                for st in statuses:
                    yield ("tool_status", st)
                tool_msg = make_tool_message(tool_call["id"], tool_call["name"], result)
                trimmed.append(tool_msg)
                tool_records.append(
                    {
                        "role": "tool",
                        "content": tool_msg.content,
                        "tool_name": tool_call["name"],
                        "tool_call_id": tool_call["id"],
                    }
                )

            # 第二次调用流式收敛;若模型再发起 tool_calls:不执行不循环(单轮语义),
            # 丢弃 tool_calls 块只取文本。
            async for chunk in self._llm.astream(CHAT_PROMPT.invoke({"messages": trimmed})):
                text = chunk.content
                if isinstance(text, str) and text:
                    parts.append(text)
                    yield ("token", {"content": text})
        finally:
            # 客户端中途断开也落库,保住已产出的部分上下文(Ch01 同款语义)
            final_text = "".join(parts)
            tool_records.append({"role": "assistant", "content": final_text})
            if self._storage is not None:
                try:
                    self._storage.persist_turn(session_id, tool_records)
                except Exception as exc:  # noqa: BLE001 - 落库失败不打断对话,仅记录
                    print(f"[storage] 落库失败: {str(exc)[:200]}")
            self._store.append(session_id, user_message, final_text)

        yield ("done", {})
```

**落库行序**:`tool_records` 第一行在函数开头就置为 user 行(`tool_records: list[dict] = [{"role": "user", "content": user_message}]`),依次 append assistant(tool_calls) / tool* / 最终 assistant,行序即「user / assistant / tool* / assistant」,与测试断言一致。

- [ ] **Step 4: 跑测试确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_chat_service.py -v`
Expected: 6 passed(3 原有 + 3 新增)

- [ ] **Step 5: 全量回归 + Commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`(35 passed)

```powershell
git add potry-ai-agent/chat_service.py potry-ai-agent/tests/test_chat_service.py
git commit -m "feat(ai-agent): single-round tool-calling orchestration in chat service (ch02)"
```

---

### Task 7: SSE 事件流与 tool_status 帧(main.py)

**Files:**
- Modify: `potry-ai-agent/main.py`
- Test: `potry-ai-agent/tests/test_chat_endpoint.py`(重写)

- [ ] **Step 1: 重写 `tests/test_chat_endpoint.py`**(原 4 条改为对 `stream_events` 打桩,另加 tool_status 序列断言;`make_client` 的 `stream_fn` 现在产出 `(event, payload)` 元组):

```python
import json

from fastapi.testclient import TestClient

import main


def make_client(monkeypatch, stream_fn):
    monkeypatch.setattr(main.service, "stream_events", stream_fn)
    return TestClient(main.app)


def test_sse_event_sequence_with_tool(monkeypatch):
    async def fake_stream(session_id, message):
        yield ("meta", {"sessionId": session_id})
        yield ("tool_status", {"tool": "query_poem", "status": "calling", "args": {"keyword": "静夜思"}, "durationMs": 0})
        yield ("tool_status", {"tool": "query_poem", "status": "done", "args": {"keyword": "静夜思"}, "durationMs": 12})
        yield ("token", {"content": "你"})
        yield ("token", {"content": "好"})
        yield ("done", {"sessionId": session_id})

    client = make_client(monkeypatch, fake_stream)
    with client.stream("POST", "/agent/chat", json={"sessionId": "s1", "message": "hi"}) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join(resp.iter_text())
    assert "event: meta" in body
    assert "event: tool_status" in body
    assert body.index("event: meta") < body.index("event: tool_status") < body.index("event: token") < body.index("event: done")
    assert json.dumps({"tool": "query_poem", "status": "calling"}, ensure_ascii=False) not in body  # 整包校验下面这行
    assert '"tool": "query_poem"' in body


def test_plain_flow_without_tools(monkeypatch):
    async def fake_stream(session_id, message):
        yield ("meta", {"sessionId": session_id})
        yield ("token", {"content": "你好"})
        yield ("done", {"sessionId": session_id})

    client = make_client(monkeypatch, fake_stream)
    with client.stream("POST", "/agent/chat", json={"message": "hi"}) as resp:
        body = "".join(resp.iter_text())
    assert "event: meta" in body
    assert "event: token" in body
    assert "event: done" in body
    assert "event: tool_status" not in body


def test_upstream_failure_before_stream_returns_502(monkeypatch):
    async def broken_stream(session_id, message):
        raise ConnectionError("connect refused")
        yield  # pragma: no cover

    client = make_client(monkeypatch, broken_stream)
    resp = client.post("/agent/chat", json={"message": "hi"})
    assert resp.status_code == 502


def test_midstream_error_emits_error_event(monkeypatch):
    async def flaky_stream(session_id, message):
        yield ("meta", {"sessionId": "s1"})
        yield ("token", {"content": "半句"})
        raise ConnectionError("reset")

    client = make_client(monkeypatch, flaky_stream)
    with client.stream("POST", "/agent/chat", json={"sessionId": "s1", "message": "hi"}) as resp:
        body = "".join(resp.iter_text())
    assert "event: token" in body
    assert "event: error" in body
    assert "event: done" not in body
```

(第一条里那个 `not in body` 断言是防半包误判的写法,如觉冗余可只保留 `'"tool": "query_poem"' in body`。)

- [ ] **Step 2: 跑测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_chat_endpoint.py -v`
Expected: FAIL(TypeError: unhashable/事件结构不符)

- [ ] **Step 3: 改 `main.py`**:`/agent/chat` 整体替换为(其余不动;`stream_reply` → `stream_events`,`meta`/`done` 由服务产出,路由只编码):

```python
@app.post("/agent/chat")
async def chat(req: ChatRequest) -> EventSourceResponse:
    """SSE 流式对话:meta → tool_status* → token* → done,中途失败补发 error 事件。

    采用普通协程 + EventSourceResponse(而非生成器路由):生成器体在路由层
    TaskGroup 内消费,流前失败会被包成 ExceptionGroup,无法干净返回 502。
    """
    session_id = req.sessionId or uuid4().hex
    stream = service.stream_events(session_id, req.message)
    try:
        first = await stream.__anext__()
    except StopAsyncIteration:
        first = None
    except Exception as exc:  # noqa: BLE001 - 未开始流的上游失败按 502 返回
        raise HTTPException(
            status_code=502,
            detail={
                "message": f"上游模型调用失败: {str(exc)[:200]}",
                "upstream": settings.llm_base_url,  # 不含密钥
            },
        )

    async def gen() -> AsyncIterator[bytes]:
        pending = [first] if first is not None else []

        async def drain():
            if pending:
                ev = pending.pop(0)
                yield ev
            async for ev in stream:
                yield ev

        try:
            async for event, payload in drain():
                yield _sse(event, payload)
        except Exception as exc:  # noqa: BLE001 - 中途断流补发 error 事件
            yield _sse("error", {"message": str(exc)[:200]})
            return

    return EventSourceResponse(gen())
```

同时:
1. `from chat_service import ChatService` 下方的装配段改为(注册表 + 落库接线):

```python
from sqlalchemy.orm import sessionmaker

from db import get_engine
from storage import ChatBase, ChatStorage
from tools.poetry_tools import query_dynasty_poems, query_poem, query_poet
from tools.registry import ToolRegistry

# 模块级装配:配置 fail-fast,会话与模型管线就绪;表结构建好(幂等)
settings = load_settings()
engine = get_engine(settings.mysql_url)
ChatBase.metadata.create_all(engine)  # 幂等;MySQL 未起时这里失败要能看清报错
session_factory = sessionmaker(bind=engine)
storage = ChatStorage(session_factory)
registry = ToolRegistry(
    timeout=settings.tool_timeout_seconds,
    max_retries=settings.tool_max_retries,
)
for _t in (query_poem, query_poet, query_dynasty_poems):
    registry.register(_t)
service = ChatService(settings, SessionStore(), tool_registry=registry, storage=storage)
```

`db.py` 需补一个 `get_engine(url)`(与 `get_session_factory` 共用全局 lazy 状态;Task 8 会把这点对齐)。`test_chat_endpoint.py` 打桩只动 `main.service.stream_events`,模块级装配在测试导入时执行——SQLite 内存 `MYSQL_URL` 下 `create_all` 正常。

2. SSE 事件名与 data 原样透传:`meta`/`tool_status`/`token`/`done`/`error` 的 data 即 payload JSON(与 spec §7 契约一致)。

- [ ] **Step 4: 跑测试确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_chat_endpoint.py -v`
Expected: 4 passed

- [ ] **Step 5: 全量回归 + Commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`(35 passed)

```powershell
git add potry-ai-agent/main.py potry-ai-agent/tests/test_chat_endpoint.py
git commit -m "feat(ai-agent): sse tool_status frames and event passthrough (ch02)"
```

---

### Task 8: db.py 接线收尾 + .env 样例

**Files:**
- Modify: `potry-ai-agent/db.py`(补 `get_engine`)
- Modify: `potry-ai-agent/.env`(追加 Ch02 配置)
- Modify: `potry-ai-agent/.env.example`?(Ch01 未建则跳过,不新建文档)

- [ ] **Step 1: `db.py` 补 `get_engine`**(把 Task 2 的 `_engine/_session_factory` 两个全局收成一处):

```python
def get_engine(url: str):
    """惰性创建 engine:首调建、后续复用(MySQL 挂了只在查询时失败)。"""
    global _engine
    if _engine is None:
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def get_session_factory(url: str):
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(url))
    return _session_factory
```

- [ ] **Step 2: `.env` 追加**(密码换用户给的强密码,示例值仅开发用;不入 git):

```
MYSQL_URL=mysql+pymysql://root:publication-placeholder-mysql_password@localhost:3306/poem?charset=utf8mb4
MYSQL_ROOT_PASSWORD=CONFIGURE_LOCALLY
TOOL_TIMEOUT_SECONDS=5
TOOL_MAX_RETRIES=1
```

- [ ] **Step 3: 全量回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`
Expected: 35 passed

- [ ] **Step 4: Commit**

```powershell
git add potry-ai-agent/db.py
git commit -m "refactor(ai-agent): lazy engine singleton in db module (ch02)"
```

(`.env` 不 add——gitignore 已覆盖。)

---

### Task 9: Docker MySQL + 数据导入(基建,手动验证为主)

**Files:**
- Create: `potry-ai-agent/docker-compose.yml`
- Create: `potry-ai-agent/mysql-init/poetry-mysql.sql`(由 `poemmax-h2.sql` 转换)

- [ ] **Step 1: 写 `docker-compose.yml`**:

```yaml
services:
  mysql:
    image: mysql:8.0
    container_name: poetry-mysql
    ports:
      - "3306:3306"
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-publication-placeholder-mysql_password}
      MYSQL_DATABASE: poem
      TZ: Asia/Shanghai
    volumes:
      - ./mysql-init:/docker-entrypoint-initdb.d
      - poetry-mysql-data:/var/lib/mysql
    command: --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci

volumes:
  poetry-mysql-data:
```

- [ ] **Step 2: 转换 SQL**:`poemmax-h2.sql`(`potry-service/src/main/resources/sql/`)→ `mysql-init/poetry-mysql.sql`,只保留 `potry` 与 `writer` 两张表(工具只用这两张,其余表 YAGNI 不导),手工修 H2 语法差异:

- `DROP TABLE IF EXISTS "potry";` → `DROP TABLE IF EXISTS \`potry\`;`(反引号)
- `"col"` → `` `col` ``
- `int NOT NULL GENERATED BY DEFAULT AS IDENTITY` → `int NOT NULL AUTO_INCREMENT`
- 删 `UNIQUE ("id")` 冗余行
- 表定义末尾加 `ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`
- 原 INSERT 行保持(值不动),首行补 `INSERT INTO \`potry\` (...) VALUES ` 的反引号风格一致即可

具体做法:写一个一次性转换脚本跑也行,手工 sed 也行——产出必须是可直接被 MySQL 容器 init 执行的合法 SQL。转换命令参考(PowerShell):

```powershell
.\.venv\Scripts\python.exe -c "import re,pathlib; src=pathlib.Path(r'e:\javatexts\poetry-spring2\potry-service\src\main\resources\sql\poemmax-h2.sql').read_text(encoding='utf-8'); ..."
```

(用 Python 脚本做正则转换,输出到 `mysql-init/poetry-mysql.sql`;截取区间:从 `DROP TABLE IF EXISTS "potry"` 到 `writer` 表 INSERT 结束。)

- [ ] **Step 3: 起库并导入**

```powershell
docker compose up -d
docker exec -i poetry-mysql mysql -uroot -ppublication-placeholder-mysql_password poem -e "SELECT COUNT(*) FROM potry; SELECT COUNT(*) FROM writer;"
```

Expected: 两表行数 > 0(与 H2 库存量一致,potry 约 10 行级以实际为准)

- [ ] **Step 4: 验证 SQL 无语法错**(若 init 报错容器日志 `docker logs poetry-mysql` 里有具体行号,修到导入成功)

- [ ] **Step 5: Commit**

```powershell
git add potry-ai-agent/docker-compose.yml potry-ai-agent/mysql-init
git commit -m "feat(ai-agent): docker mysql with poetry tables imported from h2 dump (ch02)"
```

---

### Task 10: 端到端手动验收(curl + 真模型)

**Files:** 无代码改动(只跑验证;发现问题按问题修,另提交)

- [ ] **Step 1: 起服务**

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

- [ ] **Step 2: 验收句 1(工具触发)**

```powershell
curl -N -X POST http://127.0.0.1:8000/agent/chat -H "Content-Type: application/json" -d "{\"message\": \"《静夜思》是谁写的\"}"
```

Expected: 事件序列 `meta → tool_status(calling) → tool_status(done) → token* → done`,回答提及李白且基于查询结果

- [ ] **Step 3: 验收句 2(诗人工具)**:同上,`"message": "李白是什么样的诗人"`,Expected:`tool_status` 的 tool 为 `query_poet`,回答基于 writer 表简介

- [ ] **Step 4: 验收句 3(漏召回留档)**:`"message": "那首讲月亮的叫啥"`,记录实际行为(可能 `query_poem` 查不到 `found:false`),答案含"不确定/补充线索"即通过——漏召回是预期结果,写进 dev-notes 留档

- [ ] **Step 5: 负例(不触发工具)**:`"message": "今天天气真好"`,Expected: 无 `tool_status` 帧

- [ ] **Step 6: 落库核对**

```powershell
docker exec -i poetry-mysql mysql -uroot -ppublication-placeholder-mysql_password poem -e "SELECT role, tool_name FROM messages ORDER BY id DESC LIMIT 10;"
```

Expected: 能看到 user / assistant / tool / assistant 行,tool 行带 tool_name

- [ ] **Step 7: 把四句实测结果(事件序列截图或文本)记入 `dev-notes/ch02.md` 阶段留痕**

- [ ] **Step 8: Commit(dev-notes)**

```powershell
git add dev-notes/ch02.md
git commit -m "docs(dev-notes): ch02 e2e acceptance results"
```

---

### Task 11: 评估样例回归 + Prompt 微调(如需)

**Files:**
- Modify: `potry-ai-agent/prompts.py`(仅当评估暴露问题)
- Modify: `potry-ai-agent/evals/ch02_tool_eval_cases.md`(勾结果)

- [ ] **Step 1: 按 `evals/ch02_tool_eval_cases.md` 逐条跑真实 DeepSeek**(4 条,含负例)
- [ ] **Step 2: 若某条行为偏差(该调工具没调/不该调乱调),只改 `prompts.py` 的「查数据工具」一节措辞,重跑该条;不动代码**
- [ ] **Step 3: 勾选评估表 + dev-notes 追记 + Commit**

```powershell
git add potry-ai-agent/evals/ch02_tool_eval_cases.md potry-ai-agent/prompts.py dev-notes/ch02.md
git commit -m "docs(ai-agent): ch02 eval results and prompt tuning"
```

---

### Task 12: 聊天页工具徽章(Vibe Coding,不套流程)

**Files:**
- Modify: `potry-ai-agent/static/chat.html`

直接实现,不走 brainstorm/TDD/code review(用户工作要求:聊天页是 Vibe Coding 例外)。要求:

- [ ] **Step 1: SSE 解析加 `tool_status` 分支**:收到 `calling` 时在回答气泡上方渲染工具徽章行(工具中文名映射:`query_poem`→「查诗词」、`query_poet`→「查诗人」、`query_dynasty_poems`→「查朝代」),`done` 变实、「error` 变朱砂色;文案如「已查诗词 · 静夜思 · 12ms」
- [ ] **Step 2: 徽章样式贴现有宣纸/暖金/朱砂体系**(`:root` 已有变量;小圆角、11-12px 字号、`--gold` 描边),不用动画特效,克制优雅(用户审美偏好)
- [ ] **Step 3: 浏览器验证**:重跑验收句 1,确认徽章出现、状态流转、闲聊句无徽章

---

### Task 13: 收尾(全量验证 + dev-notes + 交付)

- [ ] **Step 1: 全量测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`
Expected: 全绿(35 条上下)

- [ ] **Step 2: `dev-notes/ch02.md` 补全末段留痕**(每任务一段已追记,此步只补"完结交付"小节:演示命令、测试结果、评估结果、漏召回留档、spec/plan 路径)

- [ ] **Step 3: 提交收尾**

```powershell
git add dev-notes/ch02.md
git commit -m "docs(dev-notes): ch02 complete - deliverables and verification results"
```

- [ ] **Step 4: 交付清单给用户**:演示命令(Task 10 的 curl + 聊天页 `http://127.0.0.1:8000/chat`)、测试结果(35 passed)、评估结果、dev-notes 路径、spec/plan 路径

---

## 自检记录(写完计划后已核对)

1. **Spec 覆盖**:§3 编排(Task 6/7)、§4 基础设施(Task 3)、§5 三工具(Task 4)、§6 数据层与落库(Task 2/8/9)、§7 SSE 契约(Task 7)、§8 Prompt(Task 5)、§9 错误处理(Task 3/6/7)、§10 测试策略(各任务 TDD + Task 11 评估 + Task 12 Vibe)、验收三句(Task 10)。无缺口。
2. **占位符**:Task 9 Step 2 的 SQL 转换给了命令模板与逐条语法差异清单,执行时产出 `poetry-mysql.sql` 具体内容由转换结果决定——属操作型步骤非代码占位。
3. **类型一致性**:`StreamEvent`/`stream_events`/`persist_turn`/`make_tool_message`/`get_engine` 签名前后任务一致;`stream_reply` 保留 Ch01 签名不变。
