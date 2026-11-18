"""知识库落库:knowledge_chunks(原文权威源)/ knowledge_staging(挖知识暂存)/ knowledge_mining_cursor(水位)。"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from storage import _ID_TYPE  # 复用主键类型(MySQL BIGINT / SQLite Integer 自增)


class KnowledgeBase(DeclarativeBase):
    pass


class KnowledgeChunk(KnowledgeBase):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", "section", "seq", name="uq_knowledge_chunk_key"),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(16), index=True)  # poem / poet / qa
    source_id: Mapped[int] = mapped_column(_ID_TYPE)
    chunk_text: Mapped[str] = mapped_column(Text)  # 向量化用(带 metadata 前缀)
    raw_text: Mapped[str] = mapped_column(Text)  # 权威原文
    title: Mapped[str | None] = mapped_column(String(255))
    writer: Mapped[str | None] = mapped_column(String(100))
    dynasty: Mapped[str | None] = mapped_column(String(32))
    section: Mapped[str] = mapped_column(String(32))
    seq: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), index=True, default="pending")  # pending / embedded
    vector_id: Mapped[int | None] = mapped_column(_ID_TYPE)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class KnowledgeStaging(KnowledgeBase):
    __tablename__ = "knowledge_staging"

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    tags: Mapped[str | None] = mapped_column(Text)
    source_session_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class KnowledgeMiningCursor(KnowledgeBase):
    """单行表:记已挖到的最大 messages.id,保证只挖一次、可续跑。"""

    __tablename__ = "knowledge_mining_cursor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_mined_message_id: Mapped[int] = mapped_column(_ID_TYPE, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class PendingQuestion(KnowledgeBase):
    """置信度不足的问题:证据不足的兜底问题在此暂存,供后续数据飞轮迭代取用。

    与知识库表同 Base,便于 main.py 的 create_all 一并建表(spec §9)。
    """

    __tablename__ = "pending_questions"

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str | None] = mapped_column(String(64))
    source_entry: Mapped[str | None] = mapped_column(String(32))
    retrieved_snapshot: Mapped[str | None] = mapped_column(Text)
    matched_review_id: Mapped[int | None] = mapped_column(_ID_TYPE)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ReviewQueue(KnowledgeBase):
    """待审队列:一行一个去重缺口。"""

    __tablename__ = "review_queue"

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    standard_question: Mapped[str] = mapped_column(Text)
    example_answer: Mapped[str] = mapped_column(Text)
    occurrences: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    approved_answer: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


def ensure_ch08_schema(engine) -> None:
    """给旧 pending_questions 补三列;新表由 create_all 建。幂等。"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "pending_questions" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("pending_questions")}
    columns = {
        "source_entry": "VARCHAR(32) NULL",
        "retrieved_snapshot": "TEXT NULL",
        "matched_review_id": "BIGINT NULL",
    }
    with engine.begin() as conn:
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE pending_questions ADD COLUMN {name} {ddl}"))


_FIELDS = ("source_type", "source_id", "section", "seq", "chunk_text", "raw_text", "title", "writer", "dynasty")


def _to_dict(row: KnowledgeChunk) -> dict:
    return {
        "id": row.id,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "section": row.section,
        "seq": row.seq,
        "chunk_text": row.chunk_text,
        "raw_text": row.raw_text,
        "title": row.title,
        "writer": row.writer,
        "dynasty": row.dynasty,
        "status": row.status,
        "vector_id": row.vector_id,
    }


class KnowledgeStorage:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._factory = session_factory

    # ---------- chunks ----------
    def upsert_chunks(self, chunks: list[dict]) -> int:
        """按唯一键 (source_type, source_id, section, seq) 幂等写入;返回处理条数。

        文本变化时把状态打回 pending(内容变了要重嵌);文本未变保持原状态。
        并发写者(如建库 CLI 与进程内定时挖知识)同时写同一唯一键时,
        SELECT 未命中再 INSERT 会撞唯一约束:此时回滚整批重试一次,
        第二轮 SELECT 会命中既有行改走 UPDATE,整体仍是幂等。
        """
        try:
            return self._upsert_chunks_once(chunks)
        except IntegrityError:
            print("[knowledge] 唯一键并发冲突,回滚整批后重试一次")
            return self._upsert_chunks_once(chunks)

    def _upsert_chunks_once(self, chunks: list[dict]) -> int:
        n = 0
        with self._factory() as session:
            for c in chunks:
                row = (
                    session.execute(
                        select(KnowledgeChunk).where(
                            KnowledgeChunk.source_type == c["source_type"],
                            KnowledgeChunk.source_id == c["source_id"],
                            KnowledgeChunk.section == c["section"],
                            KnowledgeChunk.seq == c["seq"],
                        )
                    )
                    .scalars()
                    .first()
                )
                if row is None:
                    session.add(KnowledgeChunk(**{k: c.get(k) for k in _FIELDS}, status="pending"))
                else:
                    if row.chunk_text != c.get("chunk_text"):
                        row.status = "pending"
                    for k in _FIELDS:
                        setattr(row, k, c.get(k))
                n += 1
            session.commit()
        return n

    def list_pending(self, limit: int | None = None, source_type: str | None = None) -> list[dict]:
        stmt = select(KnowledgeChunk).where(KnowledgeChunk.status == "pending").order_by(KnowledgeChunk.id)
        if source_type:
            stmt = stmt.where(KnowledgeChunk.source_type == source_type)
        if limit is not None:
            stmt = stmt.limit(limit)
        with self._factory() as session:
            return [_to_dict(r) for r in session.execute(stmt).scalars()]

    def list_chunks(self, source_type: str | None = None) -> list[dict]:
        stmt = select(KnowledgeChunk).order_by(KnowledgeChunk.id)
        if source_type:
            stmt = stmt.where(KnowledgeChunk.source_type == source_type)
        with self._factory() as session:
            return [_to_dict(r) for r in session.execute(stmt).scalars()]

    def get_chunk(self, chunk_id: int) -> dict | None:
        with self._factory() as session:
            row = session.get(KnowledgeChunk, chunk_id)
            return _to_dict(row) if row else None

    def delete_chunks(self, chunk_ids: list[int]) -> int:
        """删除chunk行(源库已删的孤儿清理),返回删除数。"""
        if not chunk_ids:
            return 0
        with self._factory() as session:
            rows = session.query(KnowledgeChunk).filter(KnowledgeChunk.id.in_(chunk_ids)).all()
            for r in rows:
                session.delete(r)
            session.commit()
            return len(rows)

    def mark_embedded(self, chunk_ids: list[int]) -> None:
        """标记已嵌入。前提约定:Milvus 主键就用 MySQL 的 chunk id,故 vector_id = chunk id。

        若将来 Milvus 主键策略变化(不再用 chunk id),此处的 vector_id 赋值需同步调整。
        """
        with self._factory() as session:
            for cid in chunk_ids:
                row = session.get(KnowledgeChunk, cid)
                if row is not None:
                    row.status = "embedded"
                    row.vector_id = cid
            session.commit()

    def count_by_status(self, source_type: str | None = None) -> dict:
        # SQL 聚合计数,避免把全表拉进 Python;只返回出现过的状态(不补 0)
        stmt = select(KnowledgeChunk.status, func.count()).group_by(KnowledgeChunk.status)
        if source_type:
            stmt = stmt.where(KnowledgeChunk.source_type == source_type)
        with self._factory() as session:
            return {status: cnt for status, cnt in session.execute(stmt).all()}

    # ---------- pending questions ----------
    def add_pending_question(
        self, question: str, session_id: str | None = None,
        *, source_entry: str = "retrieval_gate",
        retrieved_snapshot: str | None = None,
    ) -> int:
        """把证据不足的问题写入 pending_questions,返回新行 id。"""
        with self._factory() as session:
            row = PendingQuestion(
                question=question, session_id=session_id,
                source_entry=source_entry, retrieved_snapshot=retrieved_snapshot,
            )
            session.add(row)
            session.commit()
            return row.id

    def get_pending_question(self, pending_id: int) -> dict | None:
        with self._factory() as session:
            row = session.get(PendingQuestion, pending_id)
            return {
                "id": row.id, "question": row.question, "session_id": row.session_id,
                "source_entry": row.source_entry,
                "retrieved_snapshot": row.retrieved_snapshot,
                "matched_review_id": row.matched_review_id,
            } if row else None

    def list_unmatched_pending(self, limit: int = 50) -> list[dict]:
        with self._factory() as session:
            rows = session.execute(
                select(PendingQuestion)
                .where(PendingQuestion.matched_review_id.is_(None))
                .order_by(PendingQuestion.id).limit(limit)
            ).scalars()
            return [
                {"id": r.id, "question": r.question, "session_id": r.session_id,
                 "source_entry": r.source_entry,
                 "retrieved_snapshot": r.retrieved_snapshot}
                for r in rows
            ]

    def mark_pending_matched(self, pending_id: int, review_id: int) -> None:
        with self._factory() as session:
            row = session.get(PendingQuestion, pending_id)
            if row is not None:
                row.matched_review_id = review_id
            session.commit()

    def list_pending_by_review(self, review_id: int) -> list[dict]:
        with self._factory() as session:
            rows = session.execute(
                select(PendingQuestion)
                .where(PendingQuestion.matched_review_id == review_id)
                .order_by(PendingQuestion.id)
            ).scalars()
            return [
                {"id": r.id, "question": r.question, "session_id": r.session_id,
                 "source_entry": r.source_entry,
                 "retrieved_snapshot": r.retrieved_snapshot,
                 "created_at": r.created_at}
                for r in rows
            ]

    # ---------- review queue ----------
    def create_review(self, standard_question: str, example_answer: str) -> int:
        with self._factory() as session:
            row = ReviewQueue(
                standard_question=standard_question, example_answer=example_answer,
            )
            session.add(row)
            session.commit()
            return row.id

    def get_review(self, review_id: int) -> dict | None:
        with self._factory() as session:
            row = session.get(ReviewQueue, review_id)
            return {
                "id": row.id, "standard_question": row.standard_question,
                "example_answer": row.example_answer, "occurrences": row.occurrences,
                "status": row.status, "approved_answer": row.approved_answer,
                "created_at": row.created_at, "updated_at": row.updated_at,
            } if row else None

    def list_reviews(self, status: str | None = "pending",
                     limit: int = 50, offset: int = 0) -> list[dict]:
        with self._factory() as session:
            stmt = select(ReviewQueue).order_by(ReviewQueue.id.desc()).limit(limit).offset(offset)
            if status:
                stmt = stmt.where(ReviewQueue.status == status)
            return [
                {"id": r.id, "standard_question": r.standard_question,
                 "example_answer": r.example_answer, "occurrences": r.occurrences,
                 "status": r.status, "approved_answer": r.approved_answer,
                 "created_at": r.created_at}
                for r in session.execute(stmt).scalars()
            ]

    def increment_review_occurrences(self, review_id: int) -> None:
        with self._factory() as session:
            row = session.get(ReviewQueue, review_id)
            if row is not None:
                row.occurrences = (row.occurrences or 0) + 1
            session.commit()

    def update_review_status(
        self, review_id: int, status: str,
        *, approved_answer: str | None = None,
        standard_question: str | None = None,
    ) -> None:
        with self._factory() as session:
            row = session.get(ReviewQueue, review_id)
            if row is None:
                return
            row.status = status
            if approved_answer is not None:
                row.approved_answer = approved_answer
            if standard_question is not None:
                row.standard_question = standard_question
            session.commit()

    def get_chunk_id(
        self, source_type: str, source_id, section: str, seq: int,
    ) -> int | None:
        with self._factory() as session:
            row = session.execute(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.source_type == source_type,
                    KnowledgeChunk.source_id == source_id,
                    KnowledgeChunk.section == section,
                    KnowledgeChunk.seq == seq,
                )
            ).scalar_one_or_none()
            return row.id if row else None

    # ---------- staging / cursor ----------
    def add_staging(self, rows: list[dict]) -> int:
        with self._factory() as session:
            for r in rows:
                session.add(
                    KnowledgeStaging(
                        question=r["question"],
                        answer=r["answer"],
                        tags=r.get("tags"),
                        source_session_id=r.get("source_session_id"),
                    )
                )
            session.commit()
        return len(rows)

    def list_staging(self) -> list[dict]:
        with self._factory() as session:
            return [
                {
                    "id": r.id,
                    "question": r.question,
                    "answer": r.answer,
                    "tags": r.tags,
                    "source_session_id": r.source_session_id,
                }
                for r in session.execute(select(KnowledgeStaging).order_by(KnowledgeStaging.id)).scalars()
            ]

    def clear_staging(self) -> None:
        with self._factory() as session:
            session.execute(delete(KnowledgeStaging))
            session.commit()

    def get_cursor(self) -> int:
        # 本表恒为单行 id=1,无行即视作未挖过(返回 0)
        with self._factory() as session:
            row = session.get(KnowledgeMiningCursor, 1)
            return row.last_mined_message_id if row else 0

    def set_cursor(self, message_id: int) -> None:
        # 本表恒为单行 id=1:无行则插入,有行则原地更新
        with self._factory() as session:
            row = session.get(KnowledgeMiningCursor, 1)
            if row is None:
                session.add(KnowledgeMiningCursor(id=1, last_mined_message_id=message_id))
            else:
                row.last_mined_message_id = message_id
            session.commit()
