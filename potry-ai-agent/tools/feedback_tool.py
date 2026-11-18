"""提交反馈工具:写 feedback 表。

⚠️ spec §12 偏差留痕:本工具**按用户决定注册给主力 Agent**;为降低"Agent 自行写库"
与需求第 8 条"后端不自动触发"的张力,工具描述里**显式约束**:仅当用户明确要求
提交反馈时才调用。验收③另行显式验证"未点击按钮时 feedback 行数不变"。
"""
from langchain_core.tools import tool
from sqlalchemy.orm import sessionmaker

from app_storage import AppStorage
from config import load_settings
from db import get_engine


def _storage_factory() -> sessionmaker:
    """单一入口:测试可 monkeypatch 本函数注入内存/文件库。"""
    return sessionmaker(bind=get_engine(load_settings().mysql_url))


@tool
def submit_feedback(content: str) -> dict:
    """提交用户反馈到反馈表。

    **仅在用户明确要求"提交反馈""建工单""帮我记下来"时才调用**;
    用户只是表达不满、抱怨答错而没有要求提交时,**不得**调用本工具。

    Args:
        content: 用户反馈的原文内容
    """
    try:
        feedback_id = AppStorage(_storage_factory()).add_feedback(content)
    except Exception as exc:  # noqa: BLE001 - 统一走契约失败分支,不抛
        return {"ok": False, "error": str(exc)[:200]}
    return {"ok": True, "submitted": True, "feedbackId": feedback_id}
