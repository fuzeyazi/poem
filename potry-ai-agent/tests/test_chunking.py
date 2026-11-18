import pytest

from chunking import (
    chunk_poem,
    chunk_poet,
    chunk_policy_doc,
    chunk_section,
    overlap_prefix,
    recursive_split,
    split_markdown_sections,
    split_sentences,
)


def test_split_sentences_keeps_punctuation():
    assert split_sentences("床前明月光,疑是地上霜。举头望明月。") == [
        "床前明月光,疑是地上霜。",
        "举头望明月。",
    ]


def test_recursive_split_never_exceeds_size():
    text = "。".join(f"句{i}" for i in range(30)) + "。"
    pieces = recursive_split(text, 20)
    assert all(len(p) <= 20 for p in pieces)
    assert "".join(pieces) == text


def test_recursive_split_hard_splits_overlong_sentence():
    text = "甲" * 50  # 无句末标点,单句超长
    pieces = recursive_split(text, 20)
    assert len(pieces) == 3
    assert all(len(p) <= 20 for p in pieces)
    assert "".join(pieces) == text


def test_recursive_split_returns_empty_for_empty_text():
    assert recursive_split("", 20) == []


def test_overlap_prefix_trims_to_nearest_sentence_end():
    prev = "第一句。第二句。第三句。"
    assert overlap_prefix(prev, 8) == "第三句。"  # 丢掉被截断的半句


def test_overlap_prefix_returns_empty_when_no_sentence_end():
    assert overlap_prefix("甲乙丙丁戊", 3) == ""


def test_overlap_prefix_returns_empty_when_prev_shorter_than_overlap():
    assert overlap_prefix("短。", 6) == ""


def test_chunk_section_keeps_overlap_truncated_to_sentence():
    body = "第一句。第二句。第三句。第四句。"
    chunks = chunk_section("静夜思|唐|李白|五言", "原文", body, chunk_size=12, overlap=6)
    assert len(chunks) == 2
    assert chunks[0]["seq"] == 0 and chunks[1]["seq"] == 1
    assert chunks[0]["chunk_text"] == "静夜思|唐|李白|五言\n原文\n第一句。第二句。第三句。"
    assert chunks[0]["raw_text"] == "第一句。第二句。第三句。"
    # 第二块带重叠:重叠从完整句子起(裁掉了被截断的半句),不是半截话
    assert chunks[1]["chunk_text"] == "静夜思|唐|李白|五言\n原文\n第三句。第四句。"
    assert chunks[1]["raw_text"] == "第四句。"


def test_chunk_section_returns_empty_for_blank_body():
    assert chunk_section("p", "原文", None, 400, 60) == []
    assert chunk_section("p", "原文", "   ", 400, 60) == []


def test_chunk_poem_covers_all_present_sections():
    poem = {
        "title": "静夜思", "dynasty": "唐", "writer": "李白", "type": "五言绝句",
        "content": "床前明月光,疑是地上霜。举头望明月,低头思故乡。",
        "translation": "明亮的月光洒在窗户纸上。",
        "shangxi": None, "remark": None,
    }
    chunks = chunk_poem(poem, chunk_size=400, overlap=60)
    assert {c["section"] for c in chunks} == {"原文", "译文"}
    assert all("静夜思|唐|李白|五言绝句" in c["chunk_text"] for c in chunks)
    assert all(c["chunk_text"].startswith("静夜思|唐|李白|五言绝句\n") for c in chunks)


def test_chunk_poet_uses_poet_meta_prefix():
    writer = {"name": "李白", "simpleIntro": "盛唐诗仙。", "detailIntro": "字太白,号青莲居士。"}
    chunks = chunk_poet(writer, chunk_size=400, overlap=60)
    assert {c["section"] for c in chunks} == {"简简介", "详简介"}
    assert all(c["chunk_text"].startswith("李白||李白|诗人\n") for c in chunks)


def test_split_sentences_preserves_whitespace_and_newlines():
    text = "第一句。\n第二句。  第三句。"
    assert "".join(split_sentences(text)) == text  # 不裁剪空白


def test_recursive_split_preserves_newlines_and_whitespace():
    text = "第一段。\n第二段。  第三段。"
    pieces = recursive_split(text, 8)
    assert "".join(pieces) == text  # 换行/空格不丢(raw_text 是权威原文)
    assert all(len(p) <= 8 for p in pieces)


def test_recursive_split_breaks_at_newline_when_no_period():
    # 赏析这类无句末标点的多段文本:应在换行处切,而不是把整段硬切碎(换行留在上一块末尾)
    text = "甲" * 6 + "\n" + "乙" * 6
    pieces = recursive_split(text, 8)
    assert "".join(pieces) == text
    assert all(len(p) <= 8 for p in pieces)
    assert pieces[0].endswith("\n")


def test_chunk_section_raw_text_keeps_newlines():
    body = "第一段。\n第二段。"
    chunks = chunk_section("p", "赏析", body, chunk_size=400, overlap=60)
    assert len(chunks) == 1
    assert chunks[0]["raw_text"] == "第一段。\n第二段。"
    assert "\n" in chunks[0]["raw_text"]


def test_recursive_split_rejects_non_positive_chunk_size():
    for bad in (0, -1):
        with pytest.raises(ValueError, match="chunk_size"):
            recursive_split("正文。", bad)


def test_chunk_section_rejects_non_positive_chunk_size():
    with pytest.raises(ValueError, match="chunk_size"):
        chunk_section("p", "原文", "正文。", 0, 0)


def test_chunk_section_clamps_overlap_to_chunk_size():
    # overlap >= chunk_size 属误配:应收敛成有效重叠,而不是静默不重叠
    body = "第一句。第二句。第三句。第四句。第五句。"
    chunks = chunk_section("p", "原文", body, chunk_size=12, overlap=100)
    assert len(chunks) >= 2
    head = chunks[1]["chunk_text"].split("\n原文\n", 1)[1]
    assert head != chunks[1]["raw_text"]  # 确有重叠前缀(收敛生效)


def test_seq_is_per_section_starting_at_zero():
    poem = {"title": "静夜思", "dynasty": "唐", "writer": "李白", "type": "五言",
            "content": "床前明月光。举头望明月。", "translation": "月光洒在床前。", "shangxi": None, "remark": None}
    chunks = chunk_poem(poem, chunk_size=8, overlap=4)
    by_section: dict[str, list[int]] = {}
    for c in chunks:
        by_section.setdefault(c["section"], []).append(c["seq"])
    assert all(seqs == list(range(len(seqs))) for seqs in by_section.values())
    assert by_section["原文"][0] == 0 and by_section["译文"][0] == 0  # seq 是子节内序号


def test_split_markdown_sections_by_h2_headings():
    md = "# 大标题\n\n前言文字\n\n## 甲节\n甲正文。\n\n## 乙节\n乙正文。\n"
    assert split_markdown_sections(md) == [("甲节", "甲正文。"), ("乙节", "乙正文。")]


def test_split_markdown_sections_falls_back_to_whole_doc():
    assert split_markdown_sections("没有二级标题的正文。") == [("正文", "没有二级标题的正文。")]


def test_split_markdown_sections_empty_doc():
    assert split_markdown_sections("") == []


def test_split_markdown_sections_truncates_long_heading_to_column_width():
    md = "## " + "长" * 40 + "\n正文。"
    (name, body) = split_markdown_sections(md)[0]
    assert len(name) == 32 and body == "正文。"


def test_chunk_policy_doc_uses_rule_meta_prefix_and_sections():
    doc = {
        "title": "格律·词牌规则",
        "markdown": "## 押韵规则\n近体诗偶句押韵。\n## 对仗规则\n律诗颔联颈联对仗。\n",
    }
    chunks = chunk_policy_doc(doc, chunk_size=400, overlap=60)
    assert {c["section"] for c in chunks} == {"押韵规则", "对仗规则"}
    assert all(c["chunk_text"].startswith("格律·词牌规则|||规则\n") for c in chunks)
    assert chunks[0]["raw_text"] == "近体诗偶句押韵。"


def test_chunk_policy_doc_returns_empty_for_blank_markdown():
    assert chunk_policy_doc({"title": "x", "markdown": "   "}, 400, 60) == []
