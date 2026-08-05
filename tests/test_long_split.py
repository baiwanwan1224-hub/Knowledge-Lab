"""Long-text splitting tests — PDF/markdown chunking (8/5 fix).

原实现只按 '\n\n' 空行分段，而 PDF 提取的文本只有 '\n' 换行（无空行），
导致长 PDF 导入后永不拆分（8/5 诊断：150K 字符提取完整、触发条件满足、仍只拆 1 篇）。
修复：段落优先 + 单段超预算按换行边界硬切兜底。
"""
from server.blueprints.notes import _split_long_text, _chunk_by_newline

SPLIT = 50000


def test_short_text_single_part():
    assert _split_long_text('短文', split_at=SPLIT) == ['短文']


def test_pdf_style_no_blank_lines_splits():
    """模拟 PDF 提取：只有 \n 换行、无 \n\n 空行 → 必须拆成多篇（根因回归）。"""
    lines = [f'第{i}段内容，这是一行足够长的测试文本用于触发拆分阈值' for i in range(4000)]
    text = '\n'.join(lines)
    assert len(text) > SPLIT  # 确保超阈值
    parts = _split_long_text(text, split_at=SPLIT)
    assert len(parts) > 1
    assert all(len(p) <= SPLIT for p in parts)
    joined = ''.join(parts)
    for line in lines:
        assert line in joined  # 不丢内容


def test_blank_line_paragraphs_chunked():
    """有 \n\n 段落但单段超预算 → 每段内部按换行边界细切。"""
    paras = [f'段落{i}' * 20000 for i in range(3)]  # 每段 60000 字符 > SPLIT
    text = '\n\n'.join(paras)
    parts = _split_long_text(text, split_at=SPLIT)
    assert len(parts) > 1
    assert all(len(p) <= SPLIT for p in parts)


def test_giant_single_paragraph_hard_chunked():
    """超长单段（无任何换行）→ 硬切兜底，内容不丢。"""
    text = 'A' * 130000
    parts = _split_long_text(text, split_at=SPLIT)
    assert len(parts) >= 2
    assert all(len(p) <= SPLIT for p in parts)
    assert ''.join(parts) == text


def test_chunk_by_newline_prefers_newline():
    text = 'a' * 100 + '\n' + 'b' * 100
    chunks = _chunk_by_newline(text, split_at=50)
    assert len(chunks) > 1
    assert all(len(c) <= 51 for c in chunks)
    assert ''.join(chunks) == text  # 不丢字符，换行保留在块尾
