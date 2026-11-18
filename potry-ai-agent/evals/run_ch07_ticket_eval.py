"""Ch07 create_ticket 行为评估:真实模型判断“该不该建单”;错例退出码 1。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import HumanMessage, SystemMessage

from chat_service import build_llm
from config import load_settings
from prompts import SYSTEM_PROMPT_TEMPLATE
from tools.ticket_tool import create_ticket

CASES = [
    ("帮我建个工单", False),
    ("我要提交一个纠错单", False),
    ("你们答错了,我不满意", False),
    ("《静夜思》是谁写的", False),
    ("查一下我的纠错单进度", False),
    ("帮我建个工单:原文有错字,《静夜思》第二句应为床前明月光", True),
]


def valid_ticket_call(ai) -> bool:
    for call in getattr(ai, "tool_calls", None) or []:
        if call["name"] != "create_ticket":
            continue
        args = call.get("args") or {}
        if args.get("ticket_type") in {"内容纠错", "功能异常", "其他"} and len(
            str(args.get("description") or "")
        ) >= 4:
            return True
    return False


async def main() -> int:
    llm = build_llm(load_settings())
    bound = llm.bind_tools([create_ticket])
    correct = 0
    for text, should_call in CASES:
        ai = await bound.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT_TEMPLATE.format()),
            HumanMessage(content=text),
        ])
        called = valid_ticket_call(ai)
        ok = called == should_call
        correct += int(ok)
        print(f"{'PASS' if ok else 'FAIL'} should_call={should_call} called={called} | {text}")
    total = len(CASES)
    print(f"[eval] create_ticket {correct}/{total} = {correct / total:.0%}")
    return 0 if correct == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
