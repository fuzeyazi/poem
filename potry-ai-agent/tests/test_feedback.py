"""feedback 表落库:列名映射(注意原表拼写 messsage / creatime)与行数 +1。"""
import asyncio

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app_storage import AppBase, AppStorage, CORRECTION_CATEGORIES, Correction, Feedback


def _memory_factory():
    engine = create_engine("sqlite:///:memory:")
    AppBase.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_feedback_columns_match_existing_table():
    # 原表列名拼写照抄:userid / messsage / creatime
    assert {c.name for c in Feedback.__table__.columns} == {"id", "userid", "messsage", "creatime"}


def test_add_feedback_appends_row():
    factory = _memory_factory()
    storage = AppStorage(factory)
    with factory() as session:
        before = session.execute(select(func.count()).select_from(Feedback)).scalar()
    fid = storage.add_feedback("回答不准确,希望改进")
    assert fid is not None
    with factory() as session:
        after = session.execute(select(func.count()).select_from(Feedback)).scalar()
        row = session.get(Feedback, fid)
    assert after == before + 1
    assert row.messsage == "回答不准确,希望改进"
    assert row.userid is None            # 无登录态留空
    assert row.creatime is not None


def test_submit_feedback_tool_writes_through_engine(monkeypatch, tmp_path):
    """工具走真实 engine:注意同步 @tool 会被丢到线程池执行,
    故必须用**文件型** SQLite(内存库每线程一个连接,换线程会拿到空库)。"""
    import tools.feedback_tool as ft

    engine = create_engine(f"sqlite:///{tmp_path / 'feedback.db'}")
    AppBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(ft, "_storage_factory", lambda: factory)

    result = asyncio.run(ft.submit_feedback.ainvoke({"content": "工单测试"}))
    assert result["ok"] is True and result["submitted"] is True

    with factory() as session:
        count = session.execute(select(func.count()).select_from(Feedback)).scalar()
    assert count == 1


def test_correction_columns_match_spec():
    assert {c.name for c in Correction.__table__.columns} == {
        "id", "userid", "poem_id", "category", "detail", "session_id", "creatime"
    }


def test_correction_categories_are_fixed_list():
    assert CORRECTION_CATEGORIES == (
        "格律错误", "作者张冠李戴", "原文有误", "译文有误", "赏析不认同",
    )


def test_add_correction_appends_row():
    engine = create_engine("sqlite:///:memory:")
    AppBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    storage = AppStorage(factory)
    cid = storage.add_correction(
        category="作者张冠李戴", detail="这首诗的作者应是王某", poem_id=7, session_id="s1"
    )
    assert cid is not None
    with factory() as session:
        row = session.get(Correction, cid)
    assert row.category == "作者张冠李戴"
    assert row.poem_id == 7 and row.session_id == "s1"
    assert row.userid is None and row.creatime is not None


def test_add_correction_rejects_unknown_category():
    engine = create_engine("sqlite:///:memory:")
    AppBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    storage = AppStorage(factory)
    with pytest.raises(ValueError, match="category"):
        storage.add_correction(category="乱填类目", detail="x")
