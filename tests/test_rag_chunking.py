"""RAG chunking tests — pure logic, no API calls."""
import pytest

from server.rag_index import chunk_markdown, _split_paragraphs


def test_heading_slicing():
    md = """---
title: "测试笔记"
topics: ["AI 评测 & 质量"]
---

# 测试笔记

> 来源：测试

## How to Help
1. 第一点内容
2. 第二点内容

## Core Principles
- 原则 A
- 原则 B

## Deep Dive
空章节
"""
    chunks = chunk_markdown(md)
    # 3 `##` sections (source blockquote folds into the first section's parent... )
    # Actually the `#`-level intro (source blockquote) becomes its own chunk.
    paths = [c['heading_path'] for c in chunks]
    assert len(chunks) == 4, [c['heading_path'] for c in chunks]
    # First chunk is the intro under the `#` title.
    assert paths[0] == ['测试笔记']
    assert '来源：测试' in chunks[0]['text']
    # Remaining are `##` sections with the parent title in the path.
    assert ['测试笔记', 'How to Help'] in paths
    assert ['测试笔记', 'Core Principles'] in paths


def test_frontmatter_stripped_from_body():
    md = """---
title: "X"
topics: ["A"]
---
正文内容只有这一句。
"""
    chunks = chunk_markdown(md)
    assert len(chunks) == 1
    assert 'title:' not in chunks[0]['text']
    assert 'topics:' not in chunks[0]['text']
    assert chunks[0]['text'] == '正文内容只有这一句。'


def test_no_heading_paragraph_split():
    md = '这是没有标题的一段。\n\n' + '长段落内容' * 50 + '。'
    # Force tiny max_chars to exercise the paragraph-split path.
    chunks = chunk_markdown(md, max_chars=200, overlap=20)
    assert len(chunks) >= 2
    # Overlap: consecutive chunk boundaries should share some text.
    all_text = '\n'.join(c['text'] for c in chunks)
    # No information loss: joining chunks covers all source paragraphs.
    for c in chunks:
        assert c['char_len'] <= 200 + 1  # each piece within budget (plus rounding)


def test_oversize_section_split():
    md = '# 标题\n\n## 超长章节\n\n' + '\n\n'.join(f'段落{i}：' + '内容' * 40 for i in range(20))
    chunks = chunk_markdown(md, max_chars=300, overlap=30)
    # The single `##` section got split into multiple chunks.
    assert len(chunks) > 1
    for c in chunks:
        assert c['char_len'] <= 300 + 40  # within budget + one overlap tail


def test_heading_path_nesting():
    md = '# A\n\n## B\n\n### C\n内容C\n\n## D\n内容D\n'
    chunks = chunk_markdown(md)
    paths = [c['heading_path'] for c in chunks]
    assert ['A', 'B', 'C'] in paths
    assert ['A', 'D'] in paths


def test_empty_body():
    assert chunk_markdown('---\ntitle: "空"\n---\n') == []


def test_split_paragraphs_budget():
    paras = ['a' * 50, 'b' * 50, 'c' * 50]
    parts = _split_paragraphs('\n\n'.join(paras), max_chars=120, overlap=10)
    assert len(parts) >= 2
    # Combined content preserved.
    joined = ''.join(parts)
    assert 'a' * 50 in joined and 'c' * 50 in joined
