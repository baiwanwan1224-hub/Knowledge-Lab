#!/usr/bin/env python3
"""RAG 单点样例整合演示 — 检索 + 记忆压缩 + 注入 prompt 全链路。

展示「分块 → 语义检索 → 长/短记忆压缩 → 组装 context 注入」。
Usage: PYTHONIOENCODING=utf-8 python scripts/rag_memory_demo.py [query]
"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'C:\Users\27224\Desktop\Project\knowledge-lab')

from server.rag_index import retrieve, format_context
from server.memory_core import (
    MemoryStore, compress_long, faithfulness_check,
    short_memory_window, format_memory_injection,
)

QUERY = sys.argv[1] if len(sys.argv) > 1 else '上下文工程如何管理大模型的上下文窗口'

# 模拟一段多轮对话（长记忆素材）
CONVERSATION = [
    {'role': 'user', 'content': '我最近在搭 RAG 学习平台，200 多篇笔记'},
    {'role': 'assistant', 'content': '建议先做数据清洗，再建语义索引'},
    {'role': 'user', 'content': '清洗完了，检索准确度从 0.27 提到 0.91'},
    {'role': 'assistant', 'content': '效果显著，下一步可以做记忆压缩'},
    {'role': 'user', 'content': '对，我现在就在做记忆压缩，还想接一个多轮问答'},
]

print('═' * 60)
print('STEP 1 · 语义检索（query → top chunks）')
print('═' * 60)
chunks = retrieve(QUERY, top_k=3, retriever='hybrid')
for i, c in enumerate(chunks, 1):
    heading = ' > '.join(c['heading_path'])
    print(f"[{i}] ({c['score']}) {c['note_path'].split('/')[-1]} :: {heading}")

print('\n' + '═' * 60)
print('STEP 2 · 长记忆压缩（多轮对话 → 结构化记忆 + 忠实度门禁）')
print('═' * 60)
store = MemoryStore()
memory = compress_long(CONVERSATION, session_id='demo', store=None)
print('记忆 JSON:')
print(f'  summary: {memory["summary"]}')
print(f'  entities: {memory["entities"]}')
print(f'  decisions: {memory["decisions"]}')
print(f'  source_hash: {memory["source_hash"]}')
faith = faithfulness_check(memory, '\n'.join(f"{t['role']}: {t['content']}" for t in CONVERSATION))
print(f'忠实度门禁: score={faith["score"]} passed={faith["passed"]}')
if faith['passed']:
    store.put('demo', memory)
    print('✓ 已进长期库')

print('\n' + '═' * 60)
print('STEP 3 · 短记忆窗口（最近 2 轮原样 + 更早用长记忆替代）')
print('═' * 60)
short = short_memory_window(CONVERSATION, recent_k=2)
print(f'older_summarized={short["older_summarized"]} · 最近 {len(short["recent"])} 轮原样')

print('\n' + '═' * 60)
print('STEP 4 · 注入 prompt（chunks XML + memory 块）')
print('═' * 60)
ctx = format_context(chunks, citations=True)
mem_xml = format_memory_injection(memory, short)
print(ctx)
print()
print(mem_xml)
print()
print('— 回答时用 [1][2][3] 引用来源，并参考 <memory> 里的对话上下文 —')

print('\n' + '═' * 60)
print('✅ 全链路完成：干净数据 → 语义检索 → 记忆压缩 → 组装注入')
print('═' * 60)
