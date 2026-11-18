"""Ch05 评估集:意图识别 / 指代消解·改写 / Query 扩写 / 多轮串 的真实模型跑批。

纯 Prompt 类任务按用户工作要求用**标注样例替代 TDD**(见 dev-notes/ch05.md 阶段 4)。
用法(在 potry-ai-agent 下执行,需 .env 可用):
    .\.venv\Scripts\python.exe eval_ch05.py
"""
import asyncio

from chat_service import build_llm
from config import load_settings
from prompts import EXPAND_PROMPT, INTENT_PROMPT, RESOLVE_PROMPT
from workflow.expand import parse_queries
from workflow.intent import parse_intent_response
from workflow.resolve import format_history, parse_resolve_result

# ---------- 意图识别评估集:8 类 × 4 条(含边界与怪问题) ----------
INTENT_SAMPLES = [
    ("《静夜思》表达了什么感情", "poem_explain"),
    ("这首诗是什么意思", "poem_explain"),
    ("帮我赏析一下《春望》", "poem_explain"),
    ("举头望明月出自哪首诗", "poem_explain"),            # 典故/出处并入 poem_explain
    ("那首讲月亮的叫啥", "find_poem"),
    ("帮我找一首写思乡的诗", "find_poem"),
    ("唐代有哪些著名的诗", "find_poem"),                  # 查朝代并入 find_poem
    ("宋朝的词人写了哪些名篇", "find_poem"),
    ("李白是什么朝代的", "find_poet"),
    ("介绍一下杜甫", "find_poet"),
    ("苏轼写过哪些名篇", "find_poem"),
    ("王维是什么风格", "find_poet"),
    ("这句合不合律", "poem_meter"),
    ("这首是不是七律", "poem_meter"),
    ("这首诗押韵出律了吗", "poem_meter"),
    ("平仄对不对", "poem_meter"),
    ("作者是不是搞错了", "poem_verify"),
    ("原文是不是有讹字", "poem_verify"),
    ("这首诗的朝代标得对吗", "poem_verify"),
    ("这首诗真的是李白写的吗", "poem_verify"),
    ("答得不对,我不满意", "complaint"),
    ("你搞错了吧", "complaint"),
    ("这个答案有误", "complaint"),
    ("太离谱了,我不接受", "complaint"),
    ("今天天气不错", "chitchat"),
    ("你叫什么名字", "chitchat"),
    ("讲个笑话吧", "chitchat"),
    ("你吃饭了吗", "chitchat"),
    ("帮我写个 Java 排序", "other"),
    ("明天股市会涨吗", "other"),
    ("随便聊聊吧", "chitchat"),
    ("这个字怎么读来着", "other"),
]

# ---------- 指代消解/改写评估集:(history, 输入, 期望结果里必须出现的关键词, 期望 changed) ----------
RESOLVE_SAMPLES = [
    ([{"role": "user", "content": "《静夜思》是谁写的"}, {"role": "assistant", "content": "李白"}],
     "它合律吗", "静夜思", True),
    ([{"role": "user", "content": "《静夜思》是谁写的"}, {"role": "assistant", "content": "李白"}],
     "那这首诗什么意思", "静夜思", True),
    ([{"role": "user", "content": "帮我找一首写月亮的"}, {"role": "assistant", "content": "《静夜思》"}],
     "它押什么韵", "静夜思", True),
    ([{"role": "user", "content": "这首诗讲什么"}, {"role": "assistant", "content": "讲思乡"}],
     "那它合律吗", "合", True),
    ([{"role": "user", "content": "介绍一下杜甫"}, {"role": "assistant", "content": "杜甫,唐代诗人"}],
     "他写过哪些名篇", "杜甫", True),
    ([{"role": "user", "content": "《春晓》的作者是谁"}, {"role": "assistant", "content": "孟浩然"}],
     "这首诗有讹字吗", "春晓", True),
    ([{"role": "user", "content": "这首是不是七律"}, {"role": "assistant", "content": "是七律"}],
     "那它押什么韵", "七律", True),
    ([{"role": "user", "content": "《静夜思》的作者是谁"}, {"role": "assistant", "content": "李白"}],
     "它的朝代标对了吗", "静夜思", True),
    # 负例:问题本身已完整 → 必须原样透传(changed=False)
    ([{"role": "user", "content": "《静夜思》是谁写的"}, {"role": "assistant", "content": "李白"}],
     "《静夜思》这首诗表达了什么感情", "静夜思", False),
    ([{"role": "user", "content": "介绍一下杜甫"}, {"role": "assistant", "content": "杜甫,唐代诗人"}],
     "杜甫的代表作有哪些", "杜甫", False),
    ([], "《静夜思》这首诗合不合律", "静夜思", False),
    ([], "帮我找一首写梅花的诗", "梅花", False),
    ([{"role": "user", "content": "唐朝有哪些诗人"}, {"role": "assistant", "content": "李白、杜甫"}],
     "李白是什么朝代的", "李白", False),
    ([{"role": "user", "content": "这首诗什么意思"}, {"role": "assistant", "content": "讲思乡"}],
     "《静夜思》的作者是谁", "静夜思", False),
    ([{"role": "user", "content": "《春晓》是谁写的"}, {"role": "assistant", "content": "孟浩然"}],
     "孟浩然还有哪些作品", "孟浩然", False),
]

# ---------- Query 扩写评估集(仅判定子流程场景) ----------
EXPAND_SAMPLES = [
    "这首是不是七律",
    "这句合不合律",
    "这首诗押韵出律了吗",
    "平仄对不对",
    "这首诗的朝代标得对吗",
    "原文是不是有讹字",
    "作者是不是搞错了",
    "这首诗的体裁是什么",
    "这首词的分片对不对",
    "这个断句合不合词谱",
]

# ---------- 多轮串:同一会话连续三轮,逐轮断言意图(验收标准 1 的用例) ----------
MULTI_TURN = [
    ("《静夜思》是谁写的", "find_poet"),
    ("那它合律吗", "poem_meter"),
    ("帮我再找一首写月亮的", "find_poem"),
]


async def _intent_case(llm, text):
    message = await llm.ainvoke(INTENT_PROMPT.invoke({"question": text}))
    return parse_intent_response(message.content or "")


async def run_intent(llm):
    print("\n===== 评估集一:意图识别(32 条) =====")
    hits = 0
    for text, expected in INTENT_SAMPLES:
        label, conf = await _intent_case(llm, text)
        hit = label == expected
        hits += int(hit)
        print(("  OK " if hit else "  NG ") + f"{text} -> {label}({conf:.2f}) 期望 {expected}")
    rate = hits / len(INTENT_SAMPLES)
    print(f"意图准确率 {hits}/{len(INTENT_SAMPLES)} = {rate:.1%}")
    assert rate >= 0.80, f"意图准确率 {rate:.1%} < 80%"
    return rate


async def run_resolve(llm):
    print("\n===== 评估集二:指代消解 / Query 改写(15 条) =====")
    hits = 0
    for history, text, keyword, expect_changed in RESOLVE_SAMPLES:
        message = await llm.ainvoke(
            RESOLVE_PROMPT.invoke({"history": format_history(history), "question": text})
        )
        query, changed = parse_resolve_result(message.content or "")
        if not query:
            query, changed = text, False
        hit = (keyword in query) and (changed == expect_changed)
        hits += int(hit)
        print(("  OK " if hit else "  NG ") + f"{text} -> {query}(changed={changed}) 期望含「{keyword}」changed={expect_changed}")
    rate = hits / len(RESOLVE_SAMPLES)
    print(f"消解/透传正确率 {hits}/{len(RESOLVE_SAMPLES)} = {rate:.1%}")
    assert rate >= 0.80, f"消解正确率 {rate:.1%} < 80%"
    return rate


async def run_expand(llm):
    print("\n===== 评估集三:Query 扩写(10 条) =====")
    parseable = in_range = 0
    for text in EXPAND_SAMPLES:
        message = await llm.ainvoke(EXPAND_PROMPT.invoke({"question": text}))
        queries = parse_queries(message.content or "")
        parseable += int(bool(queries))
        ok_range = 2 <= len(queries) <= 5
        in_range += int(ok_range)
        print(("  OK " if ok_range else "  NG ") + f"{text} -> {len(queries)} 条:{queries}")
    parse_rate = parseable / len(EXPAND_SAMPLES)
    range_rate = in_range / len(EXPAND_SAMPLES)
    print(f"JSON 可解析率 {parseable}/{len(EXPAND_SAMPLES)} = {parse_rate:.1%};2–5 条占比 {range_rate:.1%}")
    assert parse_rate >= 0.90 and range_rate >= 0.80, "扩写评估集未达阈值"
    return parse_rate


async def run_multi_turn(llm):
    print("\n===== 评估集四:多轮串(问诗人 → 判格律 → 查诗词) =====")
    history = []
    hits = 0
    for text, expected in MULTI_TURN:
        label, conf = await _intent_case(llm, text)
        hit = label == expected
        hits += int(hit)
        message = await llm.ainvoke(RESOLVE_PROMPT.invoke({"history": format_history(history), "question": text}))
        resolved, changed = parse_resolve_result(message.content or "")
        if not resolved:
            resolved, changed = text, False
        print(("  OK " if hit else "  NG ") + f"{text} -> intent={label}({conf:.2f}) 期望 {expected};resolve={resolved}(changed={changed})")
        history += [{"role": "user", "content": text}, {"role": "assistant", "content": "(上轮回答)"}]
    rate = hits / len(MULTI_TURN)
    print(f"多轮意图准确率 {hits}/{len(MULTI_TURN)} = {rate:.1%}")
    assert rate == 1.0, "多轮串必须逐轮判对(验收标准 1)"
    return rate


async def main():
    settings = load_settings()
    llm = build_llm(settings)
    await run_intent(llm)
    await run_resolve(llm)
    await run_expand(llm)
    await run_multi_turn(llm)
    print("\n[eval] 全部评估集通过")


if __name__ == "__main__":
    asyncio.run(main())
