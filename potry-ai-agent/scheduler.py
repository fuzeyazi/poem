"""APScheduler 定时任务:进程内 cron 跑「对话挖知识」(spec §5)。

版本:apscheduler 3.11.3(BackgroundScheduler + CronTrigger.from_crontab);
未引入 APScheduler 4.x(其 API 与 3.x 不兼容),实现前已过 Context7 核对。
"""
import traceback

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import Settings
from db import get_engine
from knowledge import KnowledgeStorage
from mining import mine
from storage import ChatStorage


def run_mining(settings: Settings) -> None:
    """定时任务入口:失败只打印日志,不抛出(避免调度器线程被打断)。"""
    try:
        from sqlalchemy.orm import sessionmaker

        engine = get_engine(settings.mysql_url)
        factory = sessionmaker(bind=engine)
        stats = mine(settings=settings, storage=KnowledgeStorage(factory), chat_storage=ChatStorage(factory))
        print(f"[mining] 定时任务完成: {stats}")
    except Exception as exc:  # noqa: BLE001 - 定时任务失败不炸调度器
        print(f"[mining] 定时任务失败: {str(exc)[:200]}")
        print(traceback.format_exc()[:200])


def run_flywheel(settings: Settings) -> None:
    """后台兜底:处理未匹配的 pending_questions。"""
    try:
        import asyncio

        from chat_service import build_llm
        from flywheel import FlywheelService
        from sqlalchemy.orm import sessionmaker

        engine = get_engine(settings.mysql_url)
        storage = KnowledgeStorage(sessionmaker(bind=engine))
        service = FlywheelService(storage, build_llm(settings))
        processed = asyncio.run(service.drain())
        print(f"[flywheel] 定时处理 {processed} 条")
    except Exception as exc:  # noqa: BLE001 - 定时任务失败不炸调度器
        print(f"[flywheel] 定时任务失败: {str(exc)[:200]}")


def build_scheduler(settings: Settings) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        run_mining,
        CronTrigger.from_crontab(settings.mining_cron),
        kwargs={"settings": settings},
        id="mining",
        replace_existing=True,
        coalesce=True,              # 错过的多次触发合并成一次
        misfire_grace_time=3600,    # 停机 1 小时内仍补跑一次
    )
    scheduler.add_job(
        run_flywheel,
        IntervalTrigger(minutes=settings.flywheel_drain_minutes),
        kwargs={"settings": settings},
        id="flywheel",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=600,
    )
    return scheduler
