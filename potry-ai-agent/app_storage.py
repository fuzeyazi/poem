"""应用侧业务表映射:复用 Java 既有 `feedback` 表。

列名**原样照抄**库中已有定义(实测 `SHOW COLUMNS FROM feedback`):
`id` int PK auto_increment / `userid` int NULL / `messsage` text NULL /
`creatime` timestamp DEFAULT CURRENT_TIMESTAMP。`messsage` 与 `creatime` 的拼写即原文,
不得"顺手纠正",否则与线上表结构不一致。
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class AppBase(DeclarativeBase):
    pass


class Feedback(AppBase):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userid: Mapped[int | None] = mapped_column(Integer)
    messsage: Mapped[str | None] = mapped_column(Text)
    creatime: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.now)


# 纠错/复核单的固定类目(单一来源:后端校验 + 下发前端做下拉,前端不再自维护一份)
CORRECTION_CATEGORIES = (
    "格律错误",
    "作者张冠李戴",
    "原文有误",
    "译文有误",
    "赏析不认同",
)


class Correction(AppBase):
    """纠错/复核单(需求原文的"退款单"在诗词域的等价物,spec §9)。

    与 `feedback` 同 Base,由 `main.init_db` 的 `create_all` 一并建表;与 feedback 并存互不影响。
    """

    __tablename__ = "corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userid: Mapped[int | None] = mapped_column(Integer)
    poem_id: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str | None] = mapped_column(Text)
    session_id: Mapped[str | None] = mapped_column(String(64))
    creatime: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.now)


class Ticket(AppBase):
    """建单确认流落库表(Ch07 spec §9.1);不挂外键。"""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_no: Mapped[str] = mapped_column(String(32), default="")
    userid: Mapped[str | None] = mapped_column(String(64))
    session_id: Mapped[str | None] = mapped_column(String(64))
    ticket_type: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="submitted")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.now)


class ToolAuditLog(AppBase):
    """工具调用审计(Ch07 spec §7);不挂外键,写失败不得阻断工具。"""

    __tablename__ = "tool_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(String(64))
    tool_call_id: Mapped[str | None] = mapped_column(String(64))
    tool_name: Mapped[str] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[str] = mapped_column(Text)
    result_summary: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.now)


class AppStorage:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._factory = session_factory

    def add_feedback(self, message: str, userid: int | None = None) -> int:
        """写一条反馈,返回新行 id(表已存在,create_all 幂等不重建)。"""
        with self._factory() as session:
            row = Feedback(userid=userid, messsage=message)
            session.add(row)
            session.commit()
            return row.id

    def add_correction(
        self, category: str, detail: str | None = None,
        poem_id: int | None = None, session_id: str | None = None, userid: int | None = None,
    ) -> int:
        """写一条纠错单,返回新行 id。类目非法直接抛 ValueError(边界校验,不静默存脏数据)。"""
        if category not in CORRECTION_CATEGORIES:
            raise ValueError(f"category 必须是固定类目之一,收到: {category}")
        with self._factory() as session:
            row = Correction(
                userid=userid, poem_id=poem_id, category=category,
                detail=detail, session_id=session_id,
            )
            session.add(row)
            session.commit()
            return row.id

    def add_ticket(
        self, ticket_type: str, description: str,
        session_id: str | None = None, userid: str | None = None,
    ) -> tuple[int, str]:
        """写工单并回填 `TK%06d` 编号,返回 (id, ticket_no)。"""
        with self._factory() as session:
            row = Ticket(
                userid=userid, session_id=session_id,
                ticket_type=ticket_type, description=description,
            )
            session.add(row)
            session.flush()
            row.ticket_no = f"TK{row.id:06d}"
            session.commit()
            return row.id, row.ticket_no

    def add_tool_audit(
        self, *, session_id: str | None, tool_call_id: str | None,
        tool_name: str, source: str, arguments: str, result_summary: str,
        status: str, error: str | None = None,
        retry_count: int = 0, duration_ms: int = 0,
    ) -> int:
        """每次工具调用落一条审计;调用方负责 try/except,本方法不吞异常。"""
        with self._factory() as session:
            row = ToolAuditLog(
                session_id=session_id, tool_call_id=tool_call_id,
                tool_name=tool_name, source=source, arguments=arguments,
                result_summary=result_summary, status=status, error=error,
                retry_count=retry_count, duration_ms=duration_ms,
            )
            session.add(row)
            session.commit()
            return row.id
