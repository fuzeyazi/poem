"""文档切分:按预置子节(原文/译文/赏析/注释 等)结构切分 → 超长内容切块 → 块间重叠裁到最近句号(不留半截话)。

诗词域用法:potry 一行 = 一篇文档,诗题是文档标题,原文/译文/赏析/注释 是子节;
writer 一行 = 一篇诗人文档,简简介/详简介 是子节。大表格按行切属本章非目标(YAGNI)。
"""

_SENTENCE_ENDS = "。!?;…"  # 句末标点:用于切句与重叠裁剪(裁到最近句号)
_SPLIT_BOUNDS = _SENTENCE_ENDS + "\n"  # 递归切边界:句末标点或换行
_HEADING_PREFIX = "## "
_MAX_SECTION_NAME = 32  # knowledge_chunks.section 是 String(32),超出会写不进去

# 诗词文档的子节(展示名 → potry 列名)
_POEM_SECTIONS = (("原文", "content"), ("译文", "translation"), ("赏析", "shangxi"), ("注释", "remark"))
# 诗人文档的子节(展示名 → writer 列名)
_POET_SECTIONS = (("简简介", "simpleIntro"), ("详简介", "detailIntro"))


def split_sentences(text: str, bounds: str = _SENTENCE_ENDS) -> list[str]:
    """按边界字符切句,边界字符留在句尾。**不裁剪空白**,保证 '拼接 == 原文'
    (多段赏析的换行/空格不丢,raw_text 才能当权威原文)。"""
    sentences: list[str] = []
    buf: list[str] = []
    for ch in text:
        buf.append(ch)
        if ch in bounds:
            sentences.append("".join(buf))
            buf = []
    if buf:
        sentences.append("".join(buf))
    return sentences


def recursive_split(text: str, chunk_size: int) -> list[str]:
    """按句聚合到不超过 chunk_size 的块;单句本身超长时按 chunk_size 硬切。"""
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须为正整数")
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    pieces: list[str] = []
    buf = ""
    for sent in split_sentences(text, _SPLIT_BOUNDS):
        if len(sent) > chunk_size:
            if buf:
                pieces.append(buf)
                buf = ""
            for i in range(0, len(sent), chunk_size):
                pieces.append(sent[i : i + chunk_size])
            continue
        if len(buf) + len(sent) > chunk_size:
            if buf:
                pieces.append(buf)
            buf = sent
        else:
            buf += sent
    if buf:
        pieces.append(buf)
    return pieces


def overlap_prefix(prev_piece: str, overlap: int) -> str:
    """取上一块尾部 overlap 字做重叠;裁到重叠窗口内第一个句末标点之后,
    丢掉被截断的半句;窗口内没有句末标点则不留重叠(整段不裁)。
    窗口内句末标点恰在末位时返回空串(无法确定窗口起点是否半句,宁可不重叠)。"""
    if overlap <= 0 or len(prev_piece) <= overlap:
        return ""
    tail = prev_piece[-overlap:]
    for i, ch in enumerate(tail):
        if ch in _SENTENCE_ENDS:
            return tail[i + 1 :].strip()
    return ""


def chunk_section(meta_prefix: str, section: str, body: str | None, chunk_size: int, overlap: int) -> list[dict]:
    """切一个子节,返回 [{section, seq, chunk_text, raw_text}];空正文返回 []。
    seq 为「子节内序号」,同一文档的不同 section 各自从 0 起。"""
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须为正整数")
    overlap = max(0, min(overlap, chunk_size - 1))  # overlap >= chunk_size 属误配,收敛避免重叠静默失效
    body = (body or "").strip()
    if not body:
        return []
    pieces = recursive_split(body, chunk_size)
    out: list[dict] = []
    prev = ""
    for i, piece in enumerate(pieces):
        head = overlap_prefix(prev, overlap) + piece
        out.append(
            {
                "section": section,
                "seq": i,
                # 向量化用文本:metadata 前缀 + 子节名 + 正文(含重叠)
                "chunk_text": f"{meta_prefix}\n{section}\n{head}",
                # 权威原文:本块正文本身(不含重叠前缀)
                "raw_text": piece,
            }
        )
        prev = piece
    return out


def meta_prefix(title: str | None, dynasty: str | None, writer: str | None, type_: str | None) -> str:
    """metadata 前缀:title|dynasty|writer|type。"""
    return "|".join(x or "" for x in (title, dynasty, writer, type_))


def chunk_poem(poem: dict, chunk_size: int, overlap: int) -> list[dict]:
    """把一首诗词切成块。poem 需含 title/dynasty/writer/type/content/translation/shangxi/remark。
    返回列表按子节顺序拼接,每块的 seq 是该子节内的序号(不同 section 各自从 0 起)。"""
    prefix = meta_prefix(poem.get("title"), poem.get("dynasty"), poem.get("writer"), poem.get("type"))
    chunks: list[dict] = []
    for section, field in _POEM_SECTIONS:
        chunks.extend(chunk_section(prefix, section, poem.get(field), chunk_size, overlap))
    return chunks


def chunk_poet(writer: dict, chunk_size: int, overlap: int) -> list[dict]:
    """把一位诗人切成块。writer 需含 name/simpleIntro/detailIntro。
    返回列表按子节顺序拼接,每块的 seq 是该子节内的序号(不同 section 各自从 0 起)。"""
    name = writer.get("name")
    prefix = meta_prefix(name, "", name, "诗人")
    chunks: list[dict] = []
    for section, field in _POET_SECTIONS:
        chunks.extend(chunk_section(prefix, section, writer.get(field), chunk_size, overlap))
    return chunks


def split_markdown_sections(markdown: str) -> list[tuple[str, str]]:
    """按 markdown '## ' 二级标题切子节,返回 [(标题, 正文)]。

    首个 '## ' 之前的内容(文档头 / 一级标题)不参与切块,直接忽略;
    整篇没有 '## ' 时视作单个子节,标题记作「正文」;空文档返回 []。
    标题按 section 列宽截断(32 字)。
    """
    sections: list[tuple[str, list[str]]] = []
    current: list[str] | None = None
    for line in markdown.splitlines():
        if line.startswith(_HEADING_PREFIX):
            current = []
            sections.append((line[len(_HEADING_PREFIX):].strip() or "正文", current))
        elif current is not None:
            current.append(line)
    if not sections:
        body = (markdown or "").strip()
        return [("正文", body)] if body else []
    return [(name[:_MAX_SECTION_NAME], "\n".join(body).strip()) for name, body in sections]


def chunk_policy_doc(doc: dict, chunk_size: int, overlap: int) -> list[dict]:
    """把一篇规则文档切成块。doc 需含 title / markdown。

    按 '## ' 二级标题切子节后,逐子节复用通用 `chunk_section`(与诗词/诗人文档同一套
    切块、重叠、裁句逻辑),故块结构与 Ch03 语料完全一致。
    """
    prefix = meta_prefix(doc.get("title"), "", "", "规则")
    chunks: list[dict] = []
    for section, body in split_markdown_sections(doc.get("markdown") or ""):
        chunks.extend(chunk_section(prefix, section, body, chunk_size, overlap))
    return chunks
