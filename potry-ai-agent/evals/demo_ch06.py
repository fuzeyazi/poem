"""Ch06 多轮演示/验收:连续对话、触发降级与摘要、最后追问早期事实。

用法(API 已启动):
    .\.venv\Scripts\python.exe evals\demo_ch06.py --turns 20
    .\.venv\Scripts\python.exe evals\demo_ch06.py --turns 30 --long --recall
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
    parser.add_argument("--long", action="store_true", help="每轮附带长诗句,快速触发层 2 摘要")
    args = parser.parse_args()
    session_id = uuid.uuid4().hex
    user_id = "demo-" + uuid.uuid4().hex[:8]
    async with httpx.AsyncClient(timeout=120) as client:
        for i in range(args.turns):
            question = QUESTIONS[i % len(QUESTIONS)]
            if args.long:
                question += "(请结合原句详细分析)" + "床前明月光疑是地上霜举头望明月低头思故乡" * 12
            answer = await ask(client, session_id, user_id, question)
            print(f"[{i + 1}] Q: {question[:40]}…\n    A: {answer[:80]}")
        if args.recall:
            answer = await ask(client, session_id, user_id, "最开始问的那首诗后来怎么说")
            print(f"[recall] {answer}")


if __name__ == "__main__":
    asyncio.run(main())
