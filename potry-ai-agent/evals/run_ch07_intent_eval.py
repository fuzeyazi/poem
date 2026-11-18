"""Ch07 意图评估:真实模型跑标注样例,打印准确率;任一错例即退出码 1。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chat_service import build_llm
from config import load_settings
from prompts import INTENT_PROMPT
from workflow.intent import parse_intent_response

CASES = [
    ("查一下《静夜思》的诗库档案", {"find_poem"}),
    ("查一下诗人在诗库里的资料", {"find_poet"}),
    ("帮我建个工单", {"other"}),
    ("我要提交一个纠错单", {"other"}),
    ("我的纠错单进度怎么样了", {"other"}),
    ("查一下《春望》的判定记录", {"other", "find_poem"}),
    ("答得不对,我不满意", {"complaint"}),
    ("《静夜思》表达了什么感情", {"poem_explain"}),
    ("唐代有哪些名篇", {"find_poem"}),
    ("这句合不合律", {"poem_meter"}),
]


async def main() -> int:
    llm = build_llm(load_settings())
    correct = 0
    for question, allowed in CASES:
        message = await llm.ainvoke(INTENT_PROMPT.invoke({"question": question}))
        label, confidence = parse_intent_response(message.content or "")
        ok = label in allowed
        correct += int(ok)
        print(f"{'PASS' if ok else 'FAIL'} allowed={sorted(allowed)} got={label} "
              f"conf={confidence:.2f} | {question}")
    total = len(CASES)
    print(f"[eval] intent {correct}/{total} = {correct / total:.0%}")
    return 0 if correct == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
