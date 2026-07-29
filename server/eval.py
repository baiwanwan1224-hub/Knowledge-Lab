#!/usr/bin/env python3
"""LLM Cross-Evaluation Script · Quiz Quality + Speed + Cost Benchmark"""
import os, sys, json, time, yaml, hashlib, subprocess
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICING_FILE = os.path.join(PROJECT_ROOT, 'pricing.yaml')
GEN_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quiz_generator.py')

def load_pricing():
    with open(PRICING_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)['models']

def qa_check(questions: list) -> dict:
    """L0-003 QA Gate: automated checks per question (normalized by question type)."""
    total, passed = 0, 0
    details = []
    for q in questions:
        score, issues = 0, []
        is_choice = q.get('type') == 'single_choice'
        max_score = 5 if is_choice else 3
        if q.get('question') and len(q['question']) >= 10: score += 1
        else: issues.append('question_too_short')
        if q.get('explanation') and len(q['explanation']) >= 10: score += 1
        else: issues.append('explanation_too_short')
        if is_choice:
            opts = q.get('options', [])
            if len(opts) == 4: score += 1
            else: issues.append(f'expected 4 options, got {len(opts)}')
            if q.get('correct_answer') in [o.get('label','') for o in opts]: score += 1
            else: issues.append('answer_not_in_options')
        if q.get('knowledge_point'): score += 1
        else: issues.append('missing_knowledge_point')
        qs = score / max_score
        details.append({'question': q.get('question','')[:80], 'quality_score': round(qs,2), 'passed': qs >= 0.6, 'issues': issues})
        total += 1
        if qs >= 0.6: passed += 1
    return {'total': total, 'passed': passed, 'pass_rate': round(passed/total*100,1) if total > 0 else 0, 'details': details}

def run_benchmark(topic: str = "AI产品策略", count: int = 5, difficulty: str = "medium"):
    """Run quiz generation benchmark for all configured models."""
    pricing = load_pricing()
    results = []

    # Test topics for consistency
    test_configs = [
        {'topic': topic, 'count': count, 'difficulty': difficulty},
        {'topic': '产品设计', 'count': 3, 'difficulty': 'easy'},
        {'topic': '增长实验', 'count': 3, 'difficulty': 'hard'},
    ]

    for model_name, price_info in pricing.items():
        model_results = []
        for cfg in test_configs:
            # Warm-up (not counted)
            _ = _gen_quiz(cfg['topic'], cfg['count'], cfg['difficulty'], model_name)

            # Measured run
            t0 = time.time()
            data = _gen_quiz(cfg['topic'], cfg['count'], cfg['difficulty'], model_name)
            latency = time.time() - t0

            if data and 'questions' in data:
                qa = qa_check(data['questions'])
                questions = data['questions']
                prompt_tokens = data.get('usage', {}).get('prompt_tokens', 500)
                completion_tokens = data.get('usage', {}).get('completion_tokens', 800)
            else:
                qa = {'total': 0, 'passed': 0, 'pass_rate': 0, 'details': []}
                questions = []
                prompt_tokens = 500
                completion_tokens = 800

            # Cached run
            t1 = time.time()
            _gen_quiz(cfg['topic'], cfg['count'], cfg['difficulty'], model_name)
            cached_latency = time.time() - t1

            cost = (prompt_tokens/1e6)*price_info['input_cost'] + (completion_tokens/1e6)*price_info['output_cost']

            model_results.append({
                'config': cfg,
                'questions_count': len(questions),
                'qa': qa,
                'latency_s': round(latency, 2),
                'cached_latency_ms': round(cached_latency * 1000, 1),
                'speedup': f"{round(latency/cached_latency, 1)}x" if cached_latency > 0 else "N/A",
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'cost_usd': round(cost, 6),
                'cost_100q_usd': round(cost * 100 / cfg['count'], 2),
            })

        avg_qa = round(sum(r['qa']['pass_rate'] for r in model_results) / len(model_results), 1) if model_results else 0
        avg_latency = round(sum(r['latency_s'] for r in model_results) / len(model_results), 2) if model_results else 0
        avg_cost = round(sum(r['cost_usd'] for r in model_results) / len(model_results), 6) if model_results else 0

        results.append({
            'model': model_name,
            'provider': price_info['provider'],
            'input_cost_per_1m': price_info['input_cost'],
            'output_cost_per_1m': price_info['output_cost'],
            'avg_qa_pass_rate': avg_qa,
            'avg_latency_s': avg_latency,
            'avg_cost_per_q': avg_cost,
            'cost_100q': round(avg_cost * 100, 2),
            'details': model_results,
        })

    return results

def _gen_quiz(topic: str, count: int, difficulty: str, model: str = None):
    """Internal: call quiz_generator.py via subprocess."""
    try:
        env = os.environ.copy()
        if model:
            env['LLM_MODEL'] = model
        result = subprocess.run(
            ['python', GEN_SCRIPT, '--topic', topic, '--count', str(count), '--difficulty', difficulty],
            capture_output=True, text=True, timeout=120,
            cwd=os.path.dirname(os.path.abspath(__file__)), env=env)
        return json.loads(result.stdout) if result.stdout else None
    except:
        return None

if __name__ == '__main__':
    results = run_benchmark()
    print(json.dumps(results, ensure_ascii=False, indent=2))
