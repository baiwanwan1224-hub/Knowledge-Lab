#!/usr/bin/env python3
"""
RAG 检索评测 — Recall@k / Precision@k / MRR
对比 keyword(基线·改造前) vs vector(改造后) vs hybrid(合并)。

黄金集: data/rag_golden_set.json
  [{"query": "...", "note_path": "相对路径", "note_hint": "可选·检索线索"}]
判定标准: top-k 结果中是否命中理想来源笔记(note_path)。

Usage:
    PYTHONIOENCODING=utf-8 python scripts/rag_eval.py [--golden data/rag_golden_set.json] [--top-k 5]
输出: 控制台表格 + docs/rag_eval_YYYYMMDD.json
"""
import os
import sys
import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'server'))

from server import rag_index


def load_golden(path: Path) -> list[dict]:
    if not path.exists():
        print(f'[rag_eval] 黄金集不存在: {path}')
        sys.exit(1)
    data = json.loads(path.read_text(encoding='utf-8'))
    return data.get('pairs', data if isinstance(data, list) else [])


def run_pipeline(golden: list[dict], retrievers: list[str], top_k: int) -> dict:
    """Run each retriever over the golden set; return per-retriever metrics."""
    metrics = {}
    for retriever in retrievers:
        hits_at = {k: 0 for k in range(1, top_k + 1)}
        rr_sum = 0.0
        n = len(golden)
        total_query_tokens = 0
        for pair in golden:
            query = pair['query']
            ideal = pair['note_path']
            # normalize path separators for robust compare
            ideal = ideal.replace('\\', '/')
            results = rag_index.retrieve(query, top_k=top_k, retriever=retriever)
            ranked = [r['note_path'].replace('\\', '/') for r in results]
            # first correct rank (1-based), 0 if none
            first_rank = 0
            for i, p in enumerate(ranked, 1):
                if p == ideal or p.endswith('/' + ideal.split('/')[-1]):
                    first_rank = i
                    break
            if first_rank:
                for k in range(first_rank, top_k + 1):
                    hits_at[k] += 1
                rr_sum += 1.0 / first_rank
            # count embedding query tokens (vector/hybrid call embed_texts)
            # approximate: 1 token per query char group is not accurate; use len(query)//2
            if retriever in ('vector', 'hybrid'):
                total_query_tokens += max(1, len(query) // 2)
        metrics[retriever] = {
            'queries': n,
            'recall@k': {k: round(hits_at[k] / n, 4) if n else 0 for k in range(1, top_k + 1)},
            'mrr': round(rr_sum / n, 4) if n else 0,
            'query_embed_tokens_est': total_query_tokens,
        }
    return metrics


def format_table(metrics: dict, top_k: int) -> str:
    lines = []
    header = f"{'检索器':<10} " + ' '.join(f'R@{k:<5}' for k in range(1, top_k + 1)) + f" {'MRR':<6} {'embed tok/q'}"
    lines.append(header)
    lines.append('-' * len(header))
    for retriever, m in metrics.items():
        rec = ' '.join(f'{m["recall@k"][k]:<7.3f}' for k in range(1, top_k + 1))
        per_q = round(m['query_embed_tokens_est'] / m['queries'], 1) if m['queries'] else 0
        lines.append(f"{retriever:<10} {rec} {m['mrr']:<6.3f} {per_q}")
    return '\n'.join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='RAG 检索评测')
    parser.add_argument('--golden', default=str(PROJECT_ROOT / 'data' / 'rag_golden_set.json'))
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--retrievers', default='keyword,vector,hybrid')
    args = parser.parse_args()

    golden = load_golden(Path(args.golden))
    retrievers = [r.strip() for r in args.retrievers.split(',') if r.strip()]
    print(f'[rag_eval] 黄金集 {len(golden)} 条 · retrievers={retrievers} · top_k={args.top_k}')

    metrics = run_pipeline(golden, retrievers, args.top_k)
    print('\n' + format_table(metrics, args.top_k))

    # Attach index + cost context.
    try:
        idx = rag_index.load_index()
        index_stats = idx['stats']
    except Exception:
        index_stats = {}

    report = {
        'generated_at': datetime.now().isoformat(),
        'golden_set': str(Path(args.golden)),
        'top_k': args.top_k,
        'metrics': metrics,
        'index_stats': index_stats,
        'note': '黄金集判定=命中理想来源笔记(note_path)。embedding query tokens 为估算(len(query)//2)，精确值需从 API usage 埋点。',
    }
    docs = PROJECT_ROOT / 'docs'
    docs.mkdir(exist_ok=True)
    out = docs / f'rag_eval_{datetime.now().strftime("%Y%m%d")}.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n[rag_eval] 报告已保存: {out}')


if __name__ == '__main__':
    main()
