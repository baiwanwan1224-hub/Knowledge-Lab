#!/usr/bin/env python3
"""双模型批改校准 — DeepSeek(主) vs 第二模型(默认智谱 GLM) 评分偏差追踪。

标准：standards/_STANDARD_评分标准.md §五 双模型校准
  "每 10 次批改随机抽取 1 次，用独立模型评分，偏差 > 1 分触发审查"。
落地：对 data/golden_set.json 的 5 道金题，用两个模型批改同一学生答案，对比评分偏差。

第二模型可配置（env）：
  MODEL_B_API_KEY / MODEL_B_API_URL / MODEL_B_MODEL
  默认 = 智谱 GLM-4-flash（现成 key）。标准 §五 指定 GPT-4.1——配好这三个变量即可切换。

用法：PYTHONIOENCODING=utf-8 python scripts/model_calibration.py
输出：docs/model_calibration_YYYYMMDD.json
"""
import sys
import io
import os
import json
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'server'))

from quiz_grader import grade_answer

MODEL_B_KEY = os.environ.get('MODEL_B_API_KEY', os.environ.get('ZHIPU_API_KEY', ''))
MODEL_B_URL = os.environ.get('MODEL_B_API_URL', 'https://open.bigmodel.cn/api/paas/v4/chat/completions')
MODEL_B_MODEL = os.environ.get('MODEL_B_MODEL', 'glm-4-flash')
DEVIATION_LIMIT = 1.0


def load_golden(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding='utf-8'))
    return data.get('pairs', data if isinstance(data, list) else [])


def main():
    golden_path = PROJECT_ROOT / 'data' / 'golden_set.json'
    pairs = load_golden(golden_path)
    model_a = os.environ.get('LLM_MODEL', 'deepseek-v4-pro')
    print(f'[calibrate] 模型A={model_a} vs 模型B={MODEL_B_MODEL} · 阈值 ±{DEVIATION_LIMIT}')

    results = []
    for p in pairs:
        question = {k: p.get(k) for k in ('type', 'question', 'correct_answer', 'explanation', 'difficulty') if p.get(k) is not None}
        question['options'] = p.get('options', [])
        question['knowledge_point'] = p.get('knowledge_point', '')
        answer = p.get('student_answer', '')
        ga = grade_answer(question, answer)  # 模型 A：DeepSeek
        gb = grade_answer(question, answer, api_key=MODEL_B_KEY, api_url=MODEL_B_URL, model=MODEL_B_MODEL)
        if 'error' in ga or 'error' in gb:
            results.append({'id': p['id'], 'error_a': ga.get('error'), 'error_b': gb.get('error')})
            print(f'  [✗] {p["id"]} A={ga.get("error")} · B={gb.get("error")}')
            continue
        sa = ga.get('score', 0)
        sb = gb.get('score', 0)
        dev = abs(sa - sb)
        ok = dev <= DEVIATION_LIMIT
        results.append({'id': p['id'], 'type': p['type'], 'model_a_score': sa, 'model_b_score': sb,
                        'max': p['expected_max'], 'deviation': round(dev, 2), 'passed': ok})
        flag = '✓' if ok else '✗ 超偏差'
        print(f'  [{flag}] {p["id"]} {p["type"]:<13} A={sa} vs B={sb} (dev {dev:.2f})')

    passed = sum(1 for r in results if r.get('passed'))
    print(f'\n通过 {passed}/{len(results)} · 偏差 > {DEVIATION_LIMIT} 分触发审查')
    if not MODEL_B_KEY:
        print('⚠️ 未配置 MODEL_B_API_KEY/ZHIPU_API_KEY，模型 B 结果无效')

    report = {
        'generated_at': datetime.now().isoformat(),
        'model_a': model_a,
        'model_b': MODEL_B_MODEL,
        'model_b_note': '默认智谱 GLM-4-flash；标准§五指定 GPT-4.1，配置 MODEL_B_API_KEY/URL/MODEL 即可切换',
        'threshold': DEVIATION_LIMIT,
        'pairs': results, 'passed': passed, 'total': len(results),
    }
    docs = PROJECT_ROOT / 'docs'
    docs.mkdir(exist_ok=True)
    out = docs / f'model_calibration_{datetime.now().strftime("%Y%m%d")}.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[calibrate] 报告已保存: {out}')


if __name__ == '__main__':
    main()
