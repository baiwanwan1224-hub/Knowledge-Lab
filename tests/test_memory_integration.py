"""Memory integration tests — quiz_generator read side + quiz_grader write side.

Covers the MEMORY_ENABLE opt-in wiring added 2026-08-05:
  - quiz_generator._memory_enhance: disabled / no memory / memory present
  - quiz_generator.build_prompt: memory_context injected into the prompt
  - quiz_grader.update_learner_memory: disabled / aggregates results / gate rejection
"""
import os
import sys
import pytest

# CLI scripts do `from memory_core import ...` (server/ on path when run from server/).
# Under pytest we import via `from server import ...`, so make server/ importable too.
SERVER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server')
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

# Use the TOP-LEVEL memory_core module (server/ on sys.path above) so that
# monkeypatching it matches what quiz_grader/quiz_generator import internally
# (`from memory_core import ...`), not server.memory_core which is a separate module object.
import memory_core
from server.quiz_generator import _memory_enhance, build_prompt
from server.quiz_grader import update_learner_memory


def _fake_mem(summary='进展', decisions=None, open_questions=None):
    return {'summary': summary, 'decisions': decisions or [], 'open_questions': open_questions or [],
            'source_hash': 'abc', 'ts': '2026-08-05T00:00:00'}


# ── 读侧：_memory_enhance ──
def test_memory_enhance_disabled(tmp_path, monkeypatch):
    monkeypatch.delenv('MEMORY_ENABLE', raising=False)
    store = memory_core.MemoryStore(tmp_path / 'mem.json')
    store.put('learner', _fake_mem())
    assert _memory_enhance('topic', store=store) == ''


def test_memory_enhance_no_memory(tmp_path, monkeypatch):
    monkeypatch.setenv('MEMORY_ENABLE', '1')
    store = memory_core.MemoryStore(tmp_path / 'mem2.json')  # empty store
    assert _memory_enhance('topic', store=store) == ''


def test_memory_enhance_returns_snippet(tmp_path, monkeypatch):
    monkeypatch.setenv('MEMORY_ENABLE', '1')
    store = memory_core.MemoryStore(tmp_path / 'mem3.json')
    store.put('learner', _fake_mem(summary='用户强化了 RAG 检索', decisions=['用语义检索'],
                                   open_questions=['记忆压缩待完善']))
    out = _memory_enhance('topic', store=store)
    assert '用户强化了 RAG 检索' in out
    assert '用语义检索' in out
    assert '待强化' in out


# ── 读侧：build_prompt 注入 ──
def test_build_prompt_injects_memory_context():
    prompt = build_prompt('AI产品经理', 2, ['single_choice'], 'medium', [], memory_context='薄弱点：RAG')
    assert '用户长期记忆' in prompt
    assert '薄弱点：RAG' in prompt


def test_build_prompt_no_memory_context():
    prompt = build_prompt('AI产品经理', 2, ['single_choice'], 'medium', [])
    assert '用户长期记忆' not in prompt


# ── 写侧：update_learner_memory ──
def test_update_learner_memory_disabled(monkeypatch):
    monkeypatch.delenv('MEMORY_ENABLE', raising=False)
    assert update_learner_memory([])['status'] == 'skipped'


def test_update_learner_memory_aggregates_and_updates(tmp_path, monkeypatch):
    monkeypatch.setenv('MEMORY_ENABLE', '1')
    captured = {}

    def fake_update(session_id, history, store):
        captured['session_id'] = session_id
        captured['history'] = history
        return {'status': 'updated', 'memory': {}, 'faithfulness': {'score': 1.0, 'passed': True}}

    monkeypatch.setattr(memory_core, 'update_memory', fake_update)
    results = [
        {'error': None, 'is_correct': False, 'knowledge_point': 'RAG',
         'weakness_tags': ['概念理解不清'], 'misunderstanding': '混淆了检索与生成'},
        {'error': None, 'is_correct': True, 'knowledge_point': '产品管理',
         'weakness_tags': [], 'misunderstanding': ''},
    ]
    r = update_learner_memory(results, store=memory_core.MemoryStore(tmp_path / 'mem4.json'))
    assert r['status'] == 'updated'
    assert captured['session_id'] == 'learner'
    texts = [h['content'] for h in captured['history']]
    assert any('RAG' in t and '错误' in t and '概念理解不清' in t for t in texts)
    assert any('产品管理' in t and '正确' in t for t in texts)


def test_update_learner_memory_gate_rejects(tmp_path, monkeypatch):
    monkeypatch.setenv('MEMORY_ENABLE', '1')

    def fake_update(session_id, history, store):
        return {'status': 'rejected', 'memory': {}, 'faithfulness': {'score': 0.4, 'passed': False}}

    monkeypatch.setattr(memory_core, 'update_memory', fake_update)
    results = [{'error': None, 'is_correct': False, 'knowledge_point': 'RAG',
                'weakness_tags': [], 'misunderstanding': ''}]
    r = update_learner_memory(results, store=memory_core.MemoryStore(tmp_path / 'mem5.json'))
    assert r['status'] == 'rejected'
