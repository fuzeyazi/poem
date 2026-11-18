"""Ch09 打通(二):用户个人数据工具 —— 个性化伴学的数据入口。

数据源为 Java 侧(potry-service)维护的用户收藏表,agent 只读直查
(与 potry/writer 语料同一共享库模式);Ch09 后续将扩展学习计划 / 答题弱项工具。
"""
from langchain_core.tools import tool
from sqlalchemy import select

from config import load_settings
from db import Potry, UserCollectionPoem, UserLearningSchedule, Userbook, UserbookPoem, new_session
from tool_system.spec import current_invocation

_MAX_ITEMS = 10  # 回灌上限,防上下文爆炸(与 poetry_tools 同口径)


def _get_session():
    return new_session(load_settings().mysql_url)


def _verified_userid() -> str | None:
    """会话内验签身份(JWT claims);无则 None——个性化工具不信任 LLM 传参。"""
    return current_invocation().userid


@tool
def get_my_collection(limit: int = 5) -> dict:
    """查询**当前用户**在诗词平台收藏的诗(无需用户提供用户ID)。
    返回收藏列表(诗名/作者/朝代/收藏时间),可用于了解用户偏好、推荐讲解或复习提醒。"""
    limit = max(1, min(int(limit), _MAX_ITEMS))
    uid = _verified_userid()
    if not uid or not str(uid).isdigit():
        return {"ok": False, "error_type": "no_user", "message": "当前会话没有已验证的用户身份(需带 token 登录)"}
    with _get_session() as session:
        rows = session.execute(
            select(
                Potry.title,
                Potry.writer,
                Potry.dynasty,
                UserCollectionPoem.collecter_at,
            )
            .join(UserCollectionPoem, UserCollectionPoem.poemid == Potry.id)
            .where(UserCollectionPoem.userid == int(uid))
            .order_by(UserCollectionPoem.id.desc())
            .limit(limit)
        ).all()
    items = [
        {"title": r.title, "writer": r.writer, "dynasty": r.dynasty,
         "collectedAt": str(r.collecter_at or "")}
        for r in rows
    ]
    return {"ok": True, "found": bool(items), "data": items,
            "summary": f"共收藏 {len(items)} 首" + (f"(最近{limit}条)" if len(items) == limit else "")}


_STAGE_LABELS = {0: "首轮复习(1天)", 1: "第2轮(3天)", 2: "第3轮(7天)", 3: "第4轮(14天)", 4: "第5轮(30天)"}


@tool
def get_study_plan(limit: int = 10) -> dict:
    """查询**当前用户**的诗词背诵学习计划与艾宾浩斯复习进度(无需用户提供用户ID)。返回:
    dueToday(今日应复习:title/writer/轮次/到期日)、upcoming(未来复习)、learning(待学习)、
    graduated(已毕业数)。可用于主动提醒用户今日复习、规划背诵安排。"""
    limit = max(1, min(int(limit), _MAX_ITEMS))
    uid = _verified_userid()
    if not uid or not str(uid).isdigit():
        return {"ok": False, "error_type": "no_user", "message": "当前会话没有已验证的用户身份(需带 token 登录)"}
    with _get_session() as session:
        books = session.execute(
            select(Userbook.book_id, Userbook.book_name).where(Userbook.user_id == int(uid))
        ).all()
        rows = session.execute(
            select(
                UserbookPoem.poem_id, UserbookPoem.reviewCount,
                UserbookPoem.lastReviewDate, UserbookPoem.nextReviewDate, Potry.title, Potry.writer,
            )
            .join(Potry, Potry.id == UserbookPoem.poem_id)
            .where(UserbookPoem.book_id.in_([b.book_id for b in books]) if books else False)
        ).all() if books else []
        learning = session.execute(
            select(Potry.title, Potry.writer, UserLearningSchedule.scheduled_date)
            .join(Potry, Potry.id == UserLearningSchedule.poem_id)
            .where(UserLearningSchedule.user_id == int(uid),
                   UserLearningSchedule.is_learned == 0)
            .limit(limit)
        ).all()

    due_today, upcoming, seen = [], [], set()
    graduated = 0
    for r in sorted(rows, key=lambda x: (x.nextReviewDate is None, x.nextReviewDate or "")):
        key = (r.title, r.writer)  # 同一首诗可能在多本诗集里,去重后按最近到期归并
        if r.nextReviewDate is None:
            graduated += 1
            continue
        if key in seen:
            continue
        seen.add(key)
        item = {
            "title": r.title, "writer": r.writer,
            "reviewCount": r.reviewCount or 0,
            "stage": _STAGE_LABELS.get(r.reviewCount or 0, "已毕业"),
            "nextReviewDate": str(r.nextReviewDate or "")[:10] or None,
        }
        (due_today if str(r.nextReviewDate)[:10] <= _today_str() else upcoming).append(item)
    due_today, upcoming = due_today[:limit], upcoming[:5]
    return {
        "ok": True, "found": bool(due_today or upcoming or learning),
        "data": {
            "books": [b.book_name for b in books],
            "dueToday": due_today,
            "upcoming": upcoming[:5],
            "learning": [
                {"title": t.title, "writer": t.writer, "scheduledDate": str(t.scheduled_date or "")[:10]}
                for t in learning
            ],
            "graduated": graduated,
        },
        "summary": f"今日应复习 {len(due_today)} 首,待学 {len(learning)} 首,已毕业 {graduated} 首",
    }


def _today_str() -> str:
    from datetime import date

    return date.today().isoformat()
