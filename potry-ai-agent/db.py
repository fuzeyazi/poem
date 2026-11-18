"""SQLAlchemy 引擎与诗词表映射(只读,列名与 poemmax.sql 的 poem 库一致)。"""
from sqlalchemy import String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class PoetryBase(DeclarativeBase):
    pass


class Potry(PoetryBase):
    __tablename__ = "potry"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(String(255))
    dynasty: Mapped[str | None] = mapped_column(String(10))
    writer: Mapped[str | None] = mapped_column(String(100))
    type: Mapped[str | None] = mapped_column("type", String(100))
    content: Mapped[str | None] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(Text)
    shangxi: Mapped[str | None] = mapped_column(Text)
    audioUrl: Mapped[str | None] = mapped_column("audioUrl", String(255))
    translation: Mapped[str | None] = mapped_column(Text)


class Writer(PoetryBase):
    __tablename__ = "writer"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(25))
    headImageUrl: Mapped[str | None] = mapped_column("headImageUrl", String(255))
    simpleIntro: Mapped[str | None] = mapped_column("simpleIntro", Text)
    detailIntro: Mapped[str | None] = mapped_column("detailIntro", Text)


class Userbook(PoetryBase):
    """诗集(Java 侧);Ch09 get_study_plan 只读。"""

    __tablename__ = "userbook"

    book_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column("user_id")
    book_name: Mapped[str | None] = mapped_column("book_name", String(255))
    sum: Mapped[int | None] = mapped_column("sum")


class UserbookPoem(PoetryBase):
    """诗集内每首诗的复习进度(后端 SRS 核心:nextReviewDate 按 1/3/7/14/30 推进,5轮毕业)。"""

    __tablename__ = "userbookpoem"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column("book_id")
    poem_id: Mapped[int] = mapped_column("poem_id")
    reviewCount: Mapped[int | None] = mapped_column("reviewCount")
    lastReviewDate: Mapped[str | None] = mapped_column("lastReviewDate", String(32))
    nextReviewDate: Mapped[str | None] = mapped_column("nextReviewDate", String(32))


class UserLearningSchedule(PoetryBase):
    """学习计划(每日学习任务);Ch09 get_study_plan 只读。"""

    __tablename__ = "userlearningschedule"

    user_id: Mapped[int] = mapped_column("user_id", primary_key=True)
    poem_id: Mapped[int] = mapped_column("poem_id", primary_key=True)
    scheduled_date: Mapped[str | None] = mapped_column("scheduled_date", String(32))
    is_learned: Mapped[int | None] = mapped_column("is_learned")


class UserCollectionPoem(PoetryBase):
    """Java 侧用户收藏表(只读;Ch09 打通:个性化伴学数据源)。"""

    __tablename__ = "usercollectionpoem"

    id: Mapped[int] = mapped_column(primary_key=True)
    userid: Mapped[int] = mapped_column("userid")
    poemid: Mapped[int] = mapped_column("poemid")
    collecter_at: Mapped[str | None] = mapped_column("collecter_at", String(32))


_engine = None
_session_factory = None


def get_engine(url: str):
    """惰性创建 engine:首调建、后续复用(MySQL 挂了只在查询时失败)。"""
    global _engine
    if _engine is None:
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def get_session_factory(url: str):
    """惰性创建 sessionmaker:engine 统一由 get_engine 创建,避免重复建 engine。"""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(url))
    return _session_factory


def new_session(url: str) -> Session:
    return get_session_factory(url)()


def reset_engine() -> None:
    """复位 engine/sessionmaker 单例。测试换库、或运行中切换 MYSQL_URL 时用。"""
    global _engine, _session_factory
    _engine = None
    _session_factory = None
