"""
RAG Index — chunking + embedding retrieval core for Knowledge Lab.

Provides the "检索核心" (retrieval core): Markdown structural chunking,
offline embedding index (Zhipu embedding-3), semantic retrieval (vector /
keyword / hybrid), and XML context formatting for prompt injection.

Design doc: Desktop/KnowledgeLab_RAG单点样例设计_v1.0_20260804.html
Scope: retrieval core only. Long/short memory compression is deferred.

Usage:
    python -m server.rag_index build                 # incremental index build
    python -m server.rag_index retrieve --query "上下文工程" --top-k 5
    python -m server.rag_index stats
"""
import os
import re
import sys
import json
import time
import hashlib
from datetime import datetime
from pathlib import Path

import numpy as np
import requests

# Importable both as `server.rag_index` (python -m) and as `rag_index` (top-level).
try:
    from . import frontmatter_utils
except ImportError:  # pragma: no cover - top-level import path
    import frontmatter_utils

# ── Load .env first (same pattern as classifier.py) ──
_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE, 'r', encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# ── Config ─────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
INDEX_FILE = DATA_DIR / 'rag_index.json'
INDEX_VERSION = 1

VAULT_PATH = Path(os.environ.get('VAULT_PATH', str(PROJECT_ROOT / 'vault')))
NOTES_DIR = VAULT_PATH / 'Knowledge Lab' / '00_学习笔记'
EXTRA_NOTE_DIRS = [
    VAULT_PATH / 'Clippings',
    VAULT_PATH / '网页提取',
]

ZHIPU_API_KEY = os.environ.get('ZHIPU_API_KEY', '')
ZHIPU_EMBEDDING_URL = os.environ.get('ZHIPU_EMBEDDING_URL', 'https://open.bigmodel.cn/api/paas/v4/embeddings')
ZHIPU_EMBEDDING_MODEL = os.environ.get('ZHIPU_EMBEDDING_MODEL', 'embedding-3')

# Chunking knobs (design doc: Markdown header slice + char budget + overlap)
MAX_CHARS = int(os.environ.get('RAG_MAX_CHARS', '1500'))   # ~512 token 兜底 for CJK
OVERLAP = int(os.environ.get('RAG_OVERLAP', '200'))        # carry-over tail between splits
EMBED_BATCH = 32                                           # embedding API batch size
EMBED_RETRY = 2                                            # retries per batch

_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')


# ═══════════════════════════════════════════════════════
# 1. Chunking — Markdown structural slice
# ═══════════════════════════════════════════════════════
def _token_est(text: str) -> int:
    """Rough token estimate for CJK/English mix (not authoritative)."""
    if not text:
        return 0
    return max(1, int(len(text) * 0.6))


def _split_paragraphs(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split oversized text, keeping every piece within the char budget.

    Paragraphs that fit are grouped up to max_chars (semantic boundaries kept).
    A single paragraph longer than the budget is hard-split into char windows
    with `overlap` chars carried between adjacent windows.
    """
    paras = [p.strip() for p in text.split('\n\n') if p.strip()]
    result = []
    buf = ''
    for p in paras:
        # Hard-split a paragraph that alone exceeds the budget.
        if len(p) > max_chars:
            if buf:
                result.append(buf)
                buf = ''
            pos = 0
            while pos < len(p):
                result.append(p[pos:pos + max_chars])
                pos += max_chars - overlap
            continue
        if not buf:
            buf = p
        elif len(buf) + 2 + len(p) <= max_chars:
            buf = buf + '\n\n' + p
        else:
            result.append(buf)
            buf = p
    if buf:
        result.append(buf)
    return result


def chunk_markdown(content: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP) -> list[dict]:
    """Split a Markdown note into semantic chunks.

    Strategy: split on ATX headings (# to ######). Each heading starts a new
    chunk; the heading path (ancestors + self) is preserved as metadata. Chunks
    with no direct content (heading immediately followed by a deeper heading)
    are folded away. Oversized chunks are further split by paragraphs.

    Returns list of chunk dicts (without note-level metadata):
        {heading_path: [str], text: str, char_len: int, token_est: int}
    """
    # Separate frontmatter from body.
    from . import frontmatter_utils
    meta, body = frontmatter_utils.parse_frontmatter(content)
    if not body.strip():
        return []

    chunks = []
    cur_path = []    # stack of (level, name)
    cur_lines = []   # content lines of current chunk (headings excluded)

    def flush():
        nonlocal cur_lines
        if cur_lines:
            text = '\n'.join(cur_lines).strip()
            if text:
                chunks.append({
                    'heading_path': [name for _, name in cur_path],
                    'text': text,
                    'char_len': len(text),
                    'token_est': _token_est(text),
                })
            cur_lines = []

    for line in body.split('\n'):
        m = _HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            name = m.group(2).strip()
            # Pop sibling / deeper headings, keep ancestors.
            while cur_path and cur_path[-1][0] >= level:
                cur_path.pop()
            cur_path.append((level, name))
        else:
            cur_lines.append(line)
    flush()

    # Fold away chunks that are pure headings (no direct content) — their
    # heading is already recorded in the child chunk's heading_path.
    # A chunk whose text is identical to its last heading line is a heading-only chunk.

    # Split oversized chunks by paragraphs.
    final = []
    for c in chunks:
        if c['char_len'] > max_chars:
            for part in _split_paragraphs(c['text'], max_chars, overlap):
                final.append({
                    'heading_path': c['heading_path'],
                    'text': part,
                    'char_len': len(part),
                    'token_est': _token_est(part),
                })
        else:
            final.append(c)

    # Attach heading context to chunk text used for embedding.
    for c in final:
        prefix = ' > '.join(c['heading_path'])
        c['embed_text'] = f"{prefix}\n{c['text']}" if prefix else c['text']

    return final


# ═══════════════════════════════════════════════════════
# 2. Embedding — Zhipu embedding-3
# ═══════════════════════════════════════════════════════
def embed_texts(texts: list[str]) -> tuple[list[list[float]], dict]:
    """Embed a list of texts via Zhipu embedding-3.

    Returns (embeddings, usage) where usage aggregates prompt_tokens.
    Raises RuntimeError if the API key is missing or the account has no balance.
    """
    if not ZHIPU_API_KEY:
        raise RuntimeError('ZHIPU_API_KEY 未配置。请在 .env 中设置。')
    if not texts:
        return [], {'prompt_tokens': 0}

    all_emb = []
    total_tokens = 0
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i + EMBED_BATCH]
        payload = {'model': ZHIPU_EMBEDDING_MODEL, 'input': batch}
        last_err = None
        for attempt in range(EMBED_RETRY + 1):
            try:
                resp = requests.post(
                    ZHIPU_EMBEDDING_URL,
                    headers={'Authorization': f'Bearer {ZHIPU_API_KEY}',
                             'Content-Type': 'application/json'},
                    json=payload, timeout=60,
                )
                data = resp.json()
                if resp.status_code == 200 and data.get('data'):
                    # Response order matches input order.
                    emb = [d['embedding'] for d in data['data']]
                    all_emb.extend(emb)
                    total_tokens += data.get('usage', {}).get('prompt_tokens', 0)
                    break
                last_err = f'HTTP {resp.status_code}: {json.dumps(data, ensure_ascii=False)[:300]}'
                # Balance / auth errors are not retryable — surface immediately.
                if resp.status_code in (401, 429):
                    raise RuntimeError(last_err)
            except RuntimeError:
                raise
            except Exception as e:
                last_err = str(e)
            time.sleep(1.0 * (attempt + 1))
        else:
            raise RuntimeError(f'embedding 批次失败（第 {i // EMBED_BATCH + 1} 批）: {last_err}')
    return all_emb, {'prompt_tokens': total_tokens}


# ═══════════════════════════════════════════════════════
# 3. Index persistence — data/rag_index.json (incremental)
# ═══════════════════════════════════════════════════════
def scan_notes() -> list[dict]:
    """Walk note directories, return [{rel_path, content, file_hash}]."""
    notes = []
    seen = set()
    for base in [NOTES_DIR] + EXTRA_NOTE_DIRS:
        if not base.exists():
            continue
        for root, _dirs, files in os.walk(str(base)):
            for fname in sorted(files):
                if not fname.endswith('.md') or fname.startswith('模板_') or '.tmp' in fname:
                    continue
                fp = Path(root) / fname
                try:
                    content = fp.read_text(encoding='utf-8')
                except Exception:
                    continue
                rel = str(fp.relative_to(VAULT_PATH))
                if rel in seen:
                    continue
                seen.add(rel)
                notes.append({
                    'rel_path': rel,
                    'content': content,
                    'file_hash': hashlib.sha256(content.encode('utf-8')).hexdigest()[:16],
                })
    return notes


def _normalize_chunk(chunk: dict, note: dict, idx: int) -> dict:
    """Attach note-level metadata and a stable chunk_id."""
    chunk_id = hashlib.sha256(f"{note['rel_path']}|{idx}".encode('utf-8')).hexdigest()[:12]
    return {
        'chunk_id': chunk_id,
        'note_path': note['rel_path'],
        'file_hash': note['file_hash'],
        'title': chunk.get('title', Path(note['rel_path']).stem),
        'topics': chunk.get('topics', []),
        'heading_path': chunk['heading_path'],
        'text': chunk['text'],
        'embed_text': chunk['embed_text'],
        'char_len': chunk['char_len'],
        'token_est': chunk['token_est'],
        'chunk_index': idx,
    }


def _extract_meta(content: str, fallback_title: str) -> dict:
    """Pull title/topics from frontmatter (best-effort)."""
    from . import frontmatter_utils
    meta, _ = frontmatter_utils.parse_frontmatter(content)
    topics = meta.get('topics', [])
    if isinstance(topics, str):
        topics = [t.strip() for t in topics.split(',')]
    title = meta.get('title') or fallback_title
    return {'title': title, 'topics': topics}


def build_index(force: bool = False) -> dict:
    """Incrementally build the RAG index over all notes.

    Only changed/new notes are re-chunked and re-embedded; unchanged chunks
    keep their cached embeddings. Returns stats dict.
    """
    notes = scan_notes()
    if not notes:
        raise RuntimeError('未扫描到任何笔记。请检查 VAULT_PATH 配置。')

    # Load existing index for incremental reuse.
    old = {}
    if not force and INDEX_FILE.exists():
        try:
            old = json.loads(INDEX_FILE.read_text(encoding='utf-8'))
        except Exception:
            old = {}

    old_notes = {n['note_path']: n for n in old.get('notes', [])}
    old_emb = old.get('embeddings', {})  # chunk_id -> vector

    # Decide which notes need rebuild.
    to_process = []
    for n in notes:
        prev = old_notes.get(n['rel_path'])
        if force or prev is None or prev.get('file_hash') != n['file_hash']:
            to_process.append(n)

    new_chunks = []
    new_emb = {}
    total_tokens = 0
    if to_process:
        print(f'[rag_index] 待处理笔记: {len(to_process)} 篇（共 {len(notes)} 篇）', file=sys.stderr)
        for n in to_process:
            fallback = Path(n['rel_path']).stem
            meta = _extract_meta(n['content'], fallback)
            base = chunk_markdown(n['content'])
            chunks = []
            for idx, c in enumerate(base):
                cc = _normalize_chunk(c, n, idx)
                cc['title'] = meta['title']
                cc['topics'] = meta['topics']
                chunks.append(cc)
            if not chunks:
                continue
            # Embed this note's chunks.
            texts = [c['embed_text'] for c in chunks]
            emb, usage = embed_texts(texts)
            total_tokens += usage['prompt_tokens']
            for c, vec in zip(chunks, emb):
                new_emb[c['chunk_id']] = vec
            new_chunks.extend(chunks)
            print(f'[rag_index]   {n["rel_path"]} -> {len(chunks)} chunks', file=sys.stderr)

    # Merge: new/updated chunks + unchanged chunks (embeddings preserved).
    merged_chunks = {}
    merged_emb = {}
    for c in old.get('chunks', []):
        merged_chunks[c['chunk_id']] = c
    for cid, vec in old_emb.items():
        if cid in merged_chunks:
            merged_emb[cid] = vec
    for c in new_chunks:
        merged_chunks[c['chunk_id']] = c
    for cid, vec in new_emb.items():
        merged_emb[cid] = vec

    # Drop chunks whose note no longer exists.
    valid_note_paths = {n['rel_path'] for n in notes}
    for cid in list(merged_chunks):
        if merged_chunks[cid]['note_path'] not in valid_note_paths:
            merged_chunks.pop(cid)
            merged_emb.pop(cid, None)

    chunks_list = sorted(merged_chunks.values(), key=lambda c: c['note_path'])
    stats = {
        'note_count': len(notes),
        'chunk_count': len(chunks_list),
        'processed_notes': len(to_process),
        'embed_tokens_total': total_tokens,
        'built_at': datetime.now().isoformat(),
    }
    index = {
        'version': INDEX_VERSION,
        'model': ZHIPU_EMBEDDING_MODEL,
        'stats': stats,
        'notes': [{k: n[k] for k in ('rel_path', 'file_hash')} for n in notes],
        'chunks': chunks_list,
        'embeddings': merged_emb,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'[rag_index] 索引已保存: {INDEX_FILE}（{len(chunks_list)} chunks, 本次 embed {total_tokens} tokens）', file=sys.stderr)
    return stats


def load_index() -> dict:
    if not INDEX_FILE.exists():
        raise RuntimeError(f'索引不存在: {INDEX_FILE}\n请先运行: python -m server.rag_index build')
    return json.loads(INDEX_FILE.read_text(encoding='utf-8'))


# ═══════════════════════════════════════════════════════
# 4. Retrieval — vector / keyword / hybrid
# ═══════════════════════════════════════════════════════
def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def _keyword_score(query: str, chunk: dict) -> float:
    """Baseline: substring + token + Chinese-bigram matches against title/heading/text.

    中文没有空格，q.split() 对中文查询退化为整句单 token（几乎不命中），
    导致纯 keyword 检索 R@1 仅 0.273。加相邻汉字 bigram 命中加权：
    每命中 +0.25（弱于整句 1.0 / 英文 token 1.0 / title 3.0），
    提供无依赖的近似中文分词信号。
    """
    q = query.lower()
    text = (chunk.get('text', '') + '\n' + chunk.get('title', '') + '\n' + ' '.join(chunk.get('heading_path', []))).lower()
    # Full query substring + whitespace tokens.
    score = 1.0 if q and q in text else 0.0
    for tok in q.split():
        if len(tok) >= 2 and tok in text:
            score += 1.0
    # Chinese bigram hits (contiguous CJK pairs, ~0.15 each — small enough to
    # break vector ties without crowding correct results out of top-k).
    for i in range(len(q) - 1):
        b0, b1 = q[i], q[i + 1]
        if '\u4e00' <= b0 <= '\u9fff' and '\u4e00' <= b1 <= '\u9fff' and b0 + b1 in text:
            score += 0.15
    # Title hit bonus.
    if q in chunk.get('title', '').lower():
        score += 3.0
    return score


def retrieve(query: str, top_k: int = 5, retriever: str = 'hybrid') -> list[dict]:
    """Retrieve top-k chunks for a query.

    retriever:
      'vector'  — semantic only (cosine over chunk embeddings)
      'keyword' — baseline only (substring hits against title/heading/text)
      'hybrid'  — vector score as base + keyword hit bonus. (Empirically better
                  than "keyword first + vector append", which lets noisy keyword
                  hits crowd correct semantic results out of top-k — see
                  docs/rag_eval_20260804.json.)
    """
    index = load_index()
    chunks = index['chunks']
    emb = index['embeddings']
    if not chunks or not emb:
        return []

    # Vector cosine scores (clamped to >= 0).
    v_scores: dict[str, float] = {}
    if retriever in ('vector', 'hybrid'):
        q_vec, _usage = embed_texts([query])
        if q_vec:
            qv = np.array(q_vec[0])
            for c in chunks:
                vec = emb.get(c['chunk_id'])
                if vec is not None:
                    v_scores[c['chunk_id']] = max(0.0, _cosine(qv, np.array(vec)))

    # Keyword hit scores.
    k_scores: dict[str, float] = {c['chunk_id']: _keyword_score(query, c) for c in chunks}

    def combined(c: dict) -> float:
        return v_scores.get(c['chunk_id'], 0.0) + 0.08 * k_scores.get(c['chunk_id'], 0.0)

    if retriever == 'keyword':
        ranked = sorted(chunks, key=lambda c: -k_scores.get(c['chunk_id'], 0))
        ranked = [c for c in ranked if k_scores.get(c['chunk_id'], 0) > 0]
        score_key = lambda c: k_scores.get(c['chunk_id'], 0)
    elif retriever == 'vector':
        ranked = sorted(chunks, key=lambda c: -v_scores.get(c['chunk_id'], 0.0))
        score_key = lambda c: v_scores.get(c['chunk_id'], 0.0)
    else:  # hybrid
        ranked = sorted(chunks, key=lambda c: -combined(c))
        score_key = lambda c: combined(c)

    results = []
    for c in ranked[:top_k]:
        results.append({
            'chunk_id': c['chunk_id'], 'note_path': c['note_path'],
            'title': c['title'], 'heading_path': c['heading_path'],
            'text': c['text'], 'score': round(float(score_key(c)), 4),
            'source': retriever,
        })
    return results


# ═══════════════════════════════════════════════════════
# 5. Context formatting for prompt injection
# ═══════════════════════════════════════════════════════
def format_context(chunks: list[dict], citations: bool = True) -> str:
    """Format retrieved chunks as an XML context block with metadata.

    Matches design doc P4: <chunk_N source= score=> + [1][2][3] citation markers.
    """
    parts = ['<context>']
    for i, c in enumerate(chunks, 1):
        src = c.get('note_path', '')
        heading = ' > '.join(c.get('heading_path', []))
        attrs = f' source="{src}" score="{c.get("score", "")}"'
        if heading:
            attrs += f' path="{heading}"'
        parts.append(f'<chunk_{i}{attrs}>')
        parts.append(c.get('text', ''))
        parts.append(f'</chunk_{i}>')
    parts.append('</context>')
    out = '\n'.join(parts)
    if citations:
        out += '\n\n回答时请用 [1][2][3] 标注每条引用对应的来源。'
    return out


# ═══════════════════════════════════════════════════════
# 6. CLI
# ═══════════════════════════════════════════════════════
def _cli() -> None:
    import argparse
    parser = argparse.ArgumentParser(prog='rag_index', description='Knowledge Lab RAG 检索核心')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_build = sub.add_parser('build', help='构建/增量更新索引')
    p_build.add_argument('--force', action='store_true', help='强制全量重建')

    p_retr = sub.add_parser('retrieve', help='语义检索')
    p_retr.add_argument('--query', required=True)
    p_retr.add_argument('--top-k', type=int, default=5)
    p_retr.add_argument('--retriever', choices=['vector', 'keyword', 'hybrid'], default='hybrid')
    p_retr.add_argument('--json', action='store_true', help='输出 JSON')

    p_stats = sub.add_parser('stats', help='索引统计')

    args = parser.parse_args()

    if args.cmd == 'build':
        stats = build_index(force=args.force)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    elif args.cmd == 'retrieve':
        results = retrieve(args.query, top_k=args.top_k, retriever=args.retriever)
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            for i, r in enumerate(results, 1):
                heading = ' > '.join(r['heading_path'])
                print(f"[{i}] ({r['source']}, {r['score']}) {r['note_path']} :: {heading}")
                print(f"    {r['text'][:120].replace(chr(10), ' ')}")
            if not results:
                print('无结果。')
    elif args.cmd == 'stats':
        index = load_index()
        print(json.dumps(index['stats'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    _cli()
