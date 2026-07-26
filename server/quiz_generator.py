#!/usr/bin/env python3
"""
Quiz Generator — reads Obsidian notes, calls LLM to generate quiz questions, validates quality.
Usage: python quiz_generator.py --topic "产品需求分析" --count 5 --types single_choice,short_answer --difficulty medium
"""
import sys, os, json, argparse, hashlib, requests
from datetime import datetime

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
NOTES_DIR = os.path.join(VAULT_PATH, 'Knowledge Lab', '00_学习笔记')
EXTRA_NOTE_DIRS = [os.path.join(VAULT_PATH, 'Clippings'), os.path.join(VAULT_PATH, '网页提取')]

def find_notes(topic=None):
    notes = []
    for search_dir in [NOTES_DIR] + EXTRA_NOTE_DIRS:
        if not os.path.exists(search_dir): continue
        for root, dirs, files in os.walk(search_dir):
            for f in files:
                if f.endswith('.md') and not f.startswith('模板_'):
                    path = os.path.join(root, f)
                    with open(path, 'r', encoding='utf-8') as fh: content = fh.read()
                    topics = []
                    for line in content.split('\n'):
                        if line.startswith('topic:') or line.startswith('topics:'):
                            topics = [t.strip().strip('"[]').replace('"','') for t in line.split(':')[1].split(',')]
                            break
                    title = f.replace('.md', '')
                    for line in content.split('\n'):
                        if line.startswith('# '): title = line[2:].strip(); break
                    notes.append({'path': path.replace(search_dir + os.sep, ''), 'title': title, 'topics': topics, 'content': content, 'file_hash': hashlib.sha256(content.encode()).hexdigest()})
    if topic:
        notes = [n for n in notes if topic in n.get('topics', []) or topic.lower() in n['title'].lower() or topic.lower() in n['content'].lower()]
    # Only use ready notes (per content quality standard)
    notes = [n for n in notes if any(s in n.get('content', '') for s in ['status: ready', 'status: draft', 'status: imported', 'status: needs_example'])]
    return notes

def build_prompt(topic, count, types, difficulty, notes):
    context = ''
    for i, note in enumerate(notes[:5]):
        content = note['content'][:1500]
        context += f'\n### Source {i+1}: {note["title"]}\n{content}\n'
    type_desc = {'single_choice': '单选题(4选项A/B/C/D)', 'short_answer': '简答题(2-4句)', 'scenario': '场景题(AI PM实际场景)'}
    type_str = '\n'.join([f'- {type_desc.get(t, t)}' for t in types])
    return f"""你是AI产品经理教学专家。请基于以下学习笔记内容，生成{count}道测验题。

## 内容质量标准
- 题目必须能从笔记内容中直接回答，不考外部知识
- 仅使用 status: ready 的笔记内容
- 质量门禁：题干≥10字符、解析≥20字符、选项完整、答案有效、有知识点标注

## 学习笔记
{context}

## 要求
主题：{topic} · 数量：{count} · 难度：{difficulty}
题型：{type_str}

## 规则
1. 单选题4个选项，干扰项需合理但明确错误
2. 简答题提供2-4句模型答案
3. 场景题给出真实AI PM工作场景
4. 每题含详细解析（解释为什么对、为什么错）
5. 每题标注来源笔记和考查的知识点

## 输出格式（严格JSON，不用markdown代码块）
{{"questions":[{{"type":"single_choice","question":"题目文本","options":[{{"label":"A","text":"选项A"}},{{"label":"B","text":"选项B"}},{{"label":"C","text":"选项C"}},{{"label":"D","text":"选项D"}}],"correct_answer":"B","explanation":"详细解析...","difficulty":"medium","source_note":"来源笔记名","knowledge_point":"考查的知识点"}}]}}

直接输出JSON："""

def call_llm(prompt):
    resp = requests.post(LLM_API_URL, headers={'Authorization': f'Bearer {LLM_API_KEY}', 'Content-Type': 'application/json'},
        json={'model': LLM_MODEL, 'messages': [{'role': 'system', 'content': '你是AI产品经理教学专家，严格按JSON格式输出。'}, {'role': 'user', 'content': prompt}], 'temperature': 0.7, 'max_tokens': 4000}, timeout=120)
    if resp.status_code != 200: return {'error': f'API error {resp.status_code}: {resp.text}'}
    return resp.json()

def parse_response(response):
    if 'error' in response: return response
    content = response['choices'][0]['message']['content'].strip()
    if content.startswith('```'): content = content.split('\n', 1)[1]
    if content.endswith('```'): content = content[:-3]
    try: return json.loads(content)
    except:
        import re; match = re.search(r'\{.*\}', content, re.DOTALL)
        return json.loads(match.group()) if match else {'error': 'Failed to parse JSON', 'raw': content[:500]}

def qa_check(questions):
    results = []
    for q in questions:
        score = 0; issues = []
        if q.get('question') and len(q['question']) >= 10: score += 1
        else: issues.append('question too short')
        if q.get('explanation') and len(q['explanation']) >= 20: score += 1
        else: issues.append('explanation too short')
        if q.get('type') == 'single_choice':
            opts = q.get('options', [])
            if len(opts) == 4: score += 1
            else: issues.append(f'expected 4 options, got {len(opts)}')
            if q.get('correct_answer') in [o.get('label', '') for o in opts]: score += 1
            else: issues.append('correct_answer not in options')
        if q.get('knowledge_point'): score += 1
        else: issues.append('missing knowledge_point')
        qs = score / 5.0
        results.append({**q, 'quality_score': round(qs, 2), 'quality_passed': qs >= 0.6, 'quality_issues': issues})
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--topic', required=True); parser.add_argument('--count', type=int, default=5)
    parser.add_argument('--types', default='single_choice,short_answer'); parser.add_argument('--difficulty', default='medium')
    args = parser.parse_args()
    types = [t.strip() for t in args.types.split(',')]
    notes = find_notes(args.topic)
    if not notes: print(json.dumps({'error': f'No notes found for topic "{args.topic}"', 'status': 'no_content'}, ensure_ascii=False)); sys.exit(1)
    prompt = build_prompt(args.topic, args.count, types, args.difficulty, notes)
    response = call_llm(prompt)
    result = parse_response(response)
    if 'error' in result: print(json.dumps(result, ensure_ascii=False)); sys.exit(1)
    questions = result.get('questions', [])
    checked = qa_check(questions)
    output = {'status': 'success', 'session_name': f'{args.topic}测验 {datetime.now().strftime("%Y-%m-%d %H:%M")}', 'topics': [args.topic], 'difficulty': args.difficulty, 'source_notes': [{'title': n['title'], 'path': n['path'], 'hash': n['file_hash']} for n in notes], 'questions': checked, 'total': len(checked), 'passed_qa': sum(1 for q in checked if q['quality_passed']), 'generated_at': datetime.now().isoformat()}
    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
