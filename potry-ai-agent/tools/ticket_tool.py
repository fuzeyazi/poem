"""建工单工具:本系统唯一的写操作;必须经前端确认后由执行引擎放行。"""
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy.orm import sessionmaker

from app_storage import AppStorage
from config import load_settings
from db import get_engine
from tool_system.spec import current_invocation


class CreateTicketInput(BaseModel):
    ticket_type: Literal["内容纠错", "功能异常", "其他"] = Field(
        description="工单类型:内容纠错 / 功能异常 / 其他"
    )
    description: str = Field(
        min_length=4,
        description="用户的问题描述,尽量保留用户原话,至少 4 个字",
    )


def _storage_factory() -> sessionmaker:
    """单一入口:测试可 monkeypatch 注入内存/文件库。"""
    return sessionmaker(bind=get_engine(load_settings().mysql_url))


@tool("create_ticket", args_schema=CreateTicketInput)
async def create_ticket(ticket_type: str, description: str) -> dict:
    """创建工单。**仅在用户明确要求建工单/提交纠错单/反馈问题时调用**。

    用户只是抱怨、或问题描述还不清楚时,先追问补齐,不得编造描述。
    创建成功后返回 ticket_no,回复用户时必须把工单号原样告知。

    Args:
        ticket_type: 工单类型:内容纠错 / 功能异常 / 其他
        description: 用户的问题描述(至少 4 个字,尽量保留用户原话)
    """
    invocation = current_invocation()
    try:
        ticket_id, ticket_no = AppStorage(_storage_factory()).add_ticket(
            ticket_type=ticket_type,
            description=description,
            session_id=invocation.session_id or None,
            userid=invocation.userid,
        )
    except Exception as exc:  # noqa: BLE001 - 统一走契约失败分支
        return {"ok": False, "error": str(exc)[:200]}
    return {"ok": True, "ticket_id": ticket_id, "ticket_no": ticket_no}
