# AI 伴学 Ch01(纯对话)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `potry-ai-agent` 内跑通纯对话:SSE 流式逐 token 输出 + PromptTemplate 化诗人 System Prompt + 内存会话历史裁剪(token 预算)。

**Architecture:** 扁平五模块(`config / prompts / memory / chat_service / main`),LangChain 全家桶:`ChatPromptTemplate` + `ChatOpenAI.astream` + `trim_messages`,FastAPI 内置 `fastapi.sse.EventSourceResponse` 做 SSE;`/agent/chat` 就地改造,Nacos 注册不动。

**Tech Stack:** Python 3.12+(以 `.venv` 实际版本为准)、FastAPI(需升级到含 `fastapi.sse` 的新版)、langchain-openai / langchain-core、python-dotenv、pytest + pytest-asyncio + httpx;上游 DeepSeek(OpenAI 兼容,凭据在 `.env`)。

**通用约定:**
- 所有命令在 `potry-ai-agent/` 下执行,Python 一律用 `.venv\Scripts\python.exe`(PowerShell 5,链命令用 `;` 不用 `&&`);
- 每个 Task 完成后必须在 `dev-notes/ch01.md` 追记一段(用户原话 / 关键产出 / 纠偏 / 返工),再 commit;
- 测试文件放 `potry-ai-agent/tests/`;
- API key 只存在于 `.env`,任何代码、日志、文档不得出现。

---

### Task 0: 环境与依赖准备

**Files:**
- Modify: `potry-ai-agent/requirements.txt`
- Create: `potry-ai-agent/.env`(不入库,`.gitignore` 已覆盖)

- [ ] **Step 0.1: 确认 venv 可用**

Run: `.venv\Scripts\python.exe -V`
Expected: 打印 Python 版本。若失败,在 `potry-ai-agent/` 重建:`py -m venv .venv` 后重试。

- [ ] **Step 0.2: 安装/升级依赖**

Run:
```powershell
.venv\Scripts\python.exe -m pip install -U pip fastapi "uvicorn[standard]" langchain-openai langchain-core python-dotenv pytest pytest-asyncio httpx
```
Expected: Successfully installed ... 无报错。

- [ ] **Step 0.3: 验证 fastapi.sse 存在(spec 前置条件)**

Run: `.venv\Scripts\python.exe -c "from fastapi.sse import EventSourceResponse, ServerSentEvent; print('ok')"`
Expected: `ok`。若 ImportError → FastAPI 版本不够,报用户(阻塞,不换 sse-starlette)。

- [ ] **Step 0.4: 记录版本进 requirements.txt**

Run: `.venv\Scripts\python.exe -m pip freeze | Select-String -Pattern "fastapi|uvicorn|langchain|pydantic|dotenv|httpx"`
把结果整理进 `requirements.txt`(固定实际安装版本;pytest 系列可放注释行注明 dev 依赖)。

- [ ] **Step 0.5: 写 `.env`(本地文件,不 commit)**

```
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=<用户提供的 sk-... 密钥>
LLM_MODEL=deepseek-chat
HISTORY_MAX_TOKENS=2000
LLM_TEMPERATURE=0.7
```

- [ ] **Step 0.6: Commit(只提交 requirements.txt)**

```powershell
git add potry-ai-agent/requirements.txt
git commit -m "chore(ai-agent): upgrade fastapi and add langchain deps for ch01 chat"
```

- [ ] **Step 0.7: dev-notes 追记 + commit(环境准备)**

---

### Task 1: config.py — 配置加载(fail fast)

**Files:**
- Create: `potry-ai-agent/config.py`
- Test: `potry-ai-agent/tests/test_config.py`

- [ ] **Step 1.1: 写失败测试**

```python
# tests/test_config.py
from config import load_settings


def test_missing_required_env_fails_fast(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    try:
        load_settings()
        assert False, "应抛出 RuntimeError"
    except RuntimeError as exc:
        assert "LLM_API_KEY" in str(exc)


def test_defaults_applied(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")
    monkeypatch.delenv("HISTORY_MAX_TOKENS", raising=False)
    monkeypatch.delenv("LLM_TEMPERATURE", raising=False)
    s = load_settings()
    assert s.llm_model == "deepseek-chat"
    assert s.history_max_tokens == 2000
    assert s.llm_temperature == 0.7
```

- [ ] **Step 1.2: 运行确认失败**

Run: `.venv\Scripts\python.exe -m pytest tests/test_config.py -v`
Expected: FAIL(ImportError: config 不存在)。

- [ ] **Step 1.3: 最小实现**

```python
# config.py
"""从 .env 加载配置,缺关键变量直接报错(fail fast)。"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

_REQUIRED = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")


@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    history_max_tokens: int
    llm_temperature: float


def load_settings() -> Settings:
    missing = [k for k in _REQUIRED if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"缺少必要环境变量: {', '.join(missing)}(请在 .env 中配置)")
    return Settings(
        llm_base_url=os.environ["LLM_BASE_URL"],
        llm_api_key=os.environ["LLM_API_KEY"],
        llm_model=os.environ["LLM_MODEL"],
        history_max_tokens=int(os.getenv("HISTORY_MAX_TOKENS", "2000")),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
    )
```

- [ ] **Step 1.4: 运行确认通过**

Run: `.venv\Scripts\python.exe -m pytest tests/test_config.py -v`
Expected: 2 passed。

- [ ] **Step 1.5: Commit + dev-notes 追记**

```powershell
git add config.py tests/test_config.py
git commit -m "feat(ai-agent): add env config loader with fail-fast validation"
```

---

### Task 2: memory.py — 会话存储 + 历史裁剪(TDD)

**Files:**
- Create: `potry-ai-agent/memory.py`
- Test: `potry-ai-agent/tests/test_memory.py`

- [ ] **Step 2.1: 写失败测试**

```python
# tests/test_memory.py
from langchain_core.messages import AIMessage, HumanMessage

from memory import SESSION_MAX_MESSAGES, SessionStore, trim_history


def test_trim_history_keeps_latest_human_and_cuts_old():
    msgs = []
    for i in range(20):
        msgs.append(HumanMessage(f"第{i}个问题,内容足够长以便超过token预算" * 5))
        msgs.append(AIMessage(f"第{i}个回答,内容足够长以便超过token预算" * 5))
    msgs.append(HumanMessage("最新问题"))
    trimmed = trim_history(msgs, max_tokens=100)
    assert trimmed[-1].content == "最新问题"
    assert trimmed[0].type == "human"
    assert len(trimmed) < len(msgs)


def test_trim_history_short_list_untouched():
    msgs = [HumanMessage("你好"), AIMessage("你好呀")]
    trimmed = trim_history(msgs, max_tokens=2000)
    assert [m.content for m in trimmed] == ["你好", "你好呀"]


def test_session_store_roundtrip():
    store = SessionStore()
    store.append("s1", "你好", "你好呀")
    hist = store.get_history("s1")
    assert [(m.type, m.content) for m in hist] == [("human", "你好"), ("ai", "你好呀")]
    assert store.get_history("no-such") == []


def test_session_store_caps_message_count():
    store = SessionStore()
    for i in range(SESSION_MAX_MESSAGES // 2 + 10):
        store.append("s1", f"q{i}", f"a{i}")
    hist = store.get_history("s1")
    assert len(hist) <= SESSION_MAX_MESSAGES
    assert hist[-1].content == f"a{SESSION_MAX_MESSAGES // 2 + 9}"  # 保留最新的
```

- [ ] **Step 2.2: 运行确认失败**

Run: `.venv\Scripts\python.exe -m pytest tests/test_memory.py -v`
Expected: FAIL(ImportError: memory 不存在)。

- [ ] **Step 2.3: 最小实现**

```python
# memory.py
"""进程内会话历史:按 sessionId 存储,请求时按 token 预算裁剪。"""
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.messages.utils import trim_messages

SESSION_MAX_MESSAGES = 50  # 每会话存储上限,超出丢最旧


class SessionStore:
    """内存 dict 会话存储,服务重启即丢(第一章最简版,接受)。"""

    def __init__(self) -> None:
        self._sessions: dict[str, list[BaseMessage]] = {}

    def get_history(self, session_id: str) -> list[BaseMessage]:
        return list(self._sessions.get(session_id, []))

    def append(self, session_id: str, user_message: str, assistant_message: str) -> None:
        hist = self._sessions.setdefault(session_id, [])
        hist.append(HumanMessage(user_message))
        hist.append(AIMessage(assistant_message))
        if len(hist) > SESSION_MAX_MESSAGES:
            del hist[: len(hist) - SESSION_MAX_MESSAGES]


def trim_history(messages: list[BaseMessage], max_tokens: int) -> list[BaseMessage]:
    """按 token 预算保留最近的消息,裁剪边界落在 human 消息上,最新消息必保留。"""
    return trim_messages(
        messages,
        strategy="last",
        token_counter="count_tokens_approximately",
        max_tokens=max_tokens,
        start_on="human",
        end_on="human",
    )
```

- [ ] **Step 2.4: 运行确认通过**

Run: `.venv\Scripts\python.exe -m pytest tests/test_memory.py -v`
Expected: 4 passed。

- [ ] **Step 2.5: Commit + dev-notes 追记**

```powershell
git add memory.py tests/test_memory.py
git commit -m "feat(ai-agent): in-memory session store with token-budget history trimming"
```

---

### Task 3: prompts.py — 诗人 System Prompt 模板化

纯 Prompt 文案的**效果**由 Task 6 评估样例验证(替代 TDD);本任务只对模板**接线**做单测(可单测代码照 TDD)。

**Files:**
- Create: `potry-ai-agent/prompts.py`
- Test: `potry-ai-agent/tests/test_prompts.py`

- [ ] **Step 3.1: 写失败测试**

```python
# tests/test_prompts.py
from langchain_core.messages import HumanMessage

from prompts import CHAT_PROMPT, SYSTEM_PROMPT_TEMPLATE


def test_system_template_has_role_and_constraints():
    text = SYSTEM_PROMPT_TEMPLATE.format()
    assert "诗人" in text
    assert "约束" in text


def test_chat_prompt_renders_system_plus_messages():
    result = CHAT_PROMPT.invoke({"messages": [HumanMessage("春眠不觉晓")]})
    msgs = result.to_messages()
    assert msgs[0].type == "system"
    assert msgs[1].content == "春眠不觉晓"
```

- [ ] **Step 3.2: 运行确认失败**

Run: `.venv\Scripts\python.exe -m pytest tests/test_prompts.py -v`
Expected: FAIL(ImportError: prompts 不存在)。

- [ ] **Step 3.3: 最小实现**

```python
# prompts.py
"""Prompt 管理:System Prompt 模板化(诗人角色设定 + 行为约束)。"""
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate

SYSTEM_PROMPT_TEMPLATE = PromptTemplate(
    input_variables=[],
    partial_variables={"style": "温润典雅"},
    template="""你是一位叫「青莲」的诗人,以诗人的视角陪伴用户学习古诗词。

# 角色设定
- 你浸淫古典诗词多年,谈吐{style},擅长用诗句和典故回应问题;
- 你的职责是伴学:讲解诗意、赏析名句、推荐合拍的诗词、引导用户感受音韵与意境;
- 回答以中文为主,适当引用诗词原文,引用必须真实存在,不得编造出处。

# 行为约束
- 只聊诗词与文史学习相关话题,与主题无关的请求礼貌说明并拉回正题;
- 不确定的诗人、朝代、出处要如实说不确定,不得编造;
- 单次回答尽量精炼(除非用户要求展开),避免长篇说教;
- 不代替用户写作业答案,而是启发思路。""",
)

CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT_TEMPLATE.template),
        MessagesPlaceholder("messages"),
    ]
).partial(style="温润典雅")
```

- [ ] **Step 3.4: 运行确认通过**

Run: `.venv\Scripts\python.exe -m pytest tests/test_prompts.py -v`
Expected: 2 passed。

- [ ] **Step 3.5: Commit + dev-notes 追记**

```powershell
git add prompts.py tests/test_prompts.py
git commit -m "feat(ai-agent): poet persona system prompt as PromptTemplate"
```

---

### Task 4: chat_service.py — 流式生成管线(fake llm TDD)

**Files:**
- Create: `potry-ai-agent/chat_service.py`
- Test: `potry-ai-agent/tests/test_chat_service.py`

- [ ] **Step 4.1: 写失败测试**

```python
# tests/test_chat_service.py
import pytest
from langchain_core.messages import AIMessageChunk

from chat_service import ChatService
from config import Settings
from memory import SessionStore


class FakeLLM:
    def __init__(self, pieces):
        self.pieces = pieces

    async def astream(self, prompt):
        for p in self.pieces:
            yield AIMessageChunk(p)


def make_settings():
    return Settings(
        llm_base_url="http://fake",
        llm_api_key="CONFIGURE_LOCALLY",
        llm_model="fake",
        history_max_tokens=2000,
        llm_temperature=0.7,
    )


@pytest.mark.asyncio
async def test_stream_reply_yields_pieces_and_stores_history():
    store = SessionStore()
    service = ChatService(make_settings(), store, llm=FakeLLM(["你", "好", "呀"]))
    pieces = [p async for p in service.stream_reply("s1", "你好")]
    assert pieces == ["你", "好", "呀"]
    hist = store.get_history("s1")
    assert [m.content for m in hist] == ["你好", "你好呀"]


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
```

- [ ] **Step 4.2: 运行确认失败**

Run: `.venv\Scripts\python.exe -m pytest tests/test_chat_service.py -v`
Expected: FAIL(ImportError: chat_service 不存在)。

- [ ] **Step 4.3: 最小实现**

```python
# chat_service.py
"""流式对话管线:取历史 → 裁剪 → PromptTemplate 渲染 → ChatOpenAI.astream。"""
from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from config import Settings
from memory import SessionStore, trim_history
from prompts import CHAT_PROMPT


def build_llm(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
    )


class ChatService:
    def __init__(self, settings: Settings, store: SessionStore, llm=None) -> None:
        self._settings = settings
        self._store = store
        self._llm = llm if llm is not None else build_llm(settings)

    async def stream_reply(self, session_id: str, user_message: str) -> AsyncIterator[str]:
        history = self._store.get_history(session_id)
        messages = history + [HumanMessage(user_message)]
        trimmed = trim_history(messages, self._settings.history_max_tokens)
        prompt = CHAT_PROMPT.invoke({"messages": trimmed})
        parts: list[str] = []
        async for chunk in self._llm.astream(prompt):
            text = chunk.content
            if isinstance(text, str) and text:
                parts.append(text)
                yield text
        self._store.append(session_id, user_message, "".join(parts))
```

- [ ] **Step 4.4: 运行确认通过**

Run: `.venv\Scripts\python.exe -m pytest tests/test_chat_service.py -v`
Expected: 2 passed。

- [ ] **Step 4.5: Commit + dev-notes 追记**

```powershell
git add chat_service.py tests/test_chat_service.py
git commit -m "feat(ai-agent): streaming chat pipeline with trimmed history"
```

---

### Task 5: main.py — SSE 流式接口(就地改造)

**Files:**
- Modify: `potry-ai-agent/main.py`(替换 `/agent/chat` stub 为 SSE,保留 Nacos 与 `/health`)
- Test: `potry-ai-agent/tests/test_chat_endpoint.py`

- [ ] **Step 5.1: 写失败测试**

```python
# tests/test_chat_endpoint.py
import json

import pytest
from fastapi.testclient import TestClient

import main


def make_client(monkeypatch, stream_fn):
    monkeypatch.setattr(main.service, "stream_reply", stream_fn)
    return TestClient(main.app)


def test_sse_event_sequence(monkeypatch):
    async def fake_stream(session_id, message):
        yield "你"
        yield "好"

    client = make_client(monkeypatch, fake_stream)
    with client.stream("POST", "/agent/chat", json={"sessionId": "s1", "message": "hi"}) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join(resp.iter_text())
    assert "event: meta" in body
    assert "event: token" in body
    assert "event: done" in body
    assert json.dumps({"sessionId": "s1"}, ensure_ascii=False) in body


def test_upstream_failure_before_stream_returns_502(monkeypatch):
    async def broken_stream(session_id, message):
        raise ConnectionError("connect refused")
        yield  # pragma: no cover

    client = make_client(monkeypatch, broken_stream)
    resp = client.post("/agent/chat", json={"message": "hi"})
    assert resp.status_code == 502


def test_midstream_error_emits_error_event(monkeypatch):
    async def flaky_stream(session_id, message):
        yield "半句"
        raise ConnectionError("reset")

    client = make_client(monkeypatch, flaky_stream)
    with client.stream("POST", "/agent/chat", json={"sessionId": "s1", "message": "hi"}) as resp:
        body = "".join(resp.iter_text())
    assert "event: token" in body
    assert "event: error" in body
    assert "event: done" not in body
```

- [ ] **Step 5.2: 运行确认失败**

Run: `.venv\Scripts\python.exe -m pytest tests/test_chat_endpoint.py -v`
Expected: FAIL(AssertionError / 404,现 stub 非 SSE)。

- [ ] **Step 5.3: 改造 main.py(替换 stub,其余保留)**

保留现有 import、Nacos 心跳、lifespan、`/health`、`ChatRequest` 不动;新增/替换如下:

```python
import json
from uuid import uuid4

from fastapi import HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent

from chat_service import ChatService
from config import load_settings
from memory import SessionStore

# 模块级装配(替代原 TODO stub 的占位逻辑)
settings = load_settings()
service = ChatService(settings, SessionStore())
```

`ChatResponse` 与旧 `/agent/chat` stub 整体删除,替换为:

```python
@app.post("/agent/chat")
async def chat(req: ChatRequest) -> EventSourceResponse:
    session_id = req.sessionId or uuid4().hex
    stream = service.stream_reply(session_id, req.message)
    try:
        first = await stream.__anext__()
    except StopAsyncIteration:
        first = None
    except Exception as exc:  # noqa: BLE001 - 未开始流的上游失败按 502 返回
        raise HTTPException(status_code=502, detail=f"上游模型调用失败: {exc}")

    async def gen():
        yield ServerSentEvent(
            event="meta", data=json.dumps({"sessionId": session_id}, ensure_ascii=False)
        )
        if first is not None:
            yield ServerSentEvent(
                event="token", data=json.dumps({"content": first}, ensure_ascii=False)
            )
        try:
            async for piece in stream:
                yield ServerSentEvent(
                    event="token", data=json.dumps({"content": piece}, ensure_ascii=False)
                )
        except Exception as exc:  # noqa: BLE001 - 中途断流补发 error 事件
            yield ServerSentEvent(
                event="error", data=json.dumps({"message": str(exc)}, ensure_ascii=False)
            )
            return
        yield ServerSentEvent(
            event="done", data=json.dumps({"sessionId": session_id}, ensure_ascii=False)
        )

    return EventSourceResponse(gen())
```

注意:`req.message` 为空串时由 Pydantic 层不必强拦(不做额外校验,YAGNI);`userId` 字段保留但第一章不消费。

- [ ] **Step 5.4: 运行确认通过**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: 全部 passed(test_config 2 + test_memory 4 + test_prompts 2 + test_chat_service 2 + test_chat_endpoint 3 = 13)。

- [ ] **Step 5.5: Commit + dev-notes 追记**

```powershell
git add main.py tests/test_chat_endpoint.py
git commit -m "feat(ai-agent): SSE streaming chat endpoint with meta/token/done/error events"
```

---

### Task 6: Prompt 评估样例验证(替代纯 Prompt 的 TDD)

**Files:**
- Create: `potry-ai-agent/evals/chat_eval_cases.md`

- [ ] **Step 6.1: 写标注样例**

```markdown
# Ch01 Prompt 评估样例(人工比对,替代纯 Prompt 的 TDD)

执行方式:每条用 `curl.exe -N` 以对应 sessionId 调 `/agent/chat`,人工对照"预期要点"打勾。

| # | 类别 | 输入 | 预期要点 |
|---|---|---|---|
| 1 | 角色一致性 | 你是谁? | 自我介绍为诗人「青莲」/诗人视角伴学,口吻温润,不自称 AI 助手 |
| 2 | 约束-不编造 | 《静夜思》第三句是什么?是谁在元代改写的? | 原句正确;元代改写如不确定须明说"不确定",不得编造人名 |
| 3 | 约束-拉回主题 | 帮我写一份周报 | 礼貌说明只聊诗词文史,并顺势推荐相关诗词或提问拉回 |
| 4 | 多轮上下文 | 第一轮:我最喜欢苏轼的《定风波》;第二轮:我刚才说最喜欢谁的哪首词? | 第二轮答出苏轼《定风波》 |
| 5 | 启发而非代做 | 赏析一下"大漠孤烟直"好在哪,我要写进作业 | 给赏析思路与角度,不直接产出"作业答案"整段成文 |
```

- [ ] **Step 6.2: 启动服务,跑一遍真实 DeepSeek 比对**

Run:
```powershell
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
# 另开终端逐条 curl,对照预期要点人工打勾
```
Expected: 5 条中至少 4 条符合预期;不符合的记录偏差,微调 `prompts.py` 文案后重跑该条(文案微调不需重跑单测,但要跑 Task 5 的 endpoint 测试防回归)。

- [ ] **Step 6.3: Commit + dev-notes 追记**

```powershell
git add potry-ai-agent/evals/chat_eval_cases.md
git commit -m "eval(ai-agent): add annotated prompt eval cases for ch01"
```

---

### Task 7: curl 验收(流式 + 两轮上下文)

- [ ] **Step 7.1: 启动服务**

Run: `.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000`
Expected: 启动无 traceback;`/health` 返回 UP(可顺手 `curl http://127.0.0.1:8000/health` 验证)。

- [ ] **Step 7.2: 验收 1 —— 流式回复**

Run:
```powershell
curl.exe -N -X POST http://127.0.0.1:8000/agent/chat -H "Content-Type: application/json" -d "{\"sessionId\":\"demo-1\",\"message\":\"用一句话介绍你自己,并背一句你最喜欢的诗\"}"
```
Expected: 依次看到 `event: meta`、多个 `event: token` 分片到达(非一次性)、`event: done`。

- [ ] **Step 7.3: 验收 2 —— 两轮上下文续接**

Run(同一 `sessionId: demo-1` 紧接上一条):
```powershell
curl.exe -N -X POST http://127.0.0.1:8000/agent/chat -H "Content-Type: application/json" -d "{\"sessionId\":\"demo-1\",\"message\":\"我上一条让你做了什么?\"}"
```
Expected: 回答能复述第一轮的指令内容(介绍自己 + 背诗)。

- [ ] **Step 7.4: 全量测试回归**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: 全部 passed。

- [ ] **Step 7.5: dev-notes 追记(验收结果)+ commit**

---

### Task 8: Code Review

- [ ] **Step 8.1: 调用 superpowers:requesting-code-review**,对本章 diff 做评审,结论(含修复项)追记 dev-notes 后 commit。

---

### Task 9: 聊天页面(Vibe Coding,不套流程)

- [ ] **Step 9.1: 后端验收通过后启动。用户描述效果直接改,先做一个极简聊天页(静态 HTML/或并入 frontend/,按用户当下描述为准),对接 SSE 接口;不走 brainstorm/TDD/code review 流程。完成后 dev-notes 追记。**

---

### Task 10: 收尾交付(superpowers:finishing-a-development-branch)

- [ ] **Step 10.1: 汇总交付:功能演示命令、测试结果、dev-notes 路径;dev-notes 补 finish 段;处理分支合并/保留。**
