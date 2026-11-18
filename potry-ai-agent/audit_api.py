"""Ch09 管理补全:工具调用审计只读 API。

数据源:tool_audit_logs(Ch07 工具系统逐次落库;此前只有表没有界面)。
管理端鉴权:配置 ADMIN_JWT_SECRET_KEY 后需有效管理 token(见 auth.resolve_admin)。
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from app_storage import ToolAuditLog
from auth import resolve_admin

_MAX_ARG_LEN = 400  # arguments/result 摘要回显截断,防大载荷撑爆管理页


def create_audit_router(session_factory) -> APIRouter:
    router = APIRouter()

    @router.get("/api/admin/audit")
    def list_audit(request: Request, limit: int = 50, offset: int = 0,
                   tool_name: str = "", status: str = "", session_id: str = ""):
        """工具审计流:按工具/状态/会话过滤,新在前。"""
        resolve_admin(request)
        limit = max(1, min(limit, 200))
        stmt = select(ToolAuditLog)
        if tool_name:
            stmt = stmt.where(ToolAuditLog.tool_name == tool_name)
        if status:
            stmt = stmt.where(ToolAuditLog.status == status)
        if session_id:
            stmt = stmt.where(ToolAuditLog.session_id == session_id)
        with session_factory() as session:
            total = session.scalar(
                select(func.count()).select_from(stmt.subquery())
            ) or 0
            rows = session.execute(
                stmt.order_by(ToolAuditLog.id.desc()).offset(offset).limit(limit)
            ).scalars().all()
        return {
            "total": total,
            "rows": [
                {
                    "id": r.id, "createdAt": str(r.created_at or ""),
                    "sessionId": r.session_id or "", "toolName": r.tool_name,
                    "source": r.source, "status": r.status,
                    "durationMs": r.duration_ms, "retryCount": r.retry_count,
                    "arguments": (r.arguments or "")[:_MAX_ARG_LEN],
                    "resultSummary": (r.result_summary or "")[:_MAX_ARG_LEN],
                    "error": (r.error or "")[:200],
                }
                for r in rows
            ],
        }

    return router
