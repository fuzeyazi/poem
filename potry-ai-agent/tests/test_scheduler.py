"""定时任务(spec §5):cron 注册契约 + 失败不炸调度器契约。"""
from unittest.mock import patch

from scheduler import build_scheduler, run_mining


def test_build_scheduler_registers_cron_job():
    class S:
        mining_cron = "0 3 * * *"
        mining_batch_size = 20
        flywheel_drain_minutes = 5.0

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


from apscheduler.triggers.interval import IntervalTrigger

from config import Settings
from scheduler import build_scheduler


def test_scheduler_has_flywheel_job():
    settings = Settings(
        llm_base_url="http://fake", llm_api_key="sk-fake", llm_model="fake",
        history_max_tokens=2000, llm_temperature=0.7,
        mysql_url="sqlite:///:memory:", embedding_model_path="fake-model-path",
        flywheel_drain_minutes=7,
    )
    scheduler = build_scheduler(settings)
    job = scheduler.get_job("flywheel")
    assert job is not None
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval.total_seconds() == 7 * 60
