#!/usr/bin/env python3
"""Golden Set 回归评测 — 校验 LLM 批改与人工标注的偏差。

标准：standards/_STANDARD_评分标准.md §五
  Golden Set：5 道金题 + 标准答案 + 评分基准，每周回归，偏差 > 1 分调整批改 prompt。
数据：data/golden_set.json
用法：PYTHONIOENCODING=utf-8 python scripts/golden_regression.py
输出：控制台表 + docs/golden_regression_YYYYMMDD.json
"""
import sys
import io
import json
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'server'))

from quiz_grader import grade_answer

DEVIATION_LIMIT = 1.0


def load_golden(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding='utf-8'))
    return data.get('pairs', data if isinstance(data, list) else [])


def main():
    golden_path = PROJECT_ROOT / 'data' / 'golden_set.json'
    pairs = load_golden(golden_path)
    print(f'[golden] {len(pairs)} 道金题 · 偏差阈值 ±{DEVIATION_LIMIT} 分')

    results = []
    for p in pairs:
        question = {k: p.get(k) for k in ('type', 'question', 'correct_answer', 'explanation', 'difficulty') if p.get(k) is not None}
        question['options'] = p.get('options', [])
        question['knowledge_point'] = p.get('knowledge_point', '')
        grade = grade_answer(question, p.get('student_answer', ''))
        if 'error' in grade:
            results.append({'id': p['id'], 'error': grade['error']})
            print(f'  [✗] {p["id"]} 批改失败: {grade["error"]}')
            continue
        llm_score = grade.get('score', 0)
        dev = abs(llm_score - p['expected_score'])
        ok = dev <= DEVIATION_LIMIT
        results.append({'id': p['id'], 'type': p['type'], 'llm_score': llm_score,
                        'expected_score': p['expected_score'], 'max': p['expected_max'],
                        'deviation': round(dev, 2), 'passed': ok})
        flag = '✓' if ok else '✗ 超偏差'
        print(f'  [{flag}] {p["id"]} {p["type"]:<13} LLM={llm_score} vs 标注={p["expected_score"]} (dev {dev:.2f})')

    passed = sum(1 for r in results if r.get('passed'))
    print(f'\n通过 {passed}/{len(results)} · 偏差 > {DEVIATION_LIMIT} 分需调整批改 prompt')

    report = {
        'generated_at': datetime.now().isoformat(),
        'threshold': DEVIATION_LIMIT,
        'pairs': results, 'passed': passed, 'total': len(results),
        'note': '人工标注标准评分来自 data/golden_set.json，依据 _STANDARD_评分标准.md 各题型等级。',
    }
    docs = PROJECT_ROOT / 'docs'
    docs.mkdir(exist_ok=True)
    out = docs / f'golden_regression_{datetime.now().strftime("%Y%m%d")}.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[golden] 报告已保存: {out}')


if __name__ == '__main__':
    main()
