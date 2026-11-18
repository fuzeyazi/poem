"""Ch09 文坛草稿工具:长度/内容校验契约。"""
from tools.forum_tools import draft_forum_post


def test_valid_draft_echoed():
    r = draft_forum_post.invoke({"title": "与月对饮", "content": "今晚重读《静夜思》,忽然明白了什么叫月光如水。李白把乡愁写得这么轻,又这么重,分享给各位诗友。", "tag": "诗友分享"})
    assert r["ok"] and r["found"]
    assert r["draft"]["title"] == "与月对饮"
    assert r["draft"]["tag"] == "诗友分享"


def test_title_too_short_rejected_by_schema():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        draft_forum_post.invoke({"title": "短", "content": "x" * 40})


def test_non_chinese_rejected():
    r = draft_forum_post.invoke({"title": "hello world 1234", "content": "just some english text without chinese chars"})
    assert r["ok"] is False
