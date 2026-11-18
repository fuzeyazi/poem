"""验收 6:直接用执行引擎制造读超时与写超时,核对审计的 retry_count/status/耗时。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app_storage import AppStorage, ToolAuditLog
from config import load_settings
from db import get_engine
from tool_system.audit import AuditWriter
from tool_system.engine import ToolEngine
from tool_system.spec import ToolInvocation, ToolSpec, schema_of


@tool
async def slow_read(keyword: str) -> dict:
    """慢读探针。"""
    await asyncio.sleep(1.5)
    return {"ok": True, "found": True, "keyword": keyword}


@tool
async def slow_write(description: str) -> dict:
    """慢写探针。"""
    await asyncio.sleep(1.5)
    return {"ok": True, "ticket_no": "TK999999"}


async def main() -> None:
    settings = load_settings()
    factory = sessionmaker(bind=get_engine(settings.mysql_url))
    storage = AppStorage(factory)
    engine = ToolEngine(settings, AuditWriter(storage))

    read_spec = ToolSpec(
        name="probe_slow_read", description="", input_schema=schema_of(slow_read),
        tool=slow_read, timeout=0.2, max_retries=settings.tool_max_retries,
    )
    write_spec = ToolSpec(
        name="probe_slow_write", description="", input_schema=schema_of(slow_write),
        tool=slow_write, permission="write", requires_confirmation=True, timeout=0.2,
    )

    read_result = await engine.execute(
        read_spec, {"keyword": "静夜思"},
        ToolInvocation(session_id="probe-ch07", tool_call_id="probe-read"),
    )
    write_result = await engine.execute(
        write_spec, {"description": "超时探针"},
        ToolInvocation(session_id="probe-ch07", tool_call_id="probe-write", approved=True),
    )
    print("[probe] read:", read_result)
    print("[probe] write:", write_result)

    with factory() as session:
        rows = session.execute(
            select(ToolAuditLog)
            .where(ToolAuditLog.session_id == "probe-ch07")
            .order_by(ToolAuditLog.id)
        ).scalars().all()
    for row in rows:
        print(f"[audit] {row.tool_name} status={row.status} "
              f"retry={row.retry_count} duration_ms={row.duration_ms}")


if __name__ == "__main__":
    asyncio.run(main())
