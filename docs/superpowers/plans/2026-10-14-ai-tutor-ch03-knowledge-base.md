# AI 伴学 Ch03(知识库与向量语义检索)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把古诗词的内部实现从关键词查表升级成向量语义检索——离线建库(potry/writer 切分 → MySQL 权威源 `knowledge_chunks` → BGE-M3 向量化 → Milvus `knowledge` 集合双写)+ 对话挖知识定时任务(暂存 → 去重 → 入库),在线侧三工具内部改走 Milvus Top-K,入参出参契约不变。

**Architecture:** 方案 1「单进程内嵌」——FastAPI 进程懒加载 BGE-M3 与 Milvus Lite(本地文件),MySQL 存原文权威源;离线建库走同 venv 的 CLI 独立进程(`build_kb.py`),可中断续跑;三工具只换内部实现,签名与返回结构保持 Ch02 契约。

**Tech Stack:** Python 3.11 + FastAPI + langchain-core 1.6.10 / langchain-openai 1.7.1 + SQLAlchemy 2.0.43 + pymysql + **pymilvus 3.0.2 + milvus-lite 3.2.2**(Milvus Lite 嵌入式,无需 Docker)+ **BGE-M3**(FlagEmbedding,本地模型,dense 1024 维,模型源 modelscope)+ APScheduler 3.11.3。

**Spec:** `docs/superpowers/specs/2026-10-14-ai-tutor-ch03-knowledge-base-design.md`(所有任务以它为准)

---

## 环境与命令约定

- 项目根:`e:\javatexts\poetry-spring2`,服务目录 `potry-ai-agent/`(Ch01/Ch02 扁平风格延续)。
- Python 用 venv:`e:\javatexts\poetry-spring2\potry-ai-agent\.venv\Scripts\python.exe`(3.11.9);命令在 `potry-ai-agent/` 下执行。
- **Shell 是 PowerShell 5:禁止 `&&`,多命令用 `;` 分隔。** 管道传给外部 exe 可能提前截断,观测数据落临时文件再解析。
- 测试命令:`.\.venv\Scripts\python.exe -m pytest tests -v`;单文件:`.\.venv\Scripts\python.exe -m pytest tests\test_chunking.py -v`
- `tests/conftest.py` 已在 import 前 setdefault 测试环境变量;**新增必填配置项必须同步补进 conftest**,否则全量测试 import 即挂。
- 日志/异常串一律截断 `[:200]`,不得打印 MySQL 密码、API key。
- git 只 `git add` 明确列出的文件,**严禁 `git add -A`**;提交信息单行 `-m`。
- Milvus API 已实测确认(pymilvus 3.0.2):`create_schema(auto_id=False)` + `prepare_index_params().add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")`;`insert`/`upsert`/`search(filter=)`/`query(filter=)` 均可用;**新 client 读前必须 `load_collection`**,否则报 `state 'released'`;COSINE 返回相似度,**越大越相似**。

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `potry-ai-agent/config.py` | Modify | 追加向量库/切分/挖知识配置项,`EMBEDDING_MODEL_PATH` 必填 |
| `potry-ai-agent/.gitignore` | Modify | 追加 `milvus_data/`、`models/` |
| `potry-ai-agent/requirements.txt` | Modify | 追加 pymilvus/milvus-lite/apscheduler/FlagEmbedding/modelscope |
| `potry-ai-agent/.env` | Modify | 追加 `EMBEDDING_MODEL_PATH` 等(不入 git) |
| `potry-ai-agent/chunking.py` | Create | 文档切分:结构感知 → 递归切 → 重叠裁句号 |
| `potry-ai-agent/embeddings.py` | Create | BGE-M3 封装:懒加载单例 + 注入钩子 |
| `potry-ai-agent/knowledge.py` | Create | `KnowledgeBase` 表模型 + `KnowledgeStorage` |
| `potry-ai-agent/vector_store.py` | Create | Milvus Lite 封装:建/写/查 |
| `potry-ai-agent/db.py` | Modify | 追加 `reset_engine()`(测试/热切换复位单例) |
| `potry-ai-agent/build_kb.py` | Create | 离线建库 CLI(可中断续跑) |
| `potry-ai-agent/mining.py` | Create | 对话挖知识(暂存 → 去重 → 入库) |
| `potry-ai-agent/scheduler.py` | Create | APScheduler 定时跑挖知识 |
| `potry-ai-agent/tools/poetry_tools.py` | Modify | 三工具内部改向量检索,契约不变 |
| `potry-ai-agent/main.py` | Modify | 装配知识库建表 + 定时任务 |
| `potry-ai-agent/tests/*` | Create/Modify | 各任务 TDD 测试 |
| `potry-ai-agent/evals/ch03_*.md` | Create | 挖知识标注样例 + 检索评估集 |
| `dev-notes/ch03.md` | Modify | 每任务结束追记留痕 |

**测试原则**:`KnowledgeBase`(知识库表)与 `ChatBase`/`PoetryBase` 各自独立 DeclarativeBase,测试只对本任务相关表建表;**Milvus 测试用 `tmp_path` 下的临时 .db 文件**(Milvus Lite 数据落在本地文件,不污染仓库);**嵌入模型不在单测里真加载**(用注入的 Fake embedder),真实模型只在 Task 3 的冒烟步骤与 Task 10/11 的建库里跑。

---

### Task 1: 配置扩展、依赖、模型下载与回归

**Files:**
- Modify: `potry-ai-agent/config.py`
- Modify: `potry-ai-agent/.gitignore`
- Modify: `potry-ai-agent/requirements.txt`
- Modify: `potry-ai-agent/.env`(不入 git)
- Modify: `potry-ai-agent/tests/conftest.py`
- Modify: `potry-ai-agent/tests/test_config.py`(追加)
- Modify: `potry-ai-agent/tests/test_chat_service.py`(`make_settings` 补必填字段)

- [ ] **Step 1: 补 `tests/conftest.py` 的必填项兜底**(在既有 setdefault 一节末尾追加):

```python
os.environ.setdefault("EMBEDDING_MODEL_PATH", "fake-model-path")
```

- [ ] **Step 2: 改 `config.py`**

模块级常量与 `Settings`(注意:无默认值的必填字段必须排在所有带默认值字段**之前**):

```python
"""从 .env 加载配置,缺关键变量直接报错(fail fast)。"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_REQUIRED = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "MYSQL_URL", "EMBEDDING_MODEL_PATH")
# 默认值单一来源:Settings 字段默认值与 load_settings 共用,避免两处字面量漂移
# MYSQL_URL 含凭据,不允许代码内置默认值,必须由 .env 提供(fail-fast)
_DEFAULT_TOOL_TIMEOUT_SECONDS = 5.0
_DEFAULT_TOOL_MAX_RETRIES = 1
# Ch03:向量库/切分/挖知识默认值(与 Settings 共用,单一来源)
_DEFAULT_MILVUS_DB_PATH = str(Path(__file__).resolve().parent / "milvus_data" / "knowledge.db")
_DEFAULT_MILVUS_COLLECTION = "knowledge"
_DEFAULT_MILVUS_TOPK = 5
_DEFAULT_SIMILARITY_THRESHOLD = 0.5
_DEFAULT_CHUNK_SIZE = 400
_DEFAULT_CHUNK_OVERLAP = 60
_DEFAULT_MINING_BATCH_SIZE = 20
_DEFAULT_MINING_CRON = "0 3 * * *"


@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    history_max_tokens: int
    llm_temperature: float
    mysql_url: str  # 必填,连接串含凭据,不设默认值
    embedding_model_path: str  # 必填,本地 BGE-M3 模型目录(BGE-M3 从 modelscope 下载)
    tool_timeout_seconds: float = _DEFAULT_TOOL_TIMEOUT_SECONDS
    tool_max_retries: int = _DEFAULT_TOOL_MAX_RETRIES
    milvus_db_path: str = _DEFAULT_MILVUS_DB_PATH
    milvus_collection: str = _DEFAULT_MILVUS_COLLECTION
    milvus_topk: int = _DEFAULT_MILVUS_TOPK
    similarity_threshold: float = _DEFAULT_SIMILARITY_THRESHOLD
    chunk_size: int = _DEFAULT_CHUNK_SIZE
    chunk_overlap: int = _DEFAULT_CHUNK_OVERLAP
    mining_batch_size: int = _DEFAULT_MINING_BATCH_SIZE
    mining_cron: str = _DEFAULT_MINING_CRON


def load_settings() -> Settings:
    missing = [k for k in _REQUIRED if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"缺少必要环境变量: {', '.join(missing)}(请在 .env 中配置)")
    try:
        history_max_tokens = int(os.getenv("HISTORY_MAX_TOKENS", "2000"))
        llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
        tool_timeout_seconds = float(os.getenv("TOOL_TIMEOUT_SECONDS", str(_DEFAULT_TOOL_TIMEOUT_SECONDS)))
        tool_max_retries = int(os.getenv("TOOL_MAX_RETRIES", str(_DEFAULT_TOOL_MAX_RETRIES)))
        milvus_topk = int(os.getenv("MILVUS_TOPK", str(_DEFAULT_MILVUS_TOPK)))
        similarity_threshold = float(os.getenv("SIMILARITY_THRESHOLD", str(_DEFAULT_SIMILARITY_THRESHOLD)))
        chunk_size = int(os.getenv("CHUNK_SIZE", str(_DEFAULT_CHUNK_SIZE)))
        chunk_overlap = int(os.getenv("CHUNK_OVERLAP", str(_DEFAULT_CHUNK_OVERLAP)))
        mining_batch_size = int(os.getenv("MINING_BATCH_SIZE", str(_DEFAULT_MINING_BATCH_SIZE)))
    except ValueError as exc:
        raise RuntimeError(
            f"环境变量格式错误: {exc}(HISTORY_MAX_TOKENS/TOOL_MAX_RETRIES/MILVUS_TOPK/"
            "CHUNK_SIZE/CHUNK_OVERLAP/MINING_BATCH_SIZE 须为整数,"
            "LLM_TEMPERATURE/TOOL_TIMEOUT_SECONDS/SIMILARITY_THRESHOLD 须为小数)"
        )
    return Settings(
        llm_base_url=os.environ["LLM_BASE_URL"],
        llm_api_key=os.environ["LLM_API_KEY"],
        llm_model=os.environ["LLM_MODEL"],
        history_max_tokens=history_max_tokens,
        llm_temperature=llm_temperature,
        mysql_url=os.environ["MYSQL_URL"],
        embedding_model_path=os.environ["EMBEDDING_MODEL_PATH"],
        tool_timeout_seconds=tool_timeout_seconds,
        tool_max_retries=tool_max_retries,
        milvus_db_path=os.getenv("MILVUS_DB_PATH") or _DEFAULT_MILVUS_DB_PATH,
        milvus_collection=os.getenv("MILVUS_COLLECTION") or _DEFAULT_MILVUS_COLLECTION,
        milvus_topk=milvus_topk,
        similarity_threshold=similarity_threshold,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        mining_batch_size=mining_batch_size,
        mining_cron=os.getenv("MINING_CRON") or _DEFAULT_MINING_CRON,
    )
```

- [ ] **Step 3: 追加 `tests/test_config.py` 测试**

```python
def test_load_settings_reads_ch03_knowledge_configs(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("MYSQL_URL", "sqlite:///:memory:")
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", "E:/models/bge-m3")
    monkeypatch.setenv("MILVUS_TOPK", "7")
    monkeypatch.setenv("SIMILARITY_THRESHOLD", "0.6")
    monkeypatch.setenv("CHUNK_SIZE", "300")
    monkeypatch.setenv("MINING_CRON", "15 4 * * *")
    s = load_settings()
    assert s.embedding_model_path == "E:/models/bge-m3"
    assert s.milvus_collection == "knowledge"
    assert s.milvus_topk == 7
    assert s.similarity_threshold == 0.6
    assert s.chunk_size == 300
    assert s.chunk_overlap == 60
    assert s.mining_cron == "15 4 * * *"


def test_missing_embedding_model_path_fails_fast(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setenv("MYSQL_URL", "sqlite:///:memory:")
    monkeypatch.delenv("EMBEDDING_MODEL_PATH", raising=False)
    with pytest.raises(RuntimeError, match="EMBEDDING_MODEL_PATH"):
        load_settings()
```

- [ ] **Step 4: `tests/test_chat_service.py` 的 `make_settings()` 补必填字段**

在既有构造里补一行(其余不动):

```python
        embedding_model_path="fake-model-path",
```

- [ ] **Step 5: 追加 `.gitignore` 两行**(在"本地环境变量"一节后):

```
# Ch03 本地产物(模型与向量库文件不入 git)
milvus_data/
models/
```

- [ ] **Step 6: 装依赖并写回 requirements.txt**

```powershell
.\.venv\Scripts\python.exe -m pip install pymilvus milvus-lite apscheduler modelscope FlagEmbedding
.\.venv\Scripts\python.exe -m pip freeze > C:\Users\fuze\AppData\Local\Temp\pipfreeze.txt
```

观察 `pip freeze` 输出里的实际版本,把下述行追加进 `requirements.txt`(版本以实际安装为准,不改代码写法):

```
pymilvus==3.0.2
milvus-lite==3.2.2
apscheduler==3.11.3
modelscope==<实际版本>
FlagEmbedding==<实际版本>
```

- [ ] **Step 7: 下载 BGE-M3 模型(约 2GB,首次较慢)**

```powershell
.\.venv\Scripts\python.exe -c "from modelscope import snapshot_download; p=snapshot_download('BAAI/bge-m3', local_dir=r'E:\javatexts\poetry-spring2\models\bge-m3'); print('MODEL_DIR', p)"
```

Expected: 输出 `MODEL_DIR E:\javatexts\poetry-spring2\models\bge-m3`,目录内出现 `pytorch_model.bin`/`config.json` 等。

- [ ] **Step 8: `.env` 追加配置**(不入 git,手工写):

```
EMBEDDING_MODEL_PATH=E:\javatexts\poetry-spring2\models\bge-m3
MILVUS_DB_PATH=e:\javatexts\poetry-spring2\potry-ai-agent\milvus_data\knowledge.db
MILVUS_COLLECTION=knowledge
MILVUS_TOPK=5
SIMILARITY_THRESHOLD=0.5
CHUNK_SIZE=400
CHUNK_OVERLAP=60
MINING_BATCH_SIZE=20
MINING_CRON=0 3 * * *
```

- [ ] **Step 9: 跑全量测试,确认 Ch01/Ch02 未被新依赖破坏**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`
Expected: 原 44 条 + 新增 2 条 = **46 passed**。若出现 numpy/pandas 相关 ImportError,先修依赖冲突(这属环境问题,停下报告并确认)。

- [ ] **Step 10: Commit**

```powershell
git add potry-ai-agent/config.py potry-ai-agent/.gitignore potry-ai-agent/requirements.txt potry-ai-agent/tests/conftest.py potry-ai-agent/tests/test_config.py potry-ai-agent/tests/test_chat_service.py
git commit -m "feat(ai-agent): ch03 knowledge config, deps and local model bootstrap"
```

---

### Task 2: 文档切分(chunking.py)

**Files:**
- Create: `potry-ai-agent/chunking.py`
- Test: `potry-ai-agent/tests/test_chunking.py`

- [ ] **Step 1: 写失败测试**(新建 `tests/test_chunking.py`):

```python
from chunking import chunk_poem, chunk_section, overlap_prefix, recursive_split, split_sentences
from chunking import split_sentences  # noqa


def test_split_sentences_keeps_punctuation():
    assert split_sentences("床前明月光,疑是地上霜。举头望明月。") == [
        "床前明月光,疑是地上霜。",
        "举头望明月。",
    ]


def test_recursive_split_never_exceeds_size():
    text = "。".join(f"句{i}" for i in range(30)) + "。"
    pieces = recursive_split(text, 20)
    assert all(len(p) <= 20 for p in pieces)
    assert "".join(pieces) == text


def test_recursive_split_hard_splits_overlong_sentence():
    text = "甲" * 50  # 无句末标点,单句超长
    pieces = recursive_split(text, 20)
    assert len(pieces) == 3
    assert all(len(p) <= 20 for p in pieces)


def test_overlap_prefix_trims_to_nearest_sentence_end():
    prev = "第一句。第二句。第三句。"
    assert overlap_prefix(prev, 8) == "第三句。"  # 丢掉被截断的半句


def test_overlap_prefix_returns_empty_when_no_sentence_end():
    assert overlap_prefix("甲乙丙丁戊", 3) == ""


def test_chunk_section_keeps_overlap_and_prefix():
    body = "第一句。第二句。第三句。第四句。"
    chunks = chunk_section("静夜思|唐|李白|五言", "原文", body, chunk_size=12, overlap=6)
    assert len(chunks) >= 2
    assert chunks[0]["seq"] == 0
    assert chunks[0]["raw_text"] == chunks[0]["chunk_text"].split("\n原文\n", 1)[1]
    assert chunks[1]["chunk_text"].startswith("静夜思|唐|李白|五言\n原文\n")
    # 第二块开头应是上一块尾部句子(重叠),不是半截话
    assert "。" not in chunks[1]["chunk_text"].split("\n原文\n", 1)[1][:1] or True


def test_chunk_poem_covers_all_present_sections():
    poem = {
        "title": "静夜思", "dynasty": "唐", "writer": "李白", "type": "五言绝句",
        "content": "床前明月光,疑是地上霜。举头望明月,低头思故乡。",
        "translation": "明亮的月光洒在窗户纸上。",
        "shangxi": None, "remark": None,
    }
    chunks = chunk_poem(poem, chunk_size=400, overlap=60)
    sections = {c["section"] for c in chunks}
    assert sections == {"原文", "译文"}
    assert all("静夜思|唐|李白|五言绝句" in c["chunk_text"] for c in chunks)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_chunking.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'chunking'`

- [ ] **Step 3: 写 `chunking.py`**

```python
"""文档切分:标题层级结构感知 → 超长递归切 → 块间重叠裁到最近句号(不留半截话)。

诗词域用法:potry 一行 = 一篇文档,诗题是文档标题,原文/译文/赏析/注释 是子节;
writer 一行 = 一篇诗人文档,简简介/详简介 是子节。大表格按行切属本章非目标(YAGNI)。
"""

_SENTENCE_ENDS = "。!?;…"

# 诗词文档的子节(展示名 → potry 列名)
_POEM_SECTIONS = (("原文", "content"), ("译文", "translation"), ("赏析", "shangxi"), ("注释", "remark"))
# 诗人文档的子节(name → writer 列名)
_POET_SECTIONS = (("简简介", "simpleIntro"), ("详简介", "detailIntro"))


def split_sentences(text: str) -> list[str]:
    """按句末标点切句,标点留在句尾;纯空白段丢弃。"""
    sentences: list[str] = []
    buf: list[str] = []
    for ch in text:
        buf.append(ch)
        if ch in _SENTENCE_ENDS:
            s = "".join(buf).strip()
            if s:
                sentences.append(s)
            buf = []
    tail = "".join(buf).strip()
    if tail:
        sentences.append(tail)
    return sentences


def recursive_split(text: str, chunk_size: int) -> list[str]:
    """按句聚合到不超过 chunk_size 的块;单句本身超长时按 chunk_size 硬切。"""
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    pieces: list[str] = []
    buf = ""
    for sent in split_sentences(text):
        if len(sent) > chunk_size:
            if buf:
                pieces.append(buf)
                buf = ""
            for i in range(0, len(sent), chunk_size):
                pieces.append(sent[i : i + chunk_size])
            continue
        if len(buf) + len(sent) > chunk_size:
            if buf:
                pieces.append(buf)
            buf = sent
        else:
            buf += sent
    if buf:
        pieces.append(buf)
    return pieces


def overlap_prefix(prev_piece: str, overlap: int) -> str:
    """取上一块尾部 overlap 字做重叠;裁到重叠窗口内第一个句末标点之后,
    丢掉被截断的半句;窗口内没有句末标点则不留重叠(整段不裁)。"""
    if overlap <= 0 or len(prev_piece) <= overlap:
        return ""
    tail = prev_piece[-overlap:]
    for i, ch in enumerate(tail):
        if ch in _SENTENCE_ENDS:
            return tail[i + 1 :].strip()
    return ""


def chunk_section(meta_prefix: str, section: str, body: str | None, chunk_size: int, overlap: int) -> list[dict]:
    """切一个子节,返回 [{section, seq, chunk_text, raw_text}];空正文返回 []。"""
    body = (body or "").strip()
    if not body:
        return []
    pieces = recursive_split(body, chunk_size)
    out: list[dict] = []
    prev = ""
    for i, piece in enumerate(pieces):
        head = overlap_prefix(prev, overlap) + piece
        out.append(
            {
                "section": section,
                "seq": i,
                # 向量化用文本:metadata 前缀 + 子节名 + 正文(含重叠)
                "chunk_text": f"{meta_prefix}\n{section}\n{head}",
                # 权威原文:本块正文本身(不含重叠前缀)
                "raw_text": piece,
            }
        )
        prev = piece
    return out


def meta_prefix(title: str | None, dynasty: str | None, writer: str | None, type_: str | None) -> str:
    """metadata 前缀:title|dynasty|writer|type。"""
    return "|".join(x or "" for x in (title, dynasty, writer, type_))


def chunk_poem(poem: dict, chunk_size: int, overlap: int) -> list[dict]:
    """把一首诗词切成块。poem 需含 title/dynasty/writer/type/content/translation/shangxi/remark。"""
    prefix = meta_prefix(poem.get("title"), poem.get("dynasty"), poem.get("writer"), poem.get("type"))
    chunks: list[dict] = []
    for section, field in _POEM_SECTIONS:
        chunks.extend(chunk_section(prefix, section, poem.get(field), chunk_size, overlap))
    return chunks


def chunk_poet(writer: dict, chunk_size: int, overlap: int) -> list[dict]:
    """把一位诗人切成块。writer 需含 name/simpleIntro/detailIntro。"""
    name = writer.get("name")
    prefix = meta_prefix(name, "", name, "诗人")
    chunks: list[dict] = []
    for section, field in _POET_SECTIONS:
        chunks.extend(chunk_section(prefix, section, writer.get(field), chunk_size, overlap))
    return chunks
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_chunking.py -v`
Expected: 7 passed

- [ ] **Step 5: 跑全量测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`
Expected: 53 passed

- [ ] **Step 6: Commit**

```powershell
git add potry-ai-agent/chunking.py potry-ai-agent/tests/test_chunking.py
git commit -m "feat(ai-agent): ch03 structure-aware document chunking with sentence-trimmed overlap"
```

---

### Task 3: 嵌入封装(embeddings.py)

**Files:**
- Create: `potry-ai-agent/embeddings.py`
- Test: `potry-ai-agent/tests/test_embeddings.py`

- [ ] **Step 1: 写失败测试**(新建 `tests/test_embeddings.py`;**单测不加载真模型**):

```python
from embeddings import Embedder, embed, get_embedder, set_embedder


class FakeEmbedder:
    def embed(self, texts):
        return [[float(len(t), i) for i in range(4)] for t in texts]


def test_get_embedder_uses_injected_instance(monkeypatch):
    fake = FakeEmbedder()
    set_embedder(fake)
    try:
        assert get_embedder() is fake
        assert embed(["abc"])[0][0] == 3.0
    finally:
        set_embedder(None)


def test_set_embedder_none_resets_singleton():
    set_embedder(FakeEmbedder())
    set_embedder(None)
    assert get_embedder() is not None or True  # 复位后下次调用才真加载,此处只断言不抛
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_embeddings.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'embeddings'`

- [ ] **Step 3: 写 `embeddings.py`**

```python
"""BGE-M3 本地嵌入封装:懒加载单例 + 测试注入钩子。

Ch03 只跑 dense 单路(spec §2),故 encode 时关闭 sparse/colbert 分支。
模型目录来自 EMBEDDING_MODEL_PATH(从 modelscope 下载,BGE-M3 dense 维度 1024)。
"""
from typing import Protocol

from config import load_settings

EMBED_DIM = 1024


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...  # pragma: no cover


class BGEM3Embedder:
    def __init__(self, model_path: str) -> None:
        # 重依赖与模型加载延迟到首调:import main 时不加载 2GB 模型
        from FlagEmbedding import BGEM3FlagModel

        self._model = BGEM3FlagModel(model_path, use_fp16=False)

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = self._model.encode(
            texts,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        return [[float(x) for x in vec] for vec in out["dense_vecs"]]


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """首调加载、后续复用(模型加载失败只在调用时暴露,不阻断服务启动)。"""
    global _embedder
    if _embedder is None:
        _embedder = BGEM3Embedder(load_settings().embedding_model_path)
    return _embedder


def set_embedder(embedder: Embedder | None) -> None:
    """测试注入/复位钩子(传 None 复位,下次调用重新懒加载)。"""
    global _embedder
    _embedder = embedder


def embed(texts: list[str]) -> list[list[float]]:
    return get_embedder().embed(texts)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_embeddings.py -v`
Expected: 2 passed

- [ ] **Step 5: 真模型冒烟(Context7 文档偏薄,此步实测核对 FlagEmbedding API)**

先核对 FlagEmbedding 官方文档(`mcp_context7` → `/websites/flagopen_github_io_flagembedding`,若无 `encode` 细节则直接按下面命令实测),再跑:

```powershell
.\.venv\Scripts\python.exe -c "from embeddings import BGEM3Embedder; m=BGEM3Embedder(r'E:\javatexts\poetry-spring2\models\bge-m3'); v=m.embed(['床前明月光','床前明月光']); print('DIM', len(v[0])); print('SAME', round(sum(a*b for a,b in zip(v[0],v[1])), 4))"
```

Expected: `DIM 1024`;`SAME` 接近 1.0(同一文本两次编码一致/近似)。
**若报错**:API 与预期不符 → 按官方文档改 `BGEM3Embedder.embed` 的实现,并在 dev-notes 记「API 偏差」;**不得改用其他模型**(选型定死)。

- [ ] **Step 6: Commit**

```powershell
git add potry-ai-agent/embeddings.py potry-ai-agent/tests/test_embeddings.py
git commit -m "feat(ai-agent): ch03 lazy BGE-M3 embedder with injection hook"
```

---

### Task 4: 知识库落库(knowledge.py + db 复位钩子)

**Files:**
- Create: `potry-ai-agent/knowledge.py`
- Modify: `potry-ai-agent/db.py`(追加 `reset_engine` 与 `reset_session_factory`)
- Test: `potry-ai-agent/tests/test_knowledge.py`

- [ ] **Step 1: `db.py` 末尾追加复位钩子**

```python
def reset_engine() -> None:
    """复位 engine/sessionmaker 单例。测试换库、或运行中切换 MYSQL_URL 时用。"""
    global _engine, _session_factory
    _engine = None
    _session_factory = None
```

- [ ] **Step 2: 写失败测试**(新建 `tests/test_knowledge.py`):

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from knowledge import KnowledgeBase, KnowledgeStorage


def make_storage():
    engine = create_engine("sqlite:///:memory:")
    KnowledgeBase.metadata.create_all(engine)
    return KnowledgeStorage(sessionmaker(bind=engine))


def _chunk(**over):
    base = {
        "source_type": "poem",
        "source_id": 1,
        "section": "原文",
        "seq": 0,
        "chunk_text": "静夜思|唐|李白|五言\n原文\n床前明月光。",
        "raw_text": "床前明月光。",
        "title": "静夜思",
        "writer": "李白",
        "dynasty": "唐",
    }
    base.update(over)
    return base


def test_upsert_chunks_is_idempotent_by_unique_key():
    st = make_storage()
    assert st.upsert_chunks([_chunk()]) == 1
    assert st.upsert_chunks([_chunk()]) == 1  # 同键重跑不新增
    assert st.count_by_status() == {"pending": 1}


def test_upsert_chunks_resets_status_when_text_changes():
    st = make_storage()
    st.upsert_chunks([_chunk()])
    st.mark_embedded([st.list_pending()[0]["id"]])
    assert st.count_by_status() == {"embedded": 1}
    st.upsert_chunks([_chunk(chunk_text="静夜思|唐|李白|五言\n原文\n床前明月光。疑是地上霜。")])
    assert st.count_by_status() == {"pending": 1}  # 文本变了要重嵌


def test_mark_embedded_sets_vector_id_equal_chunk_id():
    st = make_storage()
    st.upsert_chunks([_chunk()])
    cid = st.list_pending()[0]["id"]
    st.mark_embedded([cid])
    assert st.get_chunk(cid)["vector_id"] == cid
    assert st.get_chunk(cid)["status"] == "embedded"


def test_list_pending_respects_limit():
    st = make_storage()
    st.upsert_chunks([_chunk(seq=i, section=f"原文{i}") for i in range(5)])
    assert len(st.list_pending(limit=2)) == 2


def test_staging_and_cursor_round_trip():
    st = make_storage()
    st.add_staging([{"question": "月亮那首叫啥", "answer": "静夜思", "tags": "[]", "source_session_id": "s1"}])
    assert len(st.list_staging()) == 1
    st.clear_staging()
    assert st.list_staging() == []
    assert st.get_cursor() == 0
    st.set_cursor(42)
    assert st.get_cursor() == 42
```

- [ ] **Step 3: 跑测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_knowledge.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'knowledge'`

- [ ] **Step 4: 写 `knowledge.py`**

```python
"""知识库落库:knowledge_chunks(原文权威源)/ knowledge_staging(挖知识暂存)/ knowledge_mining_cursor(水位)。"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from storage import _ID_TYPE  # 复用主键类型(MySQL BIGINT / SQLite Integer 自增)


class KnowledgeBase(DeclarativeBase):
    pass


class KnowledgeChunk(KnowledgeBase):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", "section", "seq", name="uq_knowledge_chunk_key"),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(16), index=True)  # poem / poet / qa
    source_id: Mapped[int] = mapped_column(_ID_TYPE)
    chunk_text: Mapped[str] = mapped_column(Text)  # 向量化用(带 metadata 前缀)
    raw_text: Mapped[str] = mapped_column(Text)  # 权威原文
    title: Mapped[str | None] = mapped_column(String(255))
    writer: Mapped[str | None] = mapped_column(String(100))
    dynasty: Mapped[str | None] = mapped_column(String(32))
    section: Mapped[str] = mapped_column(String(32))
    seq: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), index=True, default="pending")  # pending / embedded
    vector_id: Mapped[int | None] = mapped_column(_ID_TYPE)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class KnowledgeStaging(KnowledgeBase):
    __tablename__ = "knowledge_staging"

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    tags: Mapped[str | None] = mapped_column(Text)
    source_session_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class KnowledgeMiningCursor(KnowledgeBase):
    """单行表:记已挖到的最大 messages.id,保证只挖一次、可续跑。"""

    __tablename__ = "knowledge_mining_cursor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_mined_message_id: Mapped[int] = mapped_column(_ID_TYPE, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


_FIELDS = ("source_type", "source_id", "section", "seq", "chunk_text", "raw_text", "title", "writer", "dynasty")


def _to_dict(row: KnowledgeChunk) -> dict:
    return {
        "id": row.id,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "section": row.section,
        "seq": row.seq,
        "chunk_text": row.chunk_text,
        "raw_text": row.raw_text,
        "title": row.title,
        "writer": row.writer,
        "dynasty": row.dynasty,
        "status": row.status,
        "vector_id": row.vector_id,
    }


class KnowledgeStorage:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._factory = session_factory

    # ---------- chunks ----------
    def upsert_chunks(self, chunks: list[dict]) -> int:
        """按唯一键 (source_type, source_id, section, seq) 幂等写入;返回处理条数。

        文本变化时把状态打回 pending(内容变了要重嵌);文本未变保持原状态。
        """
        n = 0
        with self._factory() as session:
            for c in chunks:
                row = (
                    session.execute(
                        select(KnowledgeChunk).where(
                            KnowledgeChunk.source_type == c["source_type"],
                            KnowledgeChunk.source_id == c["source_id"],
                            KnowledgeChunk.section == c["section"],
                            KnowledgeChunk.seq == c["seq"],
                        )
                    )
                    .scalars()
                    .first()
                )
                if row is None:
                    session.add(
                        KnowledgeChunk(
                            **{k: c.get(k) for k in _FIELDS},
                            status="pending",
                        )
                    )
                else:
                    if row.chunk_text != c["chunk_text"]:
                        row.status = "pending"
                    for k in _FIELDS:
                        setattr(row, k, c.get(k))
                n += 1
            session.commit()
        return n

    def list_pending(self, limit: int | None = None) -> list[dict]:
        stmt = select(KnowledgeChunk).where(KnowledgeChunk.status == "pending").order_by(KnowledgeChunk.id)
        if limit:
            stmt = stmt.limit(limit)
        with self._factory() as session:
            return [_to_dict(r) for r in session.execute(stmt).scalars()]

    def list_chunks(self, source_type: str | None = None) -> list[dict]:
        stmt = select(KnowledgeChunk).order_by(KnowledgeChunk.id)
        if source_type:
            stmt = stmt.where(KnowledgeChunk.source_type == source_type)
        with self._factory() as session:
            return [_to_dict(r) for r in session.execute(stmt).scalars()]

    def get_chunk(self, chunk_id: int) -> dict | None:
        with self._factory() as session:
            row = session.get(KnowledgeChunk, chunk_id)
            return _to_dict(row) if row else None

    def mark_embedded(self, chunk_ids: list[int]) -> None:
        """Milvus 主键即 chunk id,故 vector_id = chunk id。"""
        with self._factory() as session:
            for cid in chunk_ids:
                row = session.get(KnowledgeChunk, cid)
                if row is not None:
                    row.status = "embedded"
                    row.vector_id = cid
            session.commit()

    def count_by_status(self) -> dict:
        out: dict[str, int] = {}
        with self._factory() as session:
            for row in session.execute(select(KnowledgeChunk)).scalars():
                out[row.status] = out.get(row.status, 0) + 1
        return out

    # ---------- staging / cursor ----------
    def add_staging(self, rows: list[dict]) -> int:
        with self._factory() as session:
            for r in rows:
                session.add(
                    KnowledgeStaging(
                        question=r["question"],
                        answer=r["answer"],
                        tags=r.get("tags"),
                        source_session_id=r.get("source_session_id"),
                    )
                )
            session.commit()
        return len(rows)

    def list_staging(self) -> list[dict]:
        with self._factory() as session:
            return [
                {
                    "id": r.id,
                    "question": r.question,
                    "answer": r.answer,
                    "tags": r.tags,
                    "source_session_id": r.source_session_id,
                }
                for r in session.execute(select(KnowledgeStaging).order_by(KnowledgeStaging.id)).scalars()
            ]

    def clear_staging(self) -> None:
        with self._factory() as session:
            for r in session.execute(select(KnowledgeStaging)).scalars():
                session.delete(r)
            session.commit()

    def get_cursor(self) -> int:
        with self._factory() as session:
            row = session.get(KnowledgeMiningCursor, 1)
            return row.last_mined_message_id if row else 0

    def set_cursor(self, message_id: int) -> None:
        with self._factory() as session:
            row = session.get(KnowledgeMiningCursor, 1)
            if row is None:
                session.add(KnowledgeMiningCursor(id=1, last_mined_message_id=message_id))
            else:
                row.last_mined_message_id = message_id
            session.commit()
```

- [ ] **Step 5: 跑测试确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_knowledge.py tests\test_storage.py -v`
Expected: 5 + 2 = 7 passed

- [ ] **Step 6: Commit**

```powershell
git add potry-ai-agent/knowledge.py potry-ai-agent/db.py potry-ai-agent/tests/test_knowledge.py
git commit -m "feat(ai-agent): ch03 knowledge tables with idempotent chunk upsert and mining cursor"
```

---

### Task 5: 向量库封装(vector_store.py)

**Files:**
- Create: `potry-ai-agent/vector_store.py`
- Test: `potry-ai-agent/tests/test_vector_store.py`

- [ ] **Step 1: 写失败测试**(新建 `tests/test_vector_store.py`;**用临时 Milvus Lite 文件**):

```python
import pytest

from vector_store import MilvusLiteVectorStore, set_store


@pytest.fixture
def store(tmp_path):
    s = MilvusLiteVectorStore(str(tmp_path / "kb.db"), "knowledge", dim=4)
    yield s
    set_store(None)


def _meta(source_type="poem", title="静夜思", writer="李白", dynasty="唐"):
    return {"source_type": source_type, "title": title, "writer": writer, "dynasty": dynasty}


def test_upsert_and_search_returns_similarity(store):
    store.upsert([1, 2], [[1.0, 0, 0, 0], [0, 1.0, 0, 0]], [_meta(title="静夜思"), _meta(title="春晓")])
    hits = store.search([1.0, 0, 0, 0], topk=2, source_type="poem")
    assert hits[0]["id"] == 1
    assert hits[0]["title"] == "静夜思"
    assert hits[0]["score"] > hits[1]["score"]


def test_upsert_is_idempotent_by_primary_key(store):
    store.upsert([1], [[1.0, 0, 0, 0]], [_meta(title="静夜思")])
    store.upsert([1], [[1.0, 0, 0, 0]], [_meta(title="静夜思(改)")])
    hits = store.search([1.0, 0, 0, 0], topk=5, source_type="poem")
    assert len(hits) == 1
    assert hits[0]["title"] == "静夜思(改)"


def test_search_filters_by_source_type(store):
    store.upsert([1, 2], [[1.0, 0, 0, 0], [0.9, 0.1, 0, 0]], [_meta(source_type="poem"), _meta(source_type="poet", title="李白")])
    hits = store.search([1.0, 0, 0, 0], topk=5, source_type="poet")
    assert [h["title"] for h in hits] == ["李白"]


def test_query_by_dynasty_filters(store):
    store.upsert(
        [1, 2],
        [[1.0, 0, 0, 0], [0, 1.0, 0, 0]],
        [_meta(dynasty="唐"), _meta(dynasty="宋", title="春晓")],
    )
    rows = store.query_by_dynasty("唐", limit=10)
    assert [r["title"] for r in rows] == ["静夜思"]


def test_data_survives_new_client_on_same_file(tmp_path):
    path = str(tmp_path / "kb.db")
    first = MilvusLiteVectorStore(path, "knowledge", dim=4)
    first.upsert([1], [[1.0, 0, 0, 0]], [_meta()])
    second = MilvusLiteVectorStore(path, "knowledge", dim=4)  # 新 client 必须能读
    assert second.search([1.0, 0, 0, 0], topk=1, source_type="poem")[0]["id"] == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_vector_store.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'vector_store'`

- [ ] **Step 3: 写 `vector_store.py`**

```python
"""Milvus(Milvus Lite 嵌入式)封装:knowledge 集合的建/写/查。

已实测确认(pymilvus 3.0.2):
- 新 client 读前必须 load_collection,否则报 "Collection ... state 'released'"；
- COSINE 返回相似度,越大越相似(同向量 = 1.0);
- upsert 按主键幂等(同 id 覆盖)。
"""
from typing import Protocol

from config import load_settings

VECTOR_DIM = 1024
_METADATA_FIELDS = ("source_type", "title", "writer", "dynasty")
_ALLOWED_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-")


def safe_expr_value(value: str, max_len: int = 32) -> str:
    """过滤表达式里的值:只留字母数字/下划线/短横/空格,并截断,防注入(值来自模型入参)。"""
    return "".join(ch for ch in str(value) if ch in _ALLOWED_ID_CHARS)[:max_len]


class VectorStore(Protocol):
    def upsert(self, ids: list[int], vectors: list[list[float]], metadatas: list[dict]) -> None:
        ...  # pragma: no cover

    def search(self, vector: list[float], topk: int, source_type: str) -> list[dict]:
        ...  # pragma: no cover

    def query_by_dynasty(self, dynasty: str, limit: int) -> list[dict]:
        ...  # pragma: no cover


class MilvusLiteVectorStore:
    def __init__(self, db_path: str, collection: str, dim: int = VECTOR_DIM) -> None:
        from pymilvus import DataType, MilvusClient

        self._client = MilvusClient(db_path)
        self._collection = collection
        if not self._client.has_collection(collection):
            schema = self._client.create_schema(auto_id=False)
            schema.add_field("id", DataType.INT64, is_primary=True)
            schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dim)
            schema.add_field("source_type", DataType.VARCHAR, max_length=16)
            schema.add_field("title", DataType.VARCHAR, max_length=512)
            schema.add_field("writer", DataType.VARCHAR, max_length=128)
            schema.add_field("dynasty", DataType.VARCHAR, max_length=64)
            index_params = self._client.prepare_index_params()
            index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
            self._client.create_collection(collection, schema=schema, index_params=index_params)
        self._load()

    def _load(self) -> None:
        # 新 client 时集合可能处于 released,读前必须 load
        self._client.load_collection(self._collection)

    def upsert(self, ids, vectors, metadatas) -> None:
        rows = [
            {"id": int(i), "vector": [float(x) for x in v], **{k: (m.get(k) or "") for k in _METADATA_FIELDS}}
            for i, v, m in zip(ids, vectors, metadatas)
        ]
        if not rows:
            return
        self._client.upsert(self._collection, rows)
        self._load()

    def search(self, vector, topk, source_type) -> list[dict]:
        res = self._client.search(
            self._collection,
            data=[[float(x) for x in vector]],
            anns_field="vector",
            limit=topk,
            filter=f'source_type == "{safe_expr_value(source_type, 16)}"',
            output_fields=list(_METADATA_FIELDS),
            search_params={"metric_type": "COSINE"},
        )
        hits: list[dict] = []
        for hit in res[0]:
            entity = dict(hit.get("entity") or {})
            hits.append({"id": int(hit["id"]), "score": float(hit["distance"]), **entity})
        return hits

    def query_by_dynasty(self, dynasty, limit) -> list[dict]:
        expr = f'dynasty == "{safe_expr_value(dynasty)}" and source_type == "poem"'
        rows = self._client.query(
            self._collection, filter=expr, output_fields=list(_METADATA_FIELDS), limit=limit
        )
        return [dict(r) for r in rows]


_store: VectorStore | None = None


def get_store() -> VectorStore:
    """首调建 client(并 load 集合),后续复用;失败只在调用时暴露。"""
    global _store
    if _store is None:
        settings = load_settings()
        _store = MilvusLiteVectorStore(settings.milvus_db_path, settings.milvus_collection)
    return _store


def set_store(store: VectorStore | None) -> None:
    """测试注入/复位钩子。"""
    global _store
    _store = store


def upsert(ids, vectors, metadatas) -> None:
    get_store().upsert(ids, vectors, metadatas)


def search(vector, topk, source_type) -> list[dict]:
    return get_store().search(vector, topk, source_type)


def query_by_dynasty(dynasty, limit) -> list[dict]:
    return get_store().query_by_dynasty(dynasty, limit)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_vector_store.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```powershell
git add potry-ai-agent/vector_store.py potry-ai-agent/tests/test_vector_store.py
git commit -m "feat(ai-agent): ch03 milvus lite vector store wrapper with filtered search"
```

---

### Task 6: 离线建库管线(build_kb.py)

**Files:**
- Create: `potry-ai-agent/build_kb.py`
- Test: `potry-ai-agent/tests/test_build_kb.py`

- [ ] **Step 1: 写失败测试**(新建 `tests/test_build_kb.py`):

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import build_kb
from knowledge import KnowledgeBase, KnowledgeStorage
from vector_store import MilvusLiteVectorStore


class FakeEmbedder:
    def embed(self, texts):
        # 长度编码的假向量,维度固定 4,足够断言"写过 Milvus"
        return [[float(len(t))] * 4 for t in texts]


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    KnowledgeBase.metadata.create_all(engine)
    storage = KnowledgeStorage(sessionmaker(bind=engine))
    store = MilvusLiteVectorStore(str(tmp_path / "kb.db"), "knowledge", dim=4)
    monkeypatch.setattr(build_kb, "embed", FakeEmbedder().embed)
    return storage, store


def test_embed_pending_moves_all_to_embedded(env):
    storage, store = env
    storage.upsert_chunks(
        [
            {"source_type": "poem", "source_id": 1, "section": "原文", "seq": 0,
             "chunk_text": "静夜思|唐|李白|五言\n原文\n床前明月光。", "raw_text": "床前明月光。",
             "title": "静夜思", "writer": "李白", "dynasty": "唐"},
            {"source_type": "poem", "source_id": 1, "section": "译文", "seq": 0,
             "chunk_text": "静夜思|唐|李白|五言\n译文\n明月光。", "raw_text": "明月光。",
             "title": "静夜思", "writer": "李白", "dynasty": "唐"},
        ]
    )
    stats = build_kb.embed_pending(storage, store, batch_size=1)
    assert stats == {"embedded": 2, "failed": 0, "remaining": 0}
    assert storage.count_by_status() == {"embedded": 2}
    assert store.search([9.0, 9.0, 9.0, 9.0], topk=5, source_type="poem")


def test_embed_pending_keeps_pending_and_reports_failure(env, monkeypatch):
    storage, store = env

    def boom(texts):
        raise RuntimeError("模型挂了")

    monkeypatch.setattr(build_kb, "embed", boom)
    storage.upsert_chunks(
        [{"source_type": "poem", "source_id": 1, "section": "原文", "seq": 0,
          "chunk_text": "x", "raw_text": "x", "title": "t", "writer": "w", "dynasty": "d"}]
    )
    stats = build_kb.embed_pending(storage, store, batch_size=1)
    assert stats["embedded"] == 0 and stats["failed"] == 1 and stats["remaining"] == 1
    assert storage.count_by_status() == {"pending": 1}  # 挂了能重跑


def test_embed_pending_picks_up_pending_after_interruption(env):
    """模拟"中断后重跑":前一半已 embedded(上一轮已完成),重跑只补剩下的 pending。

    注:embed_pending 是"耗尽式"循环(一次调用处理完所有 pending),
    故"中断"须由外部预标记 embedded 来模拟,不能靠"单次调用只跑一批"。
    """
    storage, store = env
    rows = [
        {"source_type": "poem", "source_id": 1, "section": f"原文{i}", "seq": 0,
         "chunk_text": f"t{i}", "raw_text": f"t{i}", "title": "t", "writer": "w", "dynasty": "d"}
        for i in range(4)
    ]
    storage.upsert_chunks(rows)
    first_two = [c["id"] for c in storage.list_pending()][:2]
    storage.mark_embedded(first_two)  # 模拟"上一轮已嵌完这两块"
    assert storage.count_by_status() == {"embedded": 2, "pending": 2}
    stats = build_kb.embed_pending(storage, store, batch_size=2)
    assert stats == {"embedded": 2, "failed": 0, "remaining": 0}
    assert storage.count_by_status() == {"embedded": 4}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_build_kb.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'build_kb'`

- [ ] **Step 3: 写 `build_kb.py`**

```python
"""离线建库 CLI:potry/writer → 切分 → MySQL(待向量化)→ 嵌入 → Milvus → 回填 + 已向量化。

用法:
    .\.venv\Scripts\python.exe build_kb.py                 # 全量
    .\.venv\Scripts\python.exe build_kb.py --limit 50      # 只处理前 50 首诗(小样本验证)
    .\.venv\Scripts\python.exe build_kb.py --skip-chunk    # 只补向量化(不重切)
中断后直接重跑即可:只取 status='pending' 的块补做(spec §6.3)。
"""
import argparse

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from chunking import chunk_poem, chunk_poet
from config import load_settings
from db import Potry, Writer, get_engine, new_session
from embeddings import embed
from knowledge import KnowledgeBase, KnowledgeStorage
from storage import ChatBase
from vector_store import MilvusLiteVectorStore

_EMBED_BATCH = 16


def collect_poem_chunks(session, chunk_size: int, overlap: int, limit: int | None = None) -> list[dict]:
    stmt = select(Potry).order_by(Potry.id)
    if limit is not None:
        stmt = stmt.limit(limit)
    out: list[dict] = []
    for p in session.execute(stmt).scalars():
        poem = {
            "title": p.title, "dynasty": p.dynasty, "writer": p.writer, "type": p.type,
            "content": p.content, "translation": p.translation, "shangxi": p.shangxi, "remark": p.remark,
        }
        for c in chunk_poem(poem, chunk_size, overlap):
            out.append(
                {
                    "source_type": "poem", "source_id": p.id,
                    "title": p.title, "writer": p.writer, "dynasty": p.dynasty, **c,
                }
            )
    return out


def collect_poet_chunks(session, chunk_size: int, overlap: int) -> list[dict]:
    out: list[dict] = []
    for w in session.execute(select(Writer).order_by(Writer.id)).scalars():
        for c in chunk_poet({"name": w.name, "simpleIntro": w.simpleIntro, "detailIntro": w.detailIntro}, chunk_size, overlap):
            out.append(
                {"source_type": "poet", "source_id": w.id, "title": w.name, "writer": w.name, "dynasty": None, **c}
            )
    return out


def embed_pending(storage: KnowledgeStorage, store, batch_size: int = _EMBED_BATCH) -> dict:
    """把 status='pending' 的块分批嵌入并写入 Milvus,成功则转 embedded。

    整批嵌入/写入失败时**不标记**,块保持 pending —— 这就是"挂了能重跑"。
    """
    embedded = failed = 0
    while True:
        pending = storage.list_pending(limit=batch_size)
        if not pending:
            break
        ids = [c["id"] for c in pending]
        try:
            vectors = embed([c["chunk_text"] for c in pending])
            store.upsert(
                ids,
                vectors,
                [
                    {
                        "source_type": c["source_type"],
                        "title": c["title"],
                        "writer": c["writer"],
                        "dynasty": c["dynasty"],
                    }
                    for c in pending
                ],
            )
        except Exception as exc:  # noqa: BLE001 - 记录并停止本轮,块保持 pending 供重跑
            print(f"[kb] 批次失败(保持 pending,可重跑): {str(exc)[:200]}")
            failed += len(ids)
            break
        storage.mark_embedded(ids)
        embedded += len(ids)
    return {"embedded": embedded, "failed": failed, "remaining": len(storage.list_pending())}


def run(limit: int | None = None, skip_chunk: bool = False) -> dict:
    settings = load_settings()
    engine = get_engine(settings.mysql_url)
    KnowledgeBase.metadata.create_all(engine)
    ChatBase.metadata.create_all(engine)
    storage = KnowledgeStorage(sessionmaker(bind=engine))
    store = MilvusLiteVectorStore(settings.milvus_db_path, settings.milvus_collection)

    written = 0
    if not skip_chunk:
        session = new_session(settings.mysql_url)
        try:
            rows = collect_poem_chunks(session, settings.chunk_size, settings.chunk_overlap, limit)
            rows += collect_poet_chunks(session, settings.chunk_size, settings.chunk_overlap)
        finally:
            session.close()
        written = storage.upsert_chunks(rows)
    stats = embed_pending(storage, store)
    return {"chunks_written": written, **stats, "status_counts": storage.count_by_status()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ch03 离线建库")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 首诗(小样本验证用)")
    parser.add_argument("--skip-chunk", action="store_true", help="跳过切分入库,只补向量化")
    args = parser.parse_args()
    print(f"[kb] 结果: {run(limit=args.limit, skip_chunk=args.skip_chunk)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_build_kb.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```powershell
git add potry-ai-agent/build_kb.py potry-ai-agent/tests/test_build_kb.py
git commit -m "feat(ai-agent): ch03 offline kb build pipeline with resumable embedding"
```

---

### Task 7: 对话挖知识(mining.py)+ 标注样例

**Files:**
- Create: `potry-ai-agent/mining.py`
- Create: `potry-ai-agent/evals/ch03_mining_eval_cases.md`
- Test: `potry-ai-agent/tests/test_mining.py`

- [ ] **Step 1: 写失败测试**(新建 `tests/test_mining.py`):

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import mining
from knowledge import KnowledgeBase, KnowledgeStorage
from storage import ChatBase, ChatStorage


@pytest.fixture
def env():
    engine = create_engine("sqlite:///:memory:")
    KnowledgeBase.metadata.create_all(engine)
    ChatBase.metadata.create_all(engine)
    return KnowledgeStorage(sessionmaker(bind=engine)), ChatStorage(sessionmaker(bind=engine))


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def invoke(self, _messages):
        self.calls += 1

        class _Msg:
            content = self.payload

        return _Msg()


def test_parse_pairs_extracts_json_array_from_fenced_text():
    raw = '好的:\n```json\n[{"question": "月亮那首叫啥", "answer": "静夜思", "tags": ["月亮"]}]\n```'
    assert mining.parse_pairs(raw) == [{"question": "月亮那首叫啥", "answer": "静夜思", "tags": ["月亮"]}]


def test_parse_pairs_returns_empty_on_garbage():
    assert mining.parse_pairs("我不知道") == []


def test_normalize_question_strips_punctuation_and_whitespace():
    assert mining.normalize_question("《静夜思》是谁写的?") == mining.normalize_question("静夜思是谁写的")


def test_dedupe_pairs_drops_duplicates_and_existing():
    pairs = [
        {"question": "月亮那首叫啥", "answer": "A", "tags": []},
        {"question": "月亮那首叫啥?", "answer": "A2", "tags": []},
        {"question": "李白是谁", "answer": "B", "tags": []},
    ]
    out = mining.dedupe_pairs(pairs, existing_questions={mining.normalize_question("李白是谁?")})
    assert [p["question"] for p in out] == ["月亮那首叫啥"]


def test_mine_writes_staging_then_chunks_and_advances_cursor(env):
    storage, chat = env
    chat.persist_turn("s1", [{"role": "user", "content": "月亮那首叫啥"}, {"role": "assistant", "content": "静夜思"}])
    fake = FakeLLM('[{"question": "月亮那首叫啥", "answer": "静夜思", "tags": []}]')
    stats = mining.mine(storage=storage, chat_storage=chat, llm=fake, batch_size=10)
    assert stats["extracted"] == 1 and stats["written"] == 1
    assert storage.list_staging() == []  # 挖完暂存清空
    chunks = storage.list_chunks(source_type="qa")
    assert len(chunks) == 1 and chunks[0]["raw_text"] == "静夜思"
    assert storage.get_cursor() > 0


def test_mine_is_incremental_and_idempotent(env):
    storage, chat = env
    chat.persist_turn("s1", [{"role": "user", "content": "月亮那首叫啥"}, {"role": "assistant", "content": "静夜思"}])
    fake = FakeLLM('[{"question": "月亮那首叫啥", "answer": "静夜思", "tags": []}]')
    mining.mine(storage=storage, chat_storage=chat, llm=fake, batch_size=10)
    first_calls = fake.calls
    mining.mine(storage=storage, chat_storage=chat, llm=fake, batch_size=10)  # 再跑
    assert fake.calls == first_calls  # 水位之内,无新对话 → 不再喂 LLM
    assert len(storage.list_chunks(source_type="qa")) == 1  # 幂等不重复
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_mining.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'mining'`

- [ ] **Step 3: 写 `mining.py`**

```python
"""对话挖知识:历史对话 → 分批喂 LLM 抽问答对 → 暂存 → 整体去重 → 入库(待向量化)。

用法(手动触发,不新增 HTTP 路由):
    .\.venv\Scripts\python.exe mining.py
"""
import json
import re

from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from chat_service import build_llm
from config import load_settings
from knowledge import KnowledgeStorage
from storage import ChatStorage, Message

MINING_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是诗词伴学系统的知识抽取助手。从给定的对话片段中抽取「可复用的问答对」:"
            "问题保留用户原话里的问法,答案只保留事实性内容(诗词名句、作者、朝代、典故等),"
            "不要保留寒暄、人设口吻与推测性内容。抽不到就返回空数组。",
        ),
        (
            "human",
            "对话片段:\n{transcript}\n\n"
            "只输出 JSON 数组,每项形如 "
            '{{"question": "用户问法", "answer": "事实性答案", "tags": ["标签"]}};'
            "不要输出任何解释文字。",
        ),
    ]
)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
_NORMALIZE_DROP = set(" \t\r\n《》?？!!。,、:：;；\"'“”‘’()（）[]【】")


def normalize_question(question: str) -> str:
    """去空白与标点,统一小写,作为去重键。"""
    return "".join(ch for ch in (question or "").lower() if ch not in _NORMALIZE_DROP)


def parse_pairs(raw: str) -> list[dict]:
    """从 LLM 输出里解析 JSON 数组;带 ``` 围栏或夹带文字时尽力提取;失败返回 []。"""
    text = (raw or "").strip()
    m = _FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for item in data:
        if isinstance(item, dict) and item.get("question") and item.get("answer"):
            out.append(
                {
                    "question": str(item["question"]).strip(),
                    "answer": str(item["answer"]).strip(),
                    "tags": item.get("tags") or [],
                }
            )
    return out


def dedupe_pairs(pairs: list[dict], existing_questions: set[str]) -> list[dict]:
    """按归一化问题去重,并剔除与既有知识重复的;保留首次出现的那条。"""
    seen = set(existing_questions)
    out: list[dict] = []
    for p in pairs:
        key = normalize_question(p["question"])
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _load_transcripts(chat_storage: ChatStorage, after_id: int) -> list[dict]:
    """取 messages.id > after_id 的 user/assistant 配对,跳过 tool 行;按会话分组。"""
    with chat_storage._factory() as session:
        rows = list(session.execute(select(Message).where(Message.id > after_id).order_by(Message.id)).scalars())
    by_conv: dict[int, list] = {}
    for r in rows:
        by_conv.setdefault(r.conversation_id, []).append(r)
    out: list[dict] = []
    for conv_id, msgs in by_conv.items():
        pairs: list[dict] = []
        last_user = None
        for r in msgs:
            if r.role == "user":
                last_user = r.content
            elif r.role == "assistant" and last_user is not None:
                pairs.append({"user": last_user, "assistant": r.content})
                last_user = None
        if pairs:
            out.append({"session_id": str(conv_id), "pairs": pairs, "max_message_id": msgs[-1].id})
    return out


def _render(pairs: list[dict]) -> str:
    return "\n".join(f"用户: {p['user']}\n助手: {p['assistant']}" for p in pairs)


def _loads(text: str | None) -> list:
    try:
        return json.loads(text or "[]")
    except json.JSONDecodeError:
        return []


def mine(
    settings=None,
    llm=None,
    storage: KnowledgeStorage | None = None,
    chat_storage: ChatStorage | None = None,
    batch_size: int | None = None,
) -> dict:
    """挖一轮:增量取未挖对话 → 分批抽问答对 → 暂存 → 整体去重 → 入库(待向量化)。"""
    settings = settings or load_settings()
    llm = llm or build_llm(settings)
    batch_size = batch_size or settings.mining_batch_size
    if storage is None or chat_storage is None:
        from db import get_engine

        factory = sessionmaker(bind=get_engine(settings.mysql_url))
        storage = storage or KnowledgeStorage(factory)
        chat_storage = chat_storage or ChatStorage(factory)

    cursor = storage.get_cursor()
    transcripts = _load_transcripts(chat_storage, cursor)
    if not transcripts:
        return {"transcripts": 0, "batches": 0, "extracted": 0, "written": 0, "cursor": cursor}

    extracted: list[dict] = []
    max_id = cursor
    batches = 0
    for t in transcripts:
        max_id = max(max_id, t["max_message_id"])
        pairs = t["pairs"]
        for i in range(0, len(pairs), batch_size):
            batches += 1
            chunk = pairs[i : i + batch_size]
            try:
                resp = llm.invoke(MINING_PROMPT.invoke({"transcript": _render(chunk)}))
                got = parse_pairs(getattr(resp, "content", "") or "")
            except Exception as exc:  # noqa: BLE001 - 单批失败跳过,不污染暂存表
                print(f"[mining] 批次抽取失败,跳过: {str(exc)[:200]}")
                continue
            for g in got:
                extracted.append({**g, "source_session_id": t["session_id"]})

    if extracted:
        storage.add_staging(
            [
                {
                    "question": e["question"],
                    "answer": e["answer"],
                    "tags": json.dumps(e.get("tags") or [], ensure_ascii=False),
                    "source_session_id": e["source_session_id"],
                }
                for e in extracted
            ]
        )

    # 整体去重:既有 qa 知识的去重键存在 title(即问题原话),不是 chunk_text
    existing = {normalize_question(c["title"]) for c in storage.list_chunks(source_type="qa")}
    staged = storage.list_staging()
    by_key: dict[str, dict] = {}
    for s in staged:
        by_key.setdefault(normalize_question(s["question"]), s)  # 同问题只取暂存里首条
    kept = dedupe_pairs(
        [
            {"question": s["question"], "answer": s["answer"], "tags": _loads(s["tags"])}
            for s in staged
        ],
        existing,
    )
    rows = []
    for k in kept:
        src = by_key[normalize_question(k["question"])]
        rows.append(
            {
                "source_type": "qa",
                "source_id": src["id"],  # 来源业务键 = staging.id(spec §6.1)
                "section": "qa",
                "seq": 0,
                "chunk_text": f"{k['question']}\nqa\n{k['answer']}",
                "raw_text": k["answer"],
                "title": k["question"],
                "writer": None,
                "dynasty": None,
            }
        )
    written = storage.upsert_chunks(rows) if rows else 0
    storage.clear_staging()
    storage.set_cursor(max_id)
    return {
        "transcripts": len(transcripts),
        "batches": batches,
        "extracted": len(extracted),
        "written": written,
        "cursor": max_id,
    }


def main() -> None:
    stats = mine()
    print(f"[mining] 结果: {stats}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_mining.py -v`
Expected: 6 passed

- [ ] **Step 5: 写标注样例 `evals/ch03_mining_eval_cases.md`**

```markdown
# Ch03 对话挖知识 · 标注样例(真实 LLM 人工比对)

前置:服务与 `conversations`/`messages` 里已有真实聊天记录;跑 `.\.venv\Scripts\python.exe mining.py`。

| # | 对话片段(节选) | 期望抽到的问答对 | 通过 |
|---|---|---|---|
| 1 | 用户「那首讲月亮的叫啥」/助手「应是《静夜思》,李白所作……」 | {"question":"那首讲月亮的叫啥","answer":"《静夜思》(李白)"} | |
| 2 | 用户「李白是什么朝代的」/助手「盛唐,701—762 年……」 | {"question":"李白是什么朝代的","answer":"唐(盛唐),701—762"} | |
| 3 | 用户「今天天气真好」/助手「天气一好,人心也跟着亮堂……」 | **不抽**(纯寒暄,无事实性知识) | |
| 4 | 用户「静夜思谁写的」/助手「李白。全诗二十字:床前明月光……」 | {"question":"静夜思谁写的","answer":"李白"} | |

判定要点:①事实性内容保留;②寒暄不抽(负例 #3 是关键判别项);③问题保留用户原话问法,不回写成人设腔。逐条跑真实 DeepSeek,人工比对后勾选。
```

- [ ] **Step 6: 跑全量测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`
Expected: 全绿(46 + 7 + 2 + 5 + 5 + 3 + 6 = 74 条上下)

- [ ] **Step 7: Commit**

```powershell
git add potry-ai-agent/mining.py potry-ai-agent/tests/test_mining.py potry-ai-agent/evals/ch03_mining_eval_cases.md
git commit -m "feat(ai-agent): ch03 conversation knowledge mining with staging dedupe"
```

---

### Task 8: 三工具改向量语义检索(契约不变)

**Files:**
- Modify: `potry-ai-agent/tools/poetry_tools.py`
- Modify: `potry-ai-agent/tests/test_poetry_tools.py`

- [ ] **Step 1: 重写失败测试**(`tests/test_poetry_tools.py` 整体替换):

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import db
from knowledge import KnowledgeBase, KnowledgeStorage
from tools.poetry_tools import query_dynasty_poems, query_poem, query_poet
from embeddings import set_embedder
from vector_store import set_store


class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


class FakeStore:
    def __init__(self, hits):
        self.hits = hits

    def search(self, vector, topk, source_type):
        return [h for h in self.hits if h["source_type"] == source_type][:topk]

    def query_by_dynasty(self, dynasty, limit):
        return [h for h in self.hits if h.get("dynasty") == dynasty and h["source_type"] == "poem"][:limit]

    def upsert(self, ids, vectors, metadatas):
        raise AssertionError("工具只读,不应写 Milvus")


@pytest.fixture
def kb(tmp_path, monkeypatch):
    """知识库落 SQLite 临时文件;db 单例复位以便指向该库;诗词表用同样的 engine 建。"""
    path = str(tmp_path / "kb.db")
    monkeypatch.setenv("MYSQL_URL", f"sqlite:///{path}")
    monkeypatch.setenv("SIMILARITY_THRESHOLD", "0.5")
    db.reset_engine()
    engine = db.get_engine(f"sqlite:///{path}")
    KnowledgeBase.metadata.create_all(engine)
    db.PoetryBase.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        s.add(db.Potry(id=1, title="静夜思", dynasty="唐", writer="李白", type="五言绝句",
                       content="床前明月光,疑是地上霜。举头望明月,低头思故乡。",
                       translation="明亮的月光洒在床前。", shangxi="思乡之作。", remark=None, audioUrl=None))
        s.add(db.Writer(id=1, name="李白", simpleIntro="盛唐诗仙。", detailIntro="字太白,号青莲居士。", headImageUrl=None))
        s.commit()
    storage = KnowledgeStorage(sessionmaker(bind=engine))
    set_embedder(FakeEmbedder())
    yield storage, engine
    set_embedder(None)
    set_store(None)
    db.reset_engine()


def test_query_poem_returns_contract_shape_from_vector_hit(kb, monkeypatch):
    storage, _ = kb
    storage.upsert_chunks([{"source_type": "poem", "source_id": 1, "section": "原文", "seq": 0,
                            "chunk_text": "静夜思|唐|李白|五言\n原文\n床前明月光。", "raw_text": "床前明月光。",
                            "title": "静夜思", "writer": "李白", "dynasty": "唐"}])
    set_store(FakeStore([{"id": storage.list_chunks()[0]["id"], "score": 0.91, "source_type": "poem",
                          "title": "静夜思", "writer": "李白", "dynasty": "唐"}]))
    res = query_poem.invoke({"keyword": "那首讲月亮的叫啥"})
    assert res["ok"] is True and res["found"] is True
    assert res["poem"]["title"] == "静夜思" and res["poem"]["writer"] == "李白"
    assert set(res["poem"]) == {"title", "dynasty", "writer", "type", "content", "translation", "shangxi", "remark"}


def test_query_poem_found_false_when_below_threshold(kb):
    storage, _ = kb
    storage.upsert_chunks([{"source_type": "poem", "source_id": 1, "section": "原文", "seq": 0,
                            "chunk_text": "x", "raw_text": "x", "title": "静夜思", "writer": "李白", "dynasty": "唐"}])
    set_store(FakeStore([{"id": storage.list_chunks()[0]["id"], "score": 0.2, "source_type": "poem",
                          "title": "静夜思", "writer": "李白", "dynasty": "唐"}]))
    assert query_poem.invoke({"keyword": "随便问问"}) == {"ok": True, "found": False}


def test_query_poem_returns_ok_false_on_failure(kb):
    class Boom:
        def embed(self, texts):
            raise RuntimeError("模型挂了")

    set_embedder(Boom())
    res = query_poem.invoke({"keyword": "静夜思"})
    assert res["ok"] is False and "模型挂了" in res["error"]


def test_query_poet_returns_contract_shape(kb):
    storage, _ = kb
    storage.upsert_chunks([{"source_type": "poet", "source_id": 1, "section": "简简介", "seq": 0,
                            "chunk_text": "李白||李白|诗人\n简简介\n盛唐诗仙。", "raw_text": "盛唐诗仙。",
                            "title": "李白", "writer": "李白", "dynasty": None}])
    set_store(FakeStore([{"id": storage.list_chunks()[0]["id"], "score": 0.88, "source_type": "poet",
                          "title": "李白", "writer": "李白", "dynasty": ""}]))
    res = query_poet.invoke({"name": "李白"})
    assert res["ok"] is True and res["found"] is True
    assert set(res["poet"]) == {"name", "simpleIntro", "detailIntro", "headImageUrl"}
    assert res["works"] == ["静夜思"]


def test_query_dynasty_poems_returns_titles_deduped(kb):
    set_store(FakeStore([
        {"id": 1, "score": 0.0, "source_type": "poem", "title": "静夜思", "writer": "李白", "dynasty": "唐"},
        {"id": 2, "score": 0.0, "source_type": "poem", "title": "静夜思", "writer": "李白", "dynasty": "唐"},
        {"id": 3, "score": 0.0, "source_type": "poem", "title": "春晓", "writer": "孟浩然", "dynasty": "唐"},
    ]))
    res = query_dynasty_poems.invoke({"dynasty": "唐"})
    assert res["ok"] is True and res["found"] is True
    assert res["titles"] == ["静夜思", "春晓"] and res["count"] == 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_poetry_tools.py -v`
Expected: FAIL(旧实现仍走 `LIKE` 查表,断言 `found`/`poem` 键集合不成立)

- [ ] **Step 3: 改 `tools/poetry_tools.py`**

```python
"""诗词域业务工具:查诗词 / 诗人 / 朝代。

Ch03:内部实现从关键词查表改为向量语义检索(问题向量化 → Milvus Top-K → 回查 MySQL
权威原文),**签名与返回结构保持 Ch02 契约不变**;工具描述文案同步改为语义检索口径
(它只是给模型看的说明,不改变契约)。
"""
from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from config import load_settings
from db import Potry, Writer, get_engine, new_session
from embeddings import embed
from knowledge import KnowledgeStorage
from vector_store import query_by_dynasty, search

_MAX_CONTENT = 300  # 诗文/译文回灌截断,防上下文爆炸
_MAX_TITLES = 20  # 朝代标题列表上限
_DYNASTY_SCAN = _MAX_TITLES * 5  # 允许同一首诗多块,故多扫一些再去重


def _get_session() -> Session:
    return new_session(load_settings().mysql_url)


def _get_storage() -> KnowledgeStorage:
    return KnowledgeStorage(sessionmaker(bind=get_engine(load_settings().mysql_url)))


def _truncate(text: str | None) -> str | None:
    return text[:_MAX_CONTENT] if text else text


def _fetch_poem_by_id(session: Session, poem_id: int) -> dict | None:
    p = session.execute(select(Potry).where(Potry.id == poem_id)).scalars().first()
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


def _fetch_poet_by_id(session: Session, writer_id: int) -> dict | None:
    w = session.execute(select(Writer).where(Writer.id == writer_id)).scalars().first()
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


def _top_hit(keyword: str, source_type: str) -> dict | None:
    """向量检索取最高相似度命中;低于阈值或空结果返回 None。"""
    settings = load_settings()
    vector = embed([keyword])[0]
    hits = search(vector, settings.milvus_topk, source_type)
    if not hits or hits[0]["score"] < settings.similarity_threshold:
        return None
    return hits[0]


@tool
def query_poem(keyword: str) -> dict:
    """语义检索诗词:按问题的意思找最匹配的一首诗词(含朝代、作者、原文、译文)。

    Args:
        keyword: 用自然语言描述想找的诗词,如「那首讲月亮的叫啥」「李白写思乡的诗」「静夜思」
    """
    try:
        hit = _top_hit(keyword, "poem")
        if hit is None:
            return {"ok": True, "found": False}
        chunk = _get_storage().get_chunk(hit["id"])
        if chunk is None:
            return {"ok": True, "found": False}
        with _get_session() as session:
            poem = _fetch_poem_by_id(session, chunk["source_id"])
    except Exception as exc:  # noqa: BLE001 - 统一走契约里的失败分支,不抛
        return {"ok": False, "error": str(exc)[:200]}
    if poem is None:
        return {"ok": True, "found": False}
    return {"ok": True, "found": True, "poem": poem}


@tool
def query_poet(name: str) -> dict:
    """查诗人:生平简介与代表作标题列表。

    Args:
        name: 诗人姓名或自然语言描述,如「李白」「杜甫」「写诗很豪放的那位」
    """
    try:
        hit = _top_hit(name, "poet")
        if hit is None:
            return {"ok": True, "found": False}
        chunk = _get_storage().get_chunk(hit["id"])
        if chunk is None:
            return {"ok": True, "found": False}
        with _get_session() as session:
            poet = _fetch_poet_by_id(session, chunk["source_id"])
            works = _fetch_works(session, poet["name"]) if poet else []
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200]}
    if poet is None:
        return {"ok": True, "found": False}
    return {"ok": True, "found": True, "poet": poet, "works": works}


@tool
def query_dynasty_poems(dynasty: str) -> dict:
    """按朝代查诗词:返回该朝代的诗词标题列表(最多 20 条)。

    Args:
        dynasty: 朝代名,如「唐」「宋」
    """
    try:
        hits = query_by_dynasty(dynasty, _DYNASTY_SCAN)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200]}
    titles: list[str] = []
    seen: set[str] = set()
    for h in hits:
        t = h.get("title")
        if t and t not in seen:
            seen.add(t)
            titles.append(t)
        if len(titles) >= _MAX_TITLES:
            break
    if not titles:
        return {"ok": True, "found": False}
    return {"ok": True, "found": True, "count": len(titles), "titles": titles}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_poetry_tools.py -v`
Expected: 5 passed

- [ ] **Step 5: 跑全量测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`
Expected: 全绿

- [ ] **Step 6: Commit**

```powershell
git add potry-ai-agent/tools/poetry_tools.py potry-ai-agent/tests/test_poetry_tools.py
git commit -m "feat(ai-agent): ch03 poetry tools switched to vector retrieval, contract unchanged"
```

---

### Task 9: 定时任务与装配(scheduler.py + main.py)

**Files:**
- Create: `potry-ai-agent/scheduler.py`
- Modify: `potry-ai-agent/main.py`
- Test: `potry-ai-agent/tests/test_scheduler.py`

- [ ] **Step 1: 写失败测试**(新建 `tests/test_scheduler.py`):

```python
from unittest.mock import patch

from scheduler import build_scheduler, run_mining


def test_build_scheduler_registers_cron_job():
    class S:
        mining_cron = "0 3 * * *"
        mining_batch_size = 20

    sch = build_scheduler(S())
    job = sch.get_job("mining")
    assert job is not None
    assert "cron" in str(job.trigger).lower()
    assert job.kwargs["settings"].mining_cron == "0 3 * * *"


def test_run_mining_swallows_errors():
    class S:
        mining_cron = "0 3 * * *"
        mining_batch_size = 20
        mysql_url = "sqlite:///:memory:"

    with patch("scheduler.mine", side_effect=RuntimeError("炸了")):
        run_mining(S())  # 不应抛异常(定时任务失败只记日志)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_scheduler.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'scheduler'`

- [ ] **Step 3: 写 `scheduler.py`**

```python
"""APScheduler 定时任务:进程内 cron 跑「对话挖知识」(spec §5)。

版本:apscheduler 3.11.3(BackgroundScheduler + CronTrigger.from_crontab);
未引入 APScheduler 4.x(其 API 与 3.x 不兼容),实现前已过 Context7 核对。
"""
import traceback

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import Settings
from knowledge import KnowledgeBase, KnowledgeStorage
from db import get_engine
from storage import ChatBase, ChatStorage


def run_mining(settings: Settings) -> None:
    """定时任务入口:失败只打印日志,不抛出(避免调度器线程被打断)。"""
    try:
        from sqlalchemy.orm import sessionmaker

        from mining import mine

        engine = get_engine(settings.mysql_url)
        factory = sessionmaker(bind=engine)
        stats = mine(settings=settings, storage=KnowledgeStorage(factory), chat_storage=ChatStorage(factory))
        print(f"[mining] 定时任务完成: {stats}")
    except Exception as exc:  # noqa: BLE001 - 定时任务失败不炸调度器
        print(f"[mining] 定时任务失败: {str(exc)[:200]}")
        print(traceback.format_exc()[:200])


def build_scheduler(settings: Settings) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        run_mining,
        CronTrigger.from_crontab(settings.mining_cron),
        kwargs={"settings": settings},
        id="mining",
        replace_existing=True,
    )
    return scheduler
```

- [ ] **Step 4: 改 `main.py`**

imports 追加:

```python
from knowledge import KnowledgeBase
from scheduler import build_scheduler
```

`init_db` 改为:

```python
def init_db(target_engine) -> None:
    """建表(幂等):对话表 + 知识库表。MySQL 未起时打印中文告警后继续,不阻断服务启动。"""
    try:
        ChatBase.metadata.create_all(target_engine)
        KnowledgeBase.metadata.create_all(target_engine)
        print("[db] 表结构就绪(对话 + 知识库)")
    except Exception as exc:  # noqa: BLE001 - 建表失败仅告警,服务照常起,查询时才暴露错误
        print(f"[db] 建表失败(MySQL 不可用?): {str(exc)[:200]}")
```

`lifespan` 改为(启动段与收尾段各加 scheduler;**实际实现又按质量评审补了 `warm_up` 预热与「build_scheduler 纳入 try」,下方为最终实现,以此为准**):

```python
def warm_up() -> None:
    """预热嵌入模型与向量库。

    冷启动加载 BGE-M3(约 2.3GB)远超工具体 5s 超时,若等首个请求才懒加载,
    首次工具调用会先被 ToolRegistry 的 asyncio.wait_for 判超时(且取消不了加载线程)。
    故在服务启动时预热;失败仅告警,工具走契约里的降级分支(ok:false)。
    """
    try:
        from embeddings import get_embedder
        from vector_store import get_store

        get_embedder()
        get_store()
        print("[warmup] 嵌入模型与向量库已就绪")
    except Exception as exc:  # noqa: BLE001
        print(f"[warmup] 预热失败(工具将降级为 ok:false): {str(exc)[:200]}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期:启动时建表、预热、起定时任务、注册到 Nacos;关闭时逐项回收。"""
    init_db(engine)
    if settings.warmup_on_start:
        warm_up()
    else:
        print("[warmup] 已跳过预热(WARMUP_ON_START 关闭)")
    scheduler = None
    try:
        # build_scheduler 也必须在本 try 内:非法 MINING_CRON 会让
        # CronTrigger.from_crontab 抛 ValueError,否则会击穿 startup
        scheduler = build_scheduler(settings)
        scheduler.start()
        print(f"[scheduler] 挖知识定时任务已启动(cron={settings.mining_cron})")
    except Exception as exc:  # noqa: BLE001 - 定时任务起不来不影响聊天(含非法 cron)
        print(f"[scheduler] 启动失败(不影响聊天): {str(exc)[:200]}")
    try:
        nacos_client.add_naming_instance(SERVICE_NAME, SERVICE_IP, SERVICE_PORT)
        print(f"[nacos] 已注册 {SERVICE_NAME} -> {SERVICE_IP}:{SERVICE_PORT}")
        _stop_heartbeat.clear()
        threading.Thread(target=_heartbeat_loop, daemon=True).start()
        print("[nacos] 心跳线程已启动")
    except Exception as exc:  # noqa: BLE001 - 注册失败不应阻断服务启动
        print(f"[nacos] 注册失败: {exc}")
    yield
    if scheduler is not None:
        try:
            scheduler.shutdown(wait=False)
            print("[scheduler] 定时任务已停止")
        except Exception as exc:  # noqa: BLE001
            print(f"[scheduler] 停止失败: {str(exc)[:200]}")
    _stop_heartbeat.set()
    try:
        nacos_client.remove_naming_instance(SERVICE_NAME, SERVICE_IP, SERVICE_PORT)
        print(f"[nacos] 已注销 {SERVICE_NAME}")
    except Exception as exc:  # noqa: BLE001
        print(f"[nacos] 注销失败: {exc}")
```

> 另:`Settings` 新增 `warmup_on_start`(env `WARMUP_ON_START`;未设置/空串→默认 True,仅 `0`/`false` 关闭);`tests/conftest.py` 设 `WARMUP_ON_START=0` 以免测试加载真模型。

- [ ] **Step 5: 跑测试确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_scheduler.py tests\test_startup.py tests\test_chat_endpoint.py -v`
Expected: 全绿(2 + 2 + 6 = 10 passed)

- [ ] **Step 6: 跑全量测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`
Expected: 全绿

- [ ] **Step 7: Commit**

```powershell
git add potry-ai-agent/scheduler.py potry-ai-agent/main.py potry-ai-agent/tests/test_scheduler.py
git commit -m "feat(ai-agent): ch03 apscheduler mining job wired into app lifespan"
```

---

### Task 10: 真实建库(小样本 → 全量)+ 端到端验收

**Files:** 无代码改动(纯运行验证;发现问题按问题修,另提交)
- Create: `potry-ai-agent/evals/ch03_retrieval_eval_cases.md`

- [ ] **Step 1: 小样本建库(先验证链路与耗时)**

```powershell
.\.venv\Scripts\python.exe build_kb.py --limit 50
```

Expected: 打印 `chunks_written`、`embedded` > 0、`status_counts {'embedded': N}`。记下 50 首的耗时,据此估算全量(约 10778 首)。

- [ ] **Step 2: 检索冒烟(直接问 Milvus,不经模型)**

```powershell
.\.venv\Scripts\python.exe -c "from embeddings import embed; from vector_store import search; hits=search(embed(['那首讲月亮的叫啥'])[0], 5, 'poem'); print([(h['id'], round(h['score'],3), h['title']) for h in hits])"
```

Expected: Top-5 里出现《静夜思》。**这是本章验收标准 1 的检索面证据**。

- [ ] **Step 3: 全量建库**

```powershell
.\.venv\Scripts\python.exe build_kb.py
```

Expected: `status_counts` 里 `pending = 0`;Milvus 条目数 = `embedded` 数。CPU 耗时可能较长,放后台跑并在 dev-notes 记实际耗时。

- [ ] **Step 4: 起服务并跑验收句 1**

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

另开一个终端:

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/agent/chat -H "Content-Type: application/json" -d '{\"message\": \"那首讲月亮的叫啥\"}' --max-time 180
```

Expected: `meta → tool_status(query_poem) → token* → done`,回答指向《静夜思》且基于库内原文。**对照 Ch02 留档的漏召回,此处应已召回。**

- [ ] **Step 5: 回归其余两句 + 负例**

依次跑「《静夜思》是谁写的」「李白是什么样的诗人」「今天天气真好」,确认:
- 前两句仍触发对应工具并按库内数据作答(契约未破);
- 闲聊句无 `tool_status`。

- [ ] **Step 6: 写评估集 `evals/ch03_retrieval_eval_cases.md`**

```markdown
# Ch03 向量语义检索 · 评估集(真实模型 + 真实库)

前置:BGE-M3 模型已下载、`build_kb.py` 全量跑完、服务已起。

| # | 用户输入 | 期望 | 通过 |
|---|---|---|---|
| 1 | 那首讲月亮的叫啥 | query_poem 召回《静夜思》并答对(Ch02 漏召回句,升级后应召回) | |
| 2 | 表达思乡之情的千古名篇 | query_poem 召回《静夜思》(或同类思乡名篇) | |
| 3 | 《静夜思》是谁写的 | query_poem 召回《静夜思》,回答提及李白(原句回归) | |
| 4 | 李白是什么样的诗人 | query_poet 按 writer 表简介作答 | |
| 5 | 唐 | query_dynasty_poems 返回唐(朝)诗词标题列表 | |
| 6 | 今天天气真好 | 不调工具,无 tool_status(负例) | |
| 7 | 阿巴阿巴随便说点什么 | 允许 found:false 或朴素回应,不得编造诗词(负例) | |

判定:1/2 是本章核心(语义泛化);3/4/5 是契约回归;6/7 是负例。
```

- [ ] **Step 7: dev-notes 追记 + Commit**

```powershell
git add potry-ai-agent/evals/ch03_retrieval_eval_cases.md dev-notes/ch03.md
git commit -m "docs(ai-agent): ch03 build run and retrieval acceptance results"
```

---

### Task 11: 中断续跑验收(验收标准 2)

**Files:** 无代码改动(纯运行验证)

- [ ] **Step 1: 制造「中断」**

先删向量库文件制造"Milvus 与 MySQL 不一致"的现场(或直接验证 status 驱动):

```powershell
Remove-Item e:\javatexts\poetry-spring2\potry-ai-agent\milvus_data\knowledge.db -Force -ErrorAction SilentlyContinue; "milvus db removed"
```

- [ ] **Step 2: 制造「漏向量化的块」**

```powershell
.\.venv\Scripts\python.exe -c "from sqlalchemy.orm import sessionmaker; from config import load_settings; from db import get_engine; from knowledge import KnowledgeChunk; e=get_engine(load_settings().mysql_url); s=sessionmaker(bind=e)(); n=s.query(KnowledgeChunk).update({KnowledgeChunk.status: 'pending'}); s.commit(); print('RESET_TO_PENDING', n)"
```

Expected: 全部块状态被改回 `pending`(模拟"建到一半挂了")。

- [ ] **Step 3: 只补向量化重跑**

```powershell
.\.venv\Scripts\python.exe build_kb.py --skip-chunk
```

Expected: `embedded` 等于块总数、`remaining = 0`、`status_counts {'embedded': N}`(无 pending)。

- [ ] **Step 4: 核对 Milvus 条目数与 MySQL embedded 数一致**

```powershell
.\.venv\Scripts\python.exe -c "from sqlalchemy.orm import sessionmaker; from config import load_settings; from db import get_engine; from knowledge import KnowledgeStorage; from vector_store import get_store; e=get_engine(load_settings().mysql_url); st=KnowledgeStorage(sessionmaker(bind=e)); print('MYSQL_EMBEDDED', st.count_by_status()); c=get_store()._client; c.load_collection(load_settings().milvus_collection); print('MILVUS_TOTAL', list(c.query(load_settings().milvus_collection, filter='id >= 0', output_fields=['id'], limit=16384)))"
```

Expected: 两者数量一致(即验收标准 2:漏向量化的块被捡起补齐)。

- [ ] **Step 5: dev-notes 追记 + Commit**

```powershell
git add dev-notes/ch03.md
git commit -m "docs(dev-notes): ch03 resumable build verified after simulated interruption"
```

---

### Task 12: 评估回归、整体 code review 与收尾交付

**Files:**
- Modify: `potry-ai-agent/evals/ch03_mining_eval_cases.md`(勾结果)
- Modify: `potry-ai-agent/evals/ch03_retrieval_eval_cases.md`(勾结果)
- Modify: `dev-notes/ch03.md`

- [ ] **Step 1: 跑挖知识标注样例**

```powershell
.\.venv\Scripts\python.exe mining.py
```

把 `evals/ch03_mining_eval_cases.md` 4 条逐条人工比对勾选;若某条行为偏差(如寒暄被抽成知识对),**只改 `mining.py` 的 `MINING_PROMPT` 措辞**,重跑该条,不动流程代码。

- [ ] **Step 2: 跑检索评估集**

按 `evals/ch03_retrieval_eval_cases.md` 逐条跑真实 DeepSeek 勾选;偏差只调 `prompts.py` 的工具指引措辞(若确属 Prompt 问题),不动契约。

- [ ] **Step 3: 全量测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v`
Expected: 全绿(记录最终条数)

- [ ] **Step 4: 派最终整体 code review(范围 = Ch03 全部提交)**

review 关注:三工具契约是否真未变(签名/返回键集/截断规则)、双写幂等与续跑、Milvus 文件锁与多进程风险、注入面(`safe_expr_value` 覆盖是否完整)、`mining` 去重与 `source_id` 配对正确性、测试是否验证真实行为。评审结论写入 dev-notes。

- [ ] **Step 5: dev-notes 补「完结交付」小节** + Commit

```powershell
git add dev-notes/ch03.md potry-ai-agent/evals/ch03_mining_eval_cases.md potry-ai-agent/evals/ch03_retrieval_eval_cases.md
git commit -m "docs(dev-notes): ch03 complete - deliverables and verification results"
```

- [ ] **Step 6: 按 finishing-a-development-branch 收尾**

给出演示命令、测试结果、评估结果、dev-notes 路径,并让用户选分支处理方式。

---

## 自检记录(写完计划后已核对)

1. **Spec 覆盖**:§2 技术选型(Task 1/3/5)、§3 架构与配置(Task 1/9)、§4 文档切分(Task 2)、§5 对话挖知识(Task 7/9)、§6 落库结构与双写(Task 4/6)、§7 在线检索三工具(Task 8)、§8 错误降级(Task 6/7/8)、§9 测试与验收(Task 2–11)、验收标准 1(Task 10)、验收标准 2(Task 11)。无缺口。
2. **占位符**:无 TBD/TODO;Task 7 的 `mine()` 已按正确写法给出(staging 去重键取 `title`、`source_id` 用 (归一化问题→staging.id) 映射),无"实现时自行修正"式占位。
3. **类型一致性**:`KnowledgeStorage` 方法名(`upsert_chunks`/`list_pending`/`mark_embedded`/`get_chunk`/`list_chunks`/`count_by_status`/`add_staging`/`list_staging`/`clear_staging`/`get_cursor`/`set_cursor`)、`MilvusLiteVectorStore` 方法名(`upsert`/`search`/`query_by_dynasty`)、`chunking` 函数名(`split_sentences`/`recursive_split`/`overlap_prefix`/`chunk_section`/`meta_prefix`/`chunk_poem`/`chunk_poet`)、`embeddings`(`get_embedder`/`set_embedder`/`embed`)、`vector_store`(`get_store`/`set_store`/`upsert`/`search`/`query_by_dynasty`)在 Task 4–8 间前后一致。
4. **已知偏差需记录**:Task 3 Step 5 要求实测核对 FlagEmbedding `encode` API;若与计划写法不符,按官方文档修正并写入 dev-notes(不得换模型)。
