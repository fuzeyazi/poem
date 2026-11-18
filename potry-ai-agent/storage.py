"""对话落库:conversations / messages / conversation_summaries(ChatBase 独立于诗词表)。"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    inspect,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

# 主键/外键列类型:MySQL 用 BIGINT;SQLite 仅 INTEGER PRIMARY KEY 才自增
_ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class ChatBase(DeclarativeBase):
    pass


class Conversation(ChatBase):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    userid: Mapped[str | None] = mapped_column(String(64), index=True)
    summary_upto_msg_id: Mapped[int] = mapped_column(_ID_TYPE, default=0)
    layer1_from_msg_id: Mapped[int] = mapped_column(_ID_TYPE, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.now)


class Message(ChatBase):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(_ID_TYPE, ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(String(64))
    tool_call_id: Mapped[str | None] = mapped_column(String(64))
    tool_args: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ConversationSummary(ChatBase):
    __tablename__ = "conversation_summaries"
    __table_args__ = (UniqueConstraint("conversation_id", "seq", name="uq_summary_conv_seq"),)

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(_ID_TYPE, ForeignKey("conversations.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    upto_msg_id: Mapped[int] = mapped_column(_ID_TYPE)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


def ensure_schema(engine) -> None:
    """给已存在的 conversations 表补列(create_all 不会加列);失败逐列告警不阻断。"""
    inspector = inspect(engine)
    if "conversations" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("conversations")}
    ddl = {
        "userid": "VARCHAR(64) NULL",
        "summary_upto_msg_id": "BIGINT NOT NULL DEFAULT 0",
        "layer1_from_msg_id": "BIGINT NOT NULL DEFAULT 0",
        "updated_at": "DATETIME NULL",
    }
    for name, column_type in ddl.items():
        if name in existing:
            continue
        try:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE conversations ADD COLUMN {name} {column_type}"))
            print(f"[db] 迁移:conversations 新增列 {name}")
        except Exception as exc:  # noqa: BLE001 - 单列失败不影响其他列与服务启动
            print(f"[db] 迁移失败 col={name}: {str(exc)[:200]}")


class ChatStorage:
    """每轮只落 user + 最终 assistant;完整工具历史由 LangGraph checkpoint 保留。"""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._factory = session_factory

    def _conversation(self, session, session_id: str) -> Conversation | None:
        return (
            session.query(Conversation)
            .filter_by(session_id=session_id)
            .order_by(Conversation.id)
            .first()
        )

    def persist_turn(
        self, session_id: str, user_text: str, answer: str, userid: str | None = None
    ) -> tuple[int, int | None, int]:
        """写一条 user(非空时)与一条 assistant,返回 (conversation_id, user_msg_id, assistant_msg_id)。"""
        with self._factory() as session:
            conv = self._conversation(session, session_id)
            if conv is None:
                conv = Conversation(session_id=session_id, userid=userid)
                session.add(conv)
                session.flush()
            elif userid and not conv.userid:
                conv.userid = userid
            conv.updated_at = datetime.now()
            user_id = None
            if (user_text or "").strip():
                row = Message(conversation_id=conv.id, role="user", content=user_text)
                session.add(row)
                session.flush()
                user_id = row.id
            answer_row = Message(conversation_id=conv.id, role="assistant", content=answer or "")
            session.add(answer_row)
            session.flush()
            session.commit()
            return conv.id, user_id, answer_row.id

    def load_messages(self, conversation_id: int) -> list[dict]:
        with self._factory() as session:
            msgs = (
                session.query(Message)
                .filter_by(conversation_id=conversation_id)
                .order_by(Message.id)
                .all()
            )
            return [
                {
                    "role": m.role,
                    "content": m.content,
                    "tool_name": m.tool_name,
                    "tool_call_id": m.tool_call_id,
                    "tool_args": m.tool_args,
                }
                for m in msgs
            ]

    def load_context(self, session_id: str) -> dict:
        """一次取齐锚点、逐条消息(user/assistant)与摘要段落,供三层拼装。"""
        with self._factory() as session:
            conv = self._conversation(session, session_id)
            if conv is None:
                return {"conversationId": None, "summaryUpto": 0, "layer1From": 0,
                        "rows": [], "summaries": []}
            rows = (
                session.query(Message)
                .filter(Message.conversation_id == conv.id, Message.role.in_(("user", "assistant")))
                .order_by(Message.id)
                .all()
            )
            summaries = (
                session.query(ConversationSummary)
                .filter_by(conversation_id=conv.id)
                .order_by(ConversationSummary.seq)
                .all()
            )
            return {
                "conversationId": conv.id,
                "summaryUpto": conv.summary_upto_msg_id or 0,
                "layer1From": conv.layer1_from_msg_id or 0,
                "rows": [{"id": m.id, "role": m.role, "content": m.content} for m in rows],
                "summaries": [
                    {"seq": s.seq, "uptoMsgId": s.upto_msg_id, "content": s.content}
                    for s in summaries
                ],
            }

    def advance_layer1_anchor(self, conversation_id: int, msg_id: int) -> None:
        with self._factory() as session:
            conv = session.get(Conversation, conversation_id)
            if conv is not None:
                conv.layer1_from_msg_id = max(conv.layer1_from_msg_id or 0, msg_id)
                session.commit()

    def add_summary(self, conversation_id: int, content: str, upto_msg_id: int) -> int | None:
        """追加一段梗概并推进摘要锚点;唯一键冲突返回 None(视为已有同段)。"""
        with self._factory() as session:
            conv = session.get(Conversation, conversation_id)
            if conv is None:
                return None
            seq = (
                session.query(func.max(ConversationSummary.seq))
                .filter_by(conversation_id=conversation_id)
                .scalar()
                or 0
            ) + 1
            session.add(
                ConversationSummary(
                    conversation_id=conversation_id, seq=seq,
                    upto_msg_id=upto_msg_id, content=content,
                )
            )
            conv.summary_upto_msg_id = max(conv.summary_upto_msg_id or 0, upto_msg_id)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return None
            return seq

    def list_conversations(self, userid: str | None = None) -> list[dict]:
        with self._factory() as session:
            query = session.query(Conversation)
            if userid:
                query = query.filter(Conversation.userid == userid)
            conversations = query.order_by(
                func.coalesce(Conversation.updated_at, Conversation.created_at).desc(),
                Conversation.id.desc(),
            ).all()
            out = []
            for conv in conversations:
                first = (
                    session.query(Message)
                    .filter_by(conversation_id=conv.id, role="user")
                    .order_by(Message.id)
                    .first()
                )
                stamp = conv.updated_at or conv.created_at
                out.append(
                    {
                        "sessionId": conv.session_id,
                        "preview": (first.content or "")[:30] if first else "",
                        "updatedAt": stamp.strftime("%Y-%m-%d %H:%M") if stamp else "",
                        "summarized": (conv.summary_upto_msg_id or 0) > 0,
                    }
                )
            return out

    def load_conversation_messages(self, session_id: str, userid: str | None = None) -> list[dict] | None:
        """只读回载:只返回 user/assistant;会话不存在或 userId 不匹配返回 None(→404)。"""
        with self._factory() as session:
            conv = self._conversation(session, session_id)
            if conv is None:
                return None
            if userid and conv.userid and conv.userid != userid:
                return None
            rows = (
                session.query(Message)
                .filter(Message.conversation_id == conv.id, Message.role.in_(("user", "assistant")))
                .order_by(Message.id)
                .all()
            )
            return [
                {
                    "role": m.role,
                    "content": m.content,
                    "createdAt": m.created_at.strftime("%Y-%m-%d %H:%M") if m.created_at else "",
                }
                for m in rows
            ]
