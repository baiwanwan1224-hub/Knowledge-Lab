"""RAG retrieval tests — embedding mocked, no API calls."""
import numpy as np
import pytest

from server import rag_index


# ── Deterministic fake embeddings ──
# apple chunk -> [1,0,0], orange chunk -> [0,1,0], banana chunk -> [0,0,1]
_FAKE_VECTORS = {
    'apple': np.array([1.0, 0.0, 0.0]),
    'orange': np.array([0.0, 1.0, 0.0]),
    'banana': np.array([0.0, 0.0, 1.0]),
    # query: "一种红色的脆甜水果" ~ apple, slightly fuzzy
    'query_red': np.array([0.9, 0.1, 0.0]),
    'query_orange': np.array([0.1, 0.9, 0.0]),
    'query_unknown': np.array([1.0, 1.0, 1.0]) / np.sqrt(3),
}


def _fake_embed(texts):
    """Return deterministic vectors keyed on recognizable substrings."""
    out = []
    total = 0
    for t in texts:
        if '苹果' in t or 'apple' in t:
            vec = _FAKE_VECTORS['apple']
        elif '橙子' in t or 'orange' in t:
            vec = _FAKE_VECTORS['orange']
        elif '香蕉' in t or 'banana' in t:
            vec = _FAKE_VECTORS['banana']
        elif '红色的脆甜水果' in t:
            vec = _FAKE_VECTORS['query_red']
        elif '橙色的水果' in t:
            vec = _FAKE_VECTORS['query_orange']
        else:
            vec = _FAKE_VECTORS['query_unknown']
        out.append(vec.tolist())
        total += 1
    return out, {'prompt_tokens': total}


def _make_index():
    """Hand-crafted index: 3 chunks with known semantic tags."""
    chunks = [
        {
            'chunk_id': 'c_apple', 'note_path': '苹果.md', 'title': '苹果',
            'heading_path': ['水果'], 'text': '苹果是一种红色的脆甜水果。',
        },
        {
            'chunk_id': 'c_orange', 'note_path': '橙子.md', 'title': '橙子',
            'heading_path': ['水果'], 'text': '橙子是一种橙色的酸甜水果。',
        },
        {
            'chunk_id': 'c_banana', 'note_path': '香蕉.md', 'title': '香蕉',
            'heading_path': ['水果'], 'text': '香蕉是黄色的软糯水果。',
        },
    ]
    embeddings = {
        'c_apple': _FAKE_VECTORS['apple'].tolist(),
        'c_orange': _FAKE_VECTORS['orange'].tolist(),
        'c_banana': _FAKE_VECTORS['banana'].tolist(),
    }
    return {'chunks': chunks, 'embeddings': embeddings}


@pytest.fixture()
def fake_index(monkeypatch):
    monkeypatch.setattr(rag_index, 'load_index', _make_index)
    monkeypatch.setattr(rag_index, 'embed_texts', _fake_embed)
    return rag_index


def test_vector_retrieval_semantic_rank(fake_index):
    """'红色的脆甜水果' should surface the apple chunk first (semantic match)."""
    results = fake_index.retrieve('红色的脆甜水果', top_k=3, retriever='vector')
    assert results, 'should return results'
    assert results[0]['chunk_id'] == 'c_apple'
    assert results[0]['source'] == 'vector'


def test_vector_retrieval_different_query(fake_index):
    results = fake_index.retrieve('橙色的水果', top_k=3, retriever='vector')
    assert results[0]['chunk_id'] == 'c_orange'


def test_keyword_baseline(fake_index):
    """'苹果' keyword query hits the apple chunk by substring, no embedding semantics."""
    results = fake_index.retrieve('苹果', top_k=3, retriever='keyword')
    assert results[0]['chunk_id'] == 'c_apple'
    assert results[0]['source'] == 'keyword'


def test_hybrid_merges_and_dedups(fake_index):
    results = fake_index.retrieve('红色的脆甜水果', top_k=5, retriever='hybrid')
    ids = [r['chunk_id'] for r in results]
    assert len(ids) == len(set(ids)), 'no duplicate chunk_ids in hybrid'
    # Keyword hit (text contains '水果') present, semantic hit present.
    assert 'c_apple' in ids


def test_top_k_respected(fake_index):
    results = fake_index.retrieve('红色的脆甜水果', top_k=1, retriever='vector')
    assert len(results) == 1


# ── 中文 bigram keyword（8/5：q.split() 对中文退化为整句单 token，bigram 提供近似分词）──
def test_keyword_score_chinese_bigram():
    chunk = {'text': '苹果是一种红色的脆甜水果。', 'title': '苹果', 'heading_path': ['水果']}
    # 整句命中 → score >= 1.0（整句 1.0 + bigram 加成）
    s = rag_index._keyword_score('红色的脆甜水果', chunk)
    assert s >= 1.0
    # 非整句匹配但含命中 bigram（'红色'）→ 仍能得正分（修复前为 0）
    s2 = rag_index._keyword_score('红色水果知识', chunk)
    assert s2 > 0
    # 完全无关 → 0
    assert rag_index._keyword_score('汽车引擎', chunk) == 0
