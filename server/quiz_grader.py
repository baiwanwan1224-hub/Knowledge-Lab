#!/usr/bin/env python3
"""
Quiz Grader — grade answers via LLM, generate wrong-answer cards with SM-2 scheduling.
Usage: python quiz_grader.py --input-file /tmp/session.json
"""
import sys, os, json, argparse, requests
from datetime import datetime, timedelta

# Force UTF-8 output on Windows (prevents GBK encoding errors in subprocess)
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Load .env first
_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE, 'r', encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

LLM_API_KEY = os.environ.get('LLM_API_KEY', os.environ.get('LLM_API_KEY', ''))
LLM_API_URL = os.environ.get('LLM_API_URL', 'https://api.deepseek.com/v1/chat/completions')
LLM_MODEL = os.environ.get('LLM_MODEL', 'deepseek-v4-pro')
VAULT_PATH = os.environ.get('VAULT_PATH', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'vault'))
WRONG_ANSWER_DIR = os.path.join(VAULT_PATH, 'Knowledge Lab', '01_错题本')

def grade_answer(question, user_answer):
    q_type = question.get('type', 'short_answer'); correct = question.get('correct_answer', '')
    question_text = question.get('question', ''); explanation = question.get('explanation', '')
    prompt = f"""你是AI产品经理教学专家。严格按评分标准打分。

## 题目
类型：{q_type}
题目：{question_text}
标准答案/解析：{correct} | {explanation}
学生答案：{user_answer}

## 评分标准
- 单选题：选项标签完全匹配，选对=1.0，选错=0
- 简答题(0-5)：5=优秀(含案例)/4=良好(覆盖要点)/3=及格(有缺漏)/2=不足/1=错误/0=离题
- 场景题(0-5)：5=问题识别+方案+利益相关者/4=识别+方案/3=部分理解/2=浅层/1=偏题/0=无关
- 质量阈值：单题得分<60%标准分→标记为错题
- 输出格式（严格JSON）：{{"score":3.5,"max_score":5.0,"is_correct":false,"feedback":"反馈...","strengths":[],"gaps":[],"weakness_tags":[],"misunderstanding":"","suggested_review":"","confidence":0.85}}
- weakness_tags可选：概念理解不清、缺少具体案例、框架不完整、分析深度不足、表述不够精准、完全错误"""
    resp = requests.post(LLM_API_URL, headers={'Authorization': f'Bearer {LLM_API_KEY}', 'Content-Type': 'application/json'},
        json={'model': LLM_MODEL, 'messages': [{'role': 'system', 'content': '严格但公平的评分专家。严格按JSON格式输出。'}, {'role': 'user', 'content': prompt}], 'temperature': 0.3, 'max_tokens': 1500}, timeout=60)
    if resp.status_code != 200: return {'error': f'API error {resp.status_code}'}
    content = resp.json()['choices'][0]['message']['content'].strip()
    if content.startswith('```'): content = content.split('\n', 1)[1]
    if content.endswith('```'): content = content[:-3]
    try: return json.loads(content)
    except:
        import re; match = re.search(r'\{.*\}', content, re.DOTALL)
        return json.loads(match.group()) if match else {'error': 'JSON parse failed', 'raw': content[:300]}

def sm2_schedule(score, max_score=5.0, review_count=0, current_interval=1, ease_factor=2.5):
    quality = (score / max_score) * 5
    if quality >= 3:
        if review_count == 0: interval, ease = 1, 2.5
        elif review_count == 1: interval, ease = 6, 2.5
        else: ease = max(1.3, ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))); interval = round(current_interval * ease)
    else: interval, ease = 1, ease_factor
    next_review = datetime.now() + timedelta(days=interval)
    return {'next_review_at': next_review.isoformat(), 'review_interval_days': interval, 'ease_factor': round(ease, 2), 'review_count': review_count + 1}

def write_wrong_answer_card(question, user_answer, grade_result, sm2, source_note, session_uuid):
    topics = question.get('source_topics', [question.get('knowledge_point', '未分类')])
    if isinstance(topics, str): topics = [topics]
    topic_dir = topics[0].replace('/', '-').replace(' ', '-') if topics else '未分类'
    safe_title = question.get('question', 'unknown')[:40].replace('/', '-').replace(':', '-')
    date_str = datetime.now().strftime('%Y-%m-%d')
    os.makedirs(os.path.join(WRONG_ANSWER_DIR, topic_dir), exist_ok=True)
    card = f"""---
type: wrong-answer
question_id: {question.get('id', '')}
session_uuid: {session_uuid}
topics: {json.dumps(topics, ensure_ascii=False)}
weakness_tags: {json.dumps(grade_result.get('weakness_tags', []), ensure_ascii=False)}
difficulty: {question.get('difficulty', 'medium')}
score: {grade_result.get('score', 0)}
review_count: {sm2['review_count']}
next_review: {sm2['next_review_at']}
ease_factor: {sm2['ease_factor']}
created: {date_str}
---

# 错题：{safe_title}

## 原题
> {question.get('question', '')}

## 我的答案
{user_answer}

## 正确答案
{question.get('correct_answer', '')}

## 解析
{question.get('explanation', '')}

## 我的薄弱点
{grade_result.get('misunderstanding', '')}

## 反馈
{grade_result.get('feedback', '')}

## 知识点链接
- 来源笔记：[[{source_note}]]
- 考查知识点：{question.get('knowledge_point', '')}

## 复习记录
| 次数 | 日期 | 掌握程度 |
|------|------|----------|
| 1 | {date_str} | 初次错误 |
"""
    filename = f'错题_{date_str}_{safe_title}.md'; filepath = os.path.join(WRONG_ANSWER_DIR, topic_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f: f.write(card)
    return filepath

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default=None); parser.add_argument('--input-file', default=None)
    args = parser.parse_args()
    if args.input_file:
        with open(args.input_file, 'r', encoding='utf-8') as f: data = json.load(f)
    elif args.input: data = json.loads(args.input)
    else: print(json.dumps({'error': 'Need --input or --input-file', 'status': 'error'})); sys.exit(1)
    session_uuid = data.get('session_uuid', ''); questions = data.get('questions', [])
    answers = data.get('answers', []); source_notes = data.get('source_notes', [])
    results = []; total_score = 0; total_max = 0; wrong_count = 0
    for i, (q, a) in enumerate(zip(questions, answers)):
        grade = grade_answer(q, a)
        if 'error' in grade: results.append({'question_index': i, 'error': grade['error']}); continue
        is_wrong = grade.get('score', 0) < (grade.get('max_score', 5) * 0.6)
        sm2 = {}
        if is_wrong:
            sm2 = sm2_schedule(grade.get('score', 0), grade.get('max_score', 5))
            source_note = source_notes[0]['title'] if source_notes else q.get('knowledge_point', '')
            obsidian_path = write_wrong_answer_card(q, a, grade, sm2, source_note, session_uuid)
            sm2['obsidian_path'] = obsidian_path; wrong_count += 1
        total_score += grade.get('score', 0); total_max += grade.get('max_score', 5)
        results.append({'question_index': i, 'question_text': q.get('question', '')[:100], 'user_answer': a[:200], **grade, 'sm2': sm2 if sm2 else None, 'is_wrong': is_wrong})
    output = {'status': 'success', 'session_uuid': session_uuid, 'total_score': round(total_score, 1), 'total_max': total_max, 'score_pct': round(total_score / total_max * 100, 1) if total_max > 0 else 0, 'total_questions': len(questions), 'correct_count': len(questions) - wrong_count, 'wrong_count': wrong_count, 'results': results, 'graded_at': datetime.now().isoformat()}
    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
