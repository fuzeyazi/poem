"""启动降级契约(spec §9):建表失败不阻断服务启动,查询时才暴露数据库错误。"""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

import main


def _broken_engine():
    """连不上的 MySQL 引擎:127.0.0.1:1 立即拒连,connect_timeout 兜底防长挂。"""
    return create_engine(
        "mysql+pymysql://root:bad@127.0.0.1:1/nope",
        connect_args={"connect_timeout": 2},
    )


def test_init_db_swallows_connection_failure():
    # 真实走 create_all → 连库失败,断言 init_db 兜住不抛(不 mock 被测行为)
    main.init_db(_broken_engine())  # 不抛异常即通过


def test_app_survives_when_create_all_fails(monkeypatch):
    # 建表失败(坏库)时 app 仍能启动并应答 /health:lifespan 的 init_db 失败只告警
    monkeypatch.setattr(main, "engine", _broken_engine())
    with TestClient(main.app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "UP"


def test_warm_up_swallows_failure(monkeypatch):
    """预热失败(模型/向量库不可用)只告警,不得让服务起不来。"""
    import main

    def boom():
        raise RuntimeError("模型目录不存在")

    monkeypatch.setattr("embeddings.get_embedder", boom)
    main.warm_up()  # 不应抛异常


def test_lifespan_skips_warmup_when_disabled(monkeypatch):
    """WARMUP_ON_START 关闭时不预热(测试环境默认关闭,避免加载真模型)。"""
    import dataclasses

    import main

    called = {"n": 0}

    def spy():
        called["n"] += 1

    monkeypatch.setattr(main, "warm_up", spy)
    # settings 是 frozen dataclass,setattr(frozen 实例) 会抛 FrozenInstanceError
    # (raising=False 也拦不住),故替换整个模块级 settings 绑定为副本
    monkeypatch.setattr(main, "settings", dataclasses.replace(main.settings, warmup_on_start=False))
    from fastapi.testclient import TestClient

    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
    assert called["n"] == 0


def test_lifespan_warns_when_max_agent_steps_unset(monkeypatch, capsys):
    """MAX_AGENT_STEPS 未配置时,启动阶段明确告知回退到 WORKFLOW_MAX_ITER。"""
    import dataclasses

    import main

    monkeypatch.delenv("MAX_AGENT_STEPS", raising=False)
    monkeypatch.setattr(main, "settings", dataclasses.replace(main.settings, warmup_on_start=False))
    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
    out = capsys.readouterr().out
    assert f"[ctx] MAX_AGENT_STEPS 未配置,回退 WORKFLOW_MAX_ITER={main.settings.workflow_max_iter}" in out


def test_app_survives_invalid_mining_cron(monkeypatch):
    """非法 MINING_CRON 只让定时任务起不来,服务必须照常启动(降级契约)。"""
    import dataclasses

    import main
    from fastapi.testclient import TestClient

    monkeypatch.setattr(main, "settings", dataclasses.replace(main.settings, mining_cron="bad cron"))
    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
