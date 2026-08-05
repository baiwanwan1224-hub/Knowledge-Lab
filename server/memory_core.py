"""
Memory Core — 长/短记忆压缩（RAG 单点样例 · 第二块：记忆）

滚动摘要 + 关键信息提取 + 幻觉门禁（Faithfulness）+ 短记忆 token 窗口。
设计文档：Desktop/KnowledgeLab_RAG单点样例设计_v1.0_20260804.html (P2/P3)

记忆 JSON 结构（可检索性强）：
    {
      "summary": "对话核心进展一句话",
      "entities": ["客户A", "方案B", "知识点C"],
      "decisions": ["已定用 X 方案"],
      "open_questions": ["Y 待验证"],
      "source_hash": "原文hash，防摘要失真",
      "ts": "2026-08-04T18:00:00"
    }

原则：
- 压缩用主 LLM（DeepSeek），忠实度校验用便宜 LLM（GLM-4-flash），不烧主额度
- 摘要必须可溯源（source_hash），压缩后过 Faithfulness 门禁才允许进长期库
- 关键事实「原文 + 摘要」双存
"""
import os
import re
import sys
import json
import time
import hashlib
from datetime import datetime
from pathlib import Path

import requests

# ── Load .env first (same pattern as classifier.py / rag_index.py) ──
_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE, 'r', encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
MEMORY_STORE_FILE = DATA_DIR / 'memory_store.json'

# 压缩用主模型（DeepSeek）
LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
LLM_API_URL = os.environ.get('LLM_API_URL', 'https://api.deepseek.com/v1/chat/completions')
LLM_MODEL = os.environ.get('LLM_MODEL', 'deepseek-v4-pro')

# 忠实度校验用便宜模型（GLM-4-flash · 智谱免费额度）
ZHIPU_API_KEY = os.environ.get('ZHIPU_API_KEY', '')
ZHIPU_API_URL = os.environ.get('ZHIPU_API_URL', 'https://open.bigmodel.cn/api/paas/v4/chat/completions')
FAITHFULNESS_MODEL = os.environ.get('FAITHFULNESS_MODEL', 'glm-4-flash')

# 触发压缩的 token 阈值 / 短记忆窗口配置
COMPRESS_TOKEN_THRESHOLD = int(os.environ.get('MEMORY_COMPRESS_THRESHOLD', '6000'))
RECENT_K = int(os.environ.get('MEMORY_RECENT_K', '4'))
FAITHFULNESS_THRESHOLD = 0.95  # 断言支撑率 >= 95% 才允许进长期库（幻觉率 < 5%）


# ═══════════════════════════════════════════════════════
# Token 估算（粗略，CJK 混合）
# ═══════════════════════════════════════════════════════
def _token_est(text: str) -> int:
    if not text:
        return 0
    return max(1, int(len(text) * 0.6))


def _turn_text(turn: dict) -> str:
    role = turn.get('role', 'user')
    content = turn.get('content', '')
    return f"{role}: {content}"


# ═══════════════════════════════════════════════════════
# LLM 调用（可注入，便于测试）
# ═══════════════════════════════════════════════════════
def _call_llm(system: str, user: str, api_key: str, api_url: str, model: str,
              temperature: float = 0.3, max_tokens: int = 1200, timeout: int = 90) -> str:
    """Generic OpenAI-compatible chat completion. Returns raw content string."""
    if not api_key:
        raise RuntimeError(f'未配置 API Key（model={model}）')
    resp = requests.post(
        api_url,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={'model': model, 'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ], 'temperature': temperature, 'max_tokens': max_tokens},
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise RuntimeError(f'{model} 调用失败 HTTP {resp.status_code}: {resp.text[:300]}')
    return resp.json()['choices'][0]['message']['content']


def _parse_json_loose(content: str) -> dict:
    """Parse JSON from LLM output, tolerating markdown fences / stray text."""
    if content.startswith('```'):
        content = re.sub(r'^```\w*\n?', '', content)
        content = re.sub(r'\n?```$', '', content)
    m = re.search(r'\{.*\}', content, re.DOTALL)
    if not m:
        raise RuntimeError(f'LLM 未返回 JSON: {content[:200]}')
    return json.loads(m.group())


# ═══════════════════════════════════════════════════════
# MemoryStore — 持久化（JSON 文件，单用户够用；SQLite 为升级路径）
# ═══════════════════════════════════════════════════════
class MemoryStore:
    """Session_id → memory JSON dict, persisted to data/memory_store.json."""

    def __init__(self, path: Path = None):
        self.path = Path(path) if path else MEMORY_STORE_FILE
        self._data: dict[str, dict] = {}
        self.load()

    def load(self):
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding='utf-8'))
            except Exception:
                self._data = {}

    def persist(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding='utf-8')

    def get(self, session_id: str) -> dict | None:
        return self._data.get(session_id)

    def put(self, session_id: str, memory: dict):
        self._data[session_id] = memory
        self.persist()

    def all(self) -> dict:
        return self._data


# ═══════════════════════════════════════════════════════
# 长记忆压缩 — 滚动摘要 + 关键信息提取
# ═══════════════════════════════════════════════════════
_COMPRESS_SYSTEM = (
    '你是对话记忆压缩专家。把输入的历史对话压缩成结构化记忆 JSON，'
    '只保留对后续对话有用的信息。禁止编造——所有内容必须来自对话原文。'
)

_COMPRESS_USER = """请把以下历史对话压缩为记忆 JSON：
{prev_block}## 历史对话
{history}

## 输出格式（严格 JSON）
{{"summary": "对话核心进展一句话", "entities": ["关键实体"], "decisions": ["已做的决定"], "open_questions": ["未解决的问题"]}}
- summary ≤ 60 字
- entities/decisions/open_questions 各 ≤ 8 条，每条 ≤ 20 字
- 只输出 JSON"""


def compress_long(history: list[dict] | str, prev_memory: dict | None = None,
                  session_id: str = '', store: MemoryStore | None = None,
                  llm_call=None) -> dict:
    """把一段历史压缩成记忆 JSON（滚动：可合并已有记忆）。

    history: 对话轮次 [{"role", "content"}]，或拼接好的字符串。
    prev_memory: 已有长期记忆（滚动时传入，作为上下文并入新记忆）。
    llm_call: 可注入（测试用），默认走 DeepSeek。
    返回带 source_hash / ts 的记忆 dict，并（若给 store+session_id）持久化。
    """
    if isinstance(history, list):
        history_text = '\n'.join(_turn_text(t) for t in history)
    else:
        history_text = history
    if not history_text.strip():
        raise ValueError('history 为空，无法压缩')

    prev_block = ''
    if prev_memory:
        prev_block = (
            "## 已有记忆（并入新记忆，保留仍有效的信息）\n"
            f"{json.dumps(prev_memory, ensure_ascii=False)}\n\n"
        )

    system = _COMPRESS_SYSTEM
    user = _COMPRESS_USER.format(prev_block=prev_block, history=history_text)
    if llm_call is None:
        raw = _call_llm(system, user, LLM_API_KEY, LLM_API_URL, LLM_MODEL)
    else:
        raw = llm_call(system, user)

    parsed = _parse_json_loose(raw)
    memory = {
        'summary': str(parsed.get('summary', '')).strip(),
        'entities': [str(e).strip() for e in parsed.get('entities', []) if str(e).strip()],
        'decisions': [str(d).strip() for d in parsed.get('decisions', []) if str(d).strip()],
        'open_questions': [str(q).strip() for q in parsed.get('open_questions', []) if str(q).strip()],
        'source_hash': hashlib.sha256(history_text.encode('utf-8')).hexdigest()[:16],
        'ts': datetime.now().isoformat(timespec='seconds'),
    }
    if store is not None and session_id:
        store.put(session_id, memory)
    return memory


# ═══════════════════════════════════════════════════════
# 忠实度校验（Faithfulness）— 便宜 LLM 逐断言核对
# ═══════════════════════════════════════════════════════
_FAITH_SYSTEM = (
    '你是事实一致性审核员。下面每条断言都是一个完整的陈述句或条目。'
    '逐条判断：该断言的核心事实是否能在【对话原文】中找到依据。'
    '判定标准是语义蕴含，不是字面匹配：'
    '1. 允许同义改写、概括、指代还原——只要核心事实在原文有明确依据，就标 supported=true。'
    '2. 原文明确没有该事实、或与原文矛盾，才标 supported=false。'
    '重要：把每条断言当作一个整体判断，不要拆字符、不要拆词、不要因措辞不同就误判 false。'
    '输出 JSON。'
)

_FAITH_USER = """## 对话原文
{source}

## 待审核断言（编号列表，每条是一个完整条目）
{assertions}

## 输出格式（严格 JSON）
{{"assertions": [{{"text": "断言原文(原样)", "supported": true/false, "reason": "一句话理由"}}], "overall_pass": true/false}}
- overall_pass = 所有断言均 supported
- assertions 数组长度必须等于输入断言条数，text 字段原样回填
- 只输出 JSON"""


def _build_assertions(memory: dict) -> list[str]:
    """把记忆拆成独立断言：summary 按句切分，其余字段逐条。"""
    assertions = []
    summary = memory.get('summary', '')
    if summary:
        for sent in re.split(r'[。！？；\n]', summary):
            sent = sent.strip()
            if sent:
                assertions.append(f'[summary] {sent}')
    for key, label in (('entities', 'entity'), ('decisions', 'decision'),
                       ('open_questions', 'open_question')):
        for item in memory.get(key, []):
            if str(item).strip():
                assertions.append(f'[{label}] {item}')
    return assertions


def _truncate_source(source: str, max_chars: int = 8000) -> str:
    """保留头尾、省略中段，避免关键事实落在截断窗口外被误判为幻觉。

    原实现 `source_text[-8000:]` 只留尾部——长对话时开头/中段的关键事实
    会被切掉，导致真实信息被门禁误拒（8/5 复现：16K 字符对话，开头事实被误判）。
    输出长度严格不超过 max_chars。
    """
    if len(source) <= max_chars:
        return source
    ellipsis = '\n…[中间省略]…\n'
    half = (max_chars - len(ellipsis)) // 2
    return source[:half] + ellipsis + source[-half:]


def faithfulness_check(memory: dict, source_text: str, llm_call=None) -> dict:
    """校验记忆摘要每个断言是否被原文支撑。返回 {score, passed, issues, details}。

    门禁：支撑率 >= FAITHFULNESS_THRESHOLD（95%）才允许进长期库。
    """
    assertions = _build_assertions(memory)
    if not assertions:
        return {'score': 1.0, 'passed': True, 'issues': [], 'details': []}

    system = _FAITH_SYSTEM
    user = _FAITH_USER.format(
        source=_truncate_source(source_text),  # 头尾保留，控 token
        assertions='\n'.join(f'{i}. {a}' for i, a in enumerate(assertions, 1)),
    )
    if llm_call is None:
        raw = _call_llm(system, user, ZHIPU_API_KEY or LLM_API_KEY,
                        ZHIPU_API_URL if ZHIPU_API_KEY else LLM_API_URL,
                        FAITHFULNESS_MODEL if ZHIPU_API_KEY else LLM_MODEL,
                        temperature=0.1, max_tokens=2000)
    else:
        raw = llm_call(system, user)

    parsed = _parse_json_loose(raw)
    details = parsed.get('assertions', [])
    supported = sum(1 for a in details if a.get('supported'))
    total = len(details)
    score = supported / total if total else 1.0
    issues = [a.get('text', '') for a in details if not a.get('supported')]
    passed = score >= FAITHFULNESS_THRESHOLD and not issues
    return {'score': round(score, 3), 'passed': passed, 'issues': issues, 'details': details}


# ═══════════════════════════════════════════════════════
# 短记忆窗口 — 最近 K 轮原样 + 更早用长记忆摘要替代
# ═══════════════════════════════════════════════════════
def short_memory_window(history: list[dict], recent_k: int = RECENT_K,
                        token_budget: int | None = None) -> dict:
    """返回 {recent: [...最近轮次...], older_summarized: bool, tokens: n}。

    最近 recent_k 轮原样保留；若 token_budget 限制，从最旧轮次开始裁掉。
    更早的轮次用长记忆摘要替代（由调用方注入 older 摘要）。
    """
    turns = list(history)
    recent = turns[-recent_k:] if turns else []
    older = turns[:-recent_k] if len(turns) > recent_k else []

    if token_budget is not None:
        kept = []
        used = 0
        for t in reversed(recent):
            tok = _token_est(t.get('content', ''))
            if used + tok > token_budget and kept:
                break
            kept.insert(0, t)
            used += tok
        recent = kept

    return {
        'recent': recent,
        'older_summarized': len(older) > 0,
        'older_count': len(older),
        'tokens': sum(_token_est(t.get('content', '')) for t in recent),
    }


# ═══════════════════════════════════════════════════════
# 索引进 Prompt — XML memory 块
# ═══════════════════════════════════════════════════════
def format_memory_injection(long_memory: dict | None = None,
                            short_window: dict | None = None) -> str:
    """按设计文档格式输出 <memory> XML 块，供 prompt 注入。"""
    parts = []
    if long_memory and (long_memory.get('summary') or long_memory.get('decisions')):
        inner = []
        if long_memory.get('summary'):
            inner.append(f"summary: {long_memory['summary']}")
        if long_memory.get('decisions'):
            inner.append('decisions: ' + '; '.join(long_memory['decisions']))
        if long_memory.get('open_questions'):
            inner.append('open_questions: ' + '; '.join(long_memory['open_questions']))
        if long_memory.get('source_hash'):
            inner.append(f"source_hash: {long_memory['source_hash']}")
        parts.append(f'<memory type="long">\n' + '\n'.join(inner) + '\n</memory>')
    if short_window and short_window.get('recent'):
        recent_lines = '\n'.join(_turn_text(t) for t in short_window['recent'])
        parts.append(f'<memory type="short">\n{recent_lines}\n</memory>')
    return '\n'.join(parts)


# ═══════════════════════════════════════════════════════
# 高层：完整记忆更新流程（压缩 + 门禁 + 持久化）
# ═══════════════════════════════════════════════════════
def update_memory(session_id: str, history: list[dict], store: MemoryStore | None = None,
                  compress_llm=None, faith_llm=None) -> dict:
    """把新历史并入会话长期记忆，先过忠实度门禁。

    返回 {'status': 'updated'|'rejected', 'memory': {...}, 'faithfulness': {...}}。
    """
    store = store or MemoryStore()
    prev = store.get(session_id)
    memory = compress_long(history, prev_memory=prev, session_id=session_id,
                           store=None, llm_call=compress_llm)
    # 忠实度校验用拼接的原文
    if isinstance(history, list):
        source = '\n'.join(_turn_text(t) for t in history)
    else:
        source = history
    faith = faithfulness_check(memory, source, llm_call=faith_llm)
    if faith['passed']:
        store.put(session_id, memory)
        return {'status': 'updated', 'memory': memory, 'faithfulness': faith}
    # 未过门禁：不持久化，原记忆保留
    return {'status': 'rejected', 'memory': memory, 'faithfulness': faith,
            'note': '忠实度未过门槛，长期记忆未更新（原文+摘要双存原则下可人工复核）'}


# ═══════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════
def _cli():
    import argparse
    parser = argparse.ArgumentParser(prog='memory_core', description='Knowledge Lab 记忆压缩')
    parser.add_argument('--history', default='', help='历史对话文本（临时演示用）')
    parser.add_argument('--session', default='demo', help='会话 id')
    parser.add_argument('--no-faith', action='store_true', help='跳过忠实度门禁')
    args = parser.parse_args()

    if not args.history:
        # 演示：给一段假对话
        args.history = (
            'user: 我最近在搭 RAG 学习平台\n'
            'assistant: 建议先做数据清洗再建索引\n'
            'user: 我已经清洗完了，检索准确度从 0.27 提到 0.91\n'
            'assistant: 效果显著，下一步可以做记忆压缩'
        )
    history = [{'role': 'user', 'content': l.split(': ', 1)[1]}
               for l in args.history.split('\n') if ': ' in l]

    store = MemoryStore()
    memory = compress_long(history, session_id=args.session, store=None)
    print('═══ 长记忆压缩结果 ═══')
    print(json.dumps(memory, ensure_ascii=False, indent=2))
    if not args.no_faith:
        faith = faithfulness_check(memory, args.history)
        print('\n═══ 忠实度门禁 ═══')
        print('score:', faith['score'], '| passed:', faith['passed'])
        for a in faith['details']:
            print(f"  [{('✓' if a.get('supported') else '✗')}] {a.get('text','')[:40]} — {a.get('reason','')[:40]}")
        if faith['passed']:
            store.put(args.session, memory)
            print(f'✓ 已持久化到会话 {args.session}')
        else:
            print('✗ 未过门禁，长期记忆未更新')
    else:
        store.put(args.session, memory)
        print(f'✓ 已持久化到会话 {args.session}（跳过门禁）')

    short = short_memory_window(history, recent_k=2)
    print('\n═══ 短记忆窗口 ═══')
    print('older_summarized:', short['older_summarized'], '| tokens:', short['tokens'])
    print(format_memory_injection(memory, short))


if __name__ == '__main__':
    _cli()
