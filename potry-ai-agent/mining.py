r"""对话挖知识:历史对话 → 分批喂 LLM 抽问答对 → 暂存 → 整体去重 → 入库(待向量化)。

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
_PROGRESS_EVERY = 20  # 每 N 批打一次进度(按批调真实 LLM,全程静默时无法判断卡住没)


def normalize_question(question: str) -> str:
    """去空白与标点,统一小写,作为去重键。"""
    return "".join(ch for ch in (question or "").lower() if ch not in _NORMALIZE_DROP)


def parse_pairs(raw: str) -> list[dict]:
    """从 LLM 输出里解析 JSON 数组;带 ``` 围栏、夹带散文方括号时尽力提取;失败返回 []。"""
    text = (raw or "").strip()
    m = _FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    # 用 raw_decode 从每个 "[" 起点尝试,避免 LLM 引文里的散文方括号(如 "参考 [1]:")
    # 被 find/rfind 切出非法子串而整批丢知识。注意 "[1]" 本身是合法 JSON 数组,
    # 故只接受「含问答对 dict 的数组」为候选,否则继续找下一个 "["
    decoder = json.JSONDecoder()
    data = None
    for i, ch in enumerate(text):
        if ch != "[":
            continue
        try:
            candidate, _ = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, list) and any(
            isinstance(it, dict) and it.get("question") and it.get("answer") for it in candidate
        ):
            data = candidate
            break
    if data is None:
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
    """取 messages.id > after_id 的 user/assistant 配对,跳过 tool 行;按会话分组。

    工具轮落库顺序为 [user, assistant(空,带 tool_call_id), tool, assistant(最终答案)];
    配对时跳过带 tool_call_id 的空 assistant 中间态,否则它会抢占 last_user、
    导致最终答案被跳过(本项目诗词问答几乎全走工具)。
    """
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
            elif r.role == "assistant" and r.tool_call_id is not None:
                continue  # 工具调用中间态(content 为空),不是最终答案
            elif r.role == "assistant" and last_user is not None:
                pairs.append({"user": last_user, "assistant": r.content})
                last_user = None
        if pairs:
            out.append(
                {
                    "session_id": str(conv_id),
                    "pairs": pairs,
                    "min_message_id": msgs[0].id,  # 该会话首条:失败时不推进水位越过它
                    "max_message_id": msgs[-1].id,
                }
            )
    return out


def _render_transcript(pairs: list[dict]) -> str:
    return "\n".join(f"用户: {p['user']}\n助手: {p['assistant']}" for p in pairs)


def _parse_tags(text: str | None) -> list:
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

    total_pairs = sum(len(t["pairs"]) for t in transcripts)
    print(f"[mining] 会话 {len(transcripts)} 个,问答对 {total_pairs} 条,批大小 {batch_size}")

    extracted: list[dict] = []
    max_id = cursor
    failed_min_id: int | None = None
    batches = 0
    for t in transcripts:
        session_failed = False
        pairs = t["pairs"]
        for i in range(0, len(pairs), batch_size):
            batches += 1
            chunk = pairs[i : i + batch_size]
            # prompt 模板渲染放在 try 外:模板变量缺失属编码错误,不能被吞成"批次失败"
            messages = MINING_PROMPT.invoke({"transcript": _render_transcript(chunk)})
            try:
                resp = llm.invoke(messages)
                got = parse_pairs(getattr(resp, "content", "") or "")
            except Exception as exc:  # noqa: BLE001 - 单批失败标记会话失败,不推进水位
                session_failed = True
                print(f"[mining] 批次抽取失败,跳过: {str(exc)[:200]}")
                continue
            for g in got:
                extracted.append({**g, "source_session_id": t["session_id"]})
            if batches % _PROGRESS_EVERY == 0:
                print(f"[mining] 已处理 {batches} 批,抽取 {len(extracted)} 条")
        if session_failed:
            # 失败会话下轮要重挖,整体水位不得越过它的最小消息 id
            failed_min_id = (
                t["min_message_id"] if failed_min_id is None else min(failed_min_id, t["min_message_id"])
            )
        else:
            max_id = max(max_id, t["max_message_id"])
    if failed_min_id is not None:
        max_id = min(max_id, failed_min_id - 1)

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
        [{"question": s["question"], "answer": s["answer"], "tags": _parse_tags(s["tags"])} for s in staged],
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
