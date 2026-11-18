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
