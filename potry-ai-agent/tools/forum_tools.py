"""Ch09 打通(三):文坛帖子草稿工具。

设计:LLM 经 function calling 把整篇草稿作为工具参数生成(title+content+tag);
工具只做**长度与内容校验**并回显草稿,由 workflow 把草稿放进 state,
经 SSE action 帧(`forum_draft`)交给前端渲染。**发布由前端调 Java**
/user/luntan/fabutiezi(写操作归 Java:敏感词/事务/审计),agent 不写 poem_blog。
"""
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class DraftForumPostInput(BaseModel):
    title: str = Field(min_length=4, max_length=50, description="帖子标题,4-50字")
    content: str = Field(min_length=30, max_length=2000, description="帖子正文,30-2000字,口语自然、适合社区")
    tag: str = Field(default="", max_length=20, description="可选标签,如'诗友分享'/'求点评'")


@tool("draft_forum_post", args_schema=DraftForumPostInput)
def draft_forum_post(title: str, content: str, tag: str = "") -> dict:
    """为用户起草一篇文坛(论坛)帖子。**仅在用户明确想要发帖/分享/求点评时调用**,
    且必须基于本轮对话已聊过的诗词内容来写,不得虚构用户没提过的经历。
    正文由你(模型)撰写,作为参数整体传入;用户确认发布由前端完成。

    Args:
        title: 帖子标题,4-50字
        content: 帖子正文,30-2000字
        tag: 可选标签,如"诗友分享"
    """
    title, content, tag = title.strip(), content.strip(), (tag or "").strip()
    if not any("\u4e00" <= ch <= "\u9fff" for ch in title + content):
        return {"ok": False, "error": "草稿应为中文内容"}
    return {
        "ok": True,
        "found": True,
        "draft": {"title": title, "content": content, "tag": tag},
    }
