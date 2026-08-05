"""Memory core tests — window logic pure, LLM calls mocked."""
import json
import pytest

from server import memory_core
from server.memory_core import (
    MemoryStore, compress_long, faithfulness_check,
    short_memory_window, format_memory_injection, update_memory,
    _build_assertions, _truncate_source,
)


HISTORY = [
    {'role': 'user', 'content': '你好'},
    {'role': 'assistant', 'content': '你好，有什么可以帮你？'},
    {'role': 'user', 'content': '我要搭一个 RAG 学习平台'},
    {'role': 'assistant', 'content': '建议先做数据清洗再建索引'},
    {'role': 'user', 'content': '清洗完了，准确度从 0.27 提到 0.91'},
]


# ── 短记忆窗口 ──
def test_short_window_keeps_recent_k():
    w = short_memory_window(HISTORY, recent_k=2)
    assert len(w['recent']) == 2
    assert w['recent'][-1]['content'] == '清洗完了，准确度从 0.27 提到 0.91'
    assert w['older_summarized'] is True
    assert w['older_count'] == 3


def test_short_window_no_older():
    w = short_memory_window(HISTORY[:2], recent_k=2)
    assert w['older_summarized'] is False
    assert w['older_count'] == 0


def test_short_window_token_budget_trims():
    w = short_memory_window(HISTORY, recent_k=4, token_budget=15)
    # Must drop old turns to stay under budget.
    assert w['tokens'] <= 15
    assert len(w['recent']) < 4


# ── 长记忆压缩（mock LLM）──
def test_compress_long_with_mock(monkeypatch):
    def fake_llm(system, user):
        return json.dumps({
            'summary': '用户搭建RAG平台，完成数据清洗。',
            'entities': ['RAG平台', '数据清洗'],
            'decisions': ['先清洗再建索引'],
            'open_questions': [],
        }, ensure_ascii=False)
    mem = compress_long(HISTORY, llm_call=fake_llm, session_id='s1', store=MemoryStore('/tmp/_mc_test.json'))
    assert mem['summary'] == '用户搭建RAG平台，完成数据清洗。'
    assert 'RAG平台' in mem['entities']
    assert mem['source_hash']  # 溯源 hash 必在
    assert mem['ts']


def test_compress_long_rolls_prev_memory():
    prev = {'summary': '旧进展', 'decisions': ['旧决定']}
    called = {}
    def fake_llm(system, user):
        called['user'] = user
        return json.dumps({'summary': '新进展', 'entities': [], 'decisions': [], 'open_questions': []})
    compress_long(HISTORY, prev_memory=prev, llm_call=fake_llm)
    assert '旧进展' in called['user']  # 已有记忆并入新压缩


def test_compress_long_empty_raises():
    with pytest.raises(ValueError):
        compress_long([], llm_call=lambda s, u: '{}')


# ── 断言构建 ──
def test_build_assertions_sentence_split():
    mem = {
        'summary': '用户搭建平台。完成数据清洗。',
        'entities': ['RAG', '清洗'],
        'decisions': ['先清洗'],
        'open_questions': [],
    }
    a = _build_assertions(mem)
    # summary 两句 → 2 条 + entities 2 + decision 1 = 5
    assert len(a) == 5
    assert any('搭建平台' in x for x in a)
    assert any('完成数据清洗' in x for x in a)


# ── 原文截断（8/5 修复：头尾保留，防关键事实被尾截断误判）──
def test_truncate_source_keeps_head_and_tail():
    src = 'A' * 10000
    out = _truncate_source(src, max_chars=8000)
    assert len(out) <= 8000
    assert out.startswith('AAAA')  # 头部保留
    assert out.endswith('AAAA')    # 尾部保留
    assert '中间省略' in out


def test_truncate_source_short_passthrough():
    src = 'short source'
    assert _truncate_source(src, max_chars=8000) == src


def test_faithfulness_source_keeps_head_fact():
    """长对话 + 关键事实在开头 → 传入 LLM 的 prompt 必须含开头内容。"""
    turns = ['user: 用户决定采用语义检索方案']
    turns += [f'user: 填充第{i}轮：讨论天气午餐出行计划购物清单周末安排读书感想电影评价运动健身' for i in range(250)]
    source = '\n'.join(turns)
    assert len(source) > 8000  # 确保超截断窗口

    captured = {}
    def fake_llm(system, user):
        captured['user'] = user
        return json.dumps({'assertions': [{'text': 'a', 'supported': True, 'reason': 'ok'}], 'overall_pass': True})
    mem = {'summary': '用户决定采用语义检索方案。', 'entities': [], 'decisions': [], 'open_questions': []}
    faithfulness_check(mem, source, llm_call=fake_llm)
    assert '用户决定采用语义检索方案' in captured['user']  # 开头关键事实未被截掉


# ── 忠实度门禁 ──
def test_faithfulness_passed(monkeypatch):
    def fake_llm(system, user):
        return json.dumps({'assertions': [
            {'text': 'a', 'supported': True, 'reason': 'ok'},
            {'text': 'b', 'supported': True, 'reason': 'ok'},
        ], 'overall_pass': True})
    mem = {'summary': '用户搭建平台。', 'entities': ['RAG'], 'decisions': [], 'open_questions': []}
    r = faithfulness_check(mem, '原文', llm_call=fake_llm)
    assert r['passed'] is True
    assert r['score'] == 1.0


def test_faithfulness_rejected(monkeypatch):
    def fake_llm(system, user):
        return json.dumps({'assertions': [
            {'text': 'a', 'supported': True, 'reason': 'ok'},
            {'text': '编造的假事实', 'supported': False, 'reason': '原文没有'},
        ], 'overall_pass': False})
    mem = {'summary': '用户搭建平台。', 'entities': [], 'decisions': [], 'open_questions': []}
    r = faithfulness_check(mem, '原文', llm_call=fake_llm)
    assert r['passed'] is False
    assert r['score'] == 0.5
    assert len(r['issues']) == 1


# ── update_memory 门禁持久化 ──
def test_update_memory_gate_persists(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / 'mem.json')
    def fake_compress(s, u):
        return json.dumps({'summary': '进展X', 'entities': [], 'decisions': [], 'open_questions': []})
    def fake_faith(s, u):
        return json.dumps({'assertions': [{'text': 'x', 'supported': True, 'reason': ''}], 'overall_pass': True})
    r = update_memory('sess', HISTORY, store=store, compress_llm=fake_compress, faith_llm=fake_faith)
    assert r['status'] == 'updated'
    assert store.get('sess') is not None


def test_update_memory_gate_rejects(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / 'mem2.json')
    def fake_compress(s, u):
        return json.dumps({'summary': '进展X', 'entities': [], 'decisions': [], 'open_questions': []})
    def fake_faith(s, u):
        return json.dumps({'assertions': [{'text': 'x', 'supported': False, 'reason': 'no'}], 'overall_pass': False})
    r = update_memory('sess', HISTORY, store=store, compress_llm=fake_compress, faith_llm=fake_faith)
    assert r['status'] == 'rejected'
    assert store.get('sess') is None  # 未过门禁不持久化


# ── XML 注入 ──
def test_format_memory_injection():
    long_mem = {'summary': '进展', 'decisions': ['用X方案'], 'open_questions': ['Y待验证'], 'source_hash': 'abc'}
    short = {'recent': [{'role': 'user', 'content': '最近轮'}], 'older_summarized': True}
    out = format_memory_injection(long_mem, short)
    assert '<memory type="long">' in out
    assert '<memory type="short">' in out
    assert 'source_hash: abc' in out


def test_format_memory_injection_empty():
    assert format_memory_injection(None, None) == ''
    assert format_memory_injection({'summary': '', 'decisions': []}, None) == ''
