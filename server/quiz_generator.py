#!/usr/bin/env python3
"""
Quiz Generator — reads Obsidian notes, calls LLM to generate quiz questions, validates quality.
Usage: python quiz_generator.py --topic "产品需求分析" --count 5 --types single_choice,short_answer --difficulty medium
"""
import sys, os, json, argparse, hashlib, requests
from datetime import datetime

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
NOTES_DIR = os.path.join(VAULT_PATH, 'Knowledge Lab', '00_学习笔记')
EXTRA_NOTE_DIRS = [os.path.join(VAULT_PATH, 'Clippings'), os.path.join(VAULT_PATH, '网页提取')]

def _rag_enhance(topic, scanned_notes):
    """Opt-in semantic retrieval (RAG_RETRIEVAL=1): find notes whose chunks are
    semantically relevant to the topic even when keyword/tag matching misses them.
    Returns a set of note basenames to merge into the matched set."""
    if os.environ.get('RAG_RETRIEVAL', '') != '1':
        return set()
    try:
        from rag_index import load_index, retrieve
        try:
            load_index()
        except Exception as e:
            print(f'[RAG] 索引不存在，跳过语义检索（先运行 python -m server.rag_index build）: {e}', file=sys.stderr)
            return set()
        chunks = retrieve(topic, top_k=5, retriever='hybrid')
        if not chunks:
            return set()
        # Match by basename: rag_index paths are VAULT-relative, quiz paths are dir-relative.
        return {os.path.basename(c['note_path']) for c in chunks}
    except Exception as e:
        print(f'[RAG] 语义检索失败: {e}', file=sys.stderr)
        return set()


def _memory_enhance(topic, store=None):
    """Opt-in learner memory injection (MEMORY_ENABLE=1): read the learner's
    long-term memory (progress / decisions / open questions) from
    data/memory_store.json and return a prompt snippet for build_prompt.
    Returns '' when disabled, no memory, or on any error (出题不受影响)."""
    if os.environ.get('MEMORY_ENABLE', '') != '1':
        return ''
    try:
        from memory_core import MemoryStore
        mem = (store or MemoryStore()).get('learner')
        if not mem:
            return ''
        parts = []
        if mem.get('summary'):
            parts.append(f"- 学习进展: {mem['summary']}")
        if mem.get('decisions'):
            parts.append('- 已确定事项: ' + '; '.join(mem['decisions']))
        if mem.get('open_questions'):
            parts.append('- 待强化: ' + '; '.join(mem['open_questions']))
        if not parts:
            return ''
        return '\n'.join(parts)
    except Exception as e:
        print(f'[MEMORY] 读取长期记忆失败（不影响出题）: {e}', file=sys.stderr)
        return ''


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
                            raw = line.split(':', 1)[1].strip()
                            # Handle JSON array format: ["tag1", "tag2"]
                            if raw.startswith('['):
                                try:
                                    import json as _json
                                    topics = _json.loads(raw)
                                except Exception:
                                    topics = [t.strip().strip('"[]').replace('"','') for t in raw.split(',')]
                            else:
                                topics = [t.strip().strip('"[]').replace('"','') for t in raw.split(',')]
                            break
                    title = f.replace('.md', '')
                    for line in content.split('\n'):
                        if line.startswith('# '): title = line[2:].strip(); break
                    notes.append({'path': path.replace(search_dir + os.sep, ''), 'title': title, 'topics': topics, 'content': content, 'file_hash': hashlib.sha256(content.encode()).hexdigest()})
    if topic:
        # L0-005: Exact tag match on topics list (RAG-classified)
        matched = [n for n in notes if topic in n.get('topics', [])]
        if not matched:
            # Fallback: try classifier for related topics
            try:
                from classifier import TopicClassifier
                c = TopicClassifier()
                similar_topics = c._vector_filter(topic, top_k=3)
                if similar_topics:
                    matched = [n for n in notes if any(t in n.get('topics', []) for t in similar_topics)]
                else:
                    print(f'[Classifier] No similar topics found for "{topic}"', file=sys.stderr)
            except Exception:
                pass
        if not matched:
            # Last fallback: substring match on title/content
            matched = [n for n in notes if topic.lower() in n['title'].lower() or topic.lower() in n['content'].lower()]
        # RAG semantic enhancement (opt-in): merge semantically relevant notes
        # that keyword/tag matching missed. Default off — existing behavior unchanged.
        rag_basenames = _rag_enhance(topic, notes)
        if rag_basenames:
            seen = {n['path'] for n in matched}
            extra = [n for n in notes
                     if os.path.basename(n['path']) in rag_basenames
                     and n['path'] not in seen
                     and 'status: ready' in n.get('content', '')]
            if extra:
                print(f'[RAG] 语义检索补充 {len(extra)} 篇笔记', file=sys.stderr)
                matched = matched + extra
        notes = matched
    # Quality Gate (L0-003): Only use status: ready notes
    eligible = []
    skipped = 0
    for n in notes:
        content = n.get('content', '')
        if 'status: ready' in content:
            eligible.append(n)
        else:
            skipped += 1
    if skipped > 0:
        print(f'[QualityGate] Skipped {skipped} non-ready notes (only "ready" notes are used for quiz generation)', file=sys.stderr)
    if not eligible and notes:
        print(f'[QualityGate] ERROR: {len(notes)} notes found for topic but 0 are "ready". Use the dashboard to review and approve draft notes.', file=sys.stderr)
    return eligible

def build_prompt(topic, count, types, difficulty, notes, memory_context=''):
    context = ''
    for i, note in enumerate(notes[:10]):
        content = note['content'][:3000]
        context += f'\n### Source {i+1}: {note["title"]}\n{content}\n'
    type_desc = {'single_choice': '单选题(4选项A/B/C/D)', 'short_answer': '简答题(2-4句)', 'scenario': '场景题(AI PM实际场景)'}
    type_str = '\n'.join([f'- {type_desc.get(t, t)}' for t in types])
    memory_block = f'\n## 用户长期记忆（出题参考：侧重薄弱点）\n{memory_context}\n' if memory_context else ''
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
{memory_block}
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
    if not LLM_API_KEY:
        return {'error': 'LLM_API_KEY not configured — set it in .env'}
    try:
        resp = requests.post(LLM_API_URL, headers={'Authorization': f'Bearer {LLM_API_KEY}', 'Content-Type': 'application/json'},
            json={'model': LLM_MODEL, 'messages': [{'role': 'system', 'content': '你是AI产品经理教学专家，严格按JSON格式输出。'}, {'role': 'user', 'content': prompt}], 'temperature': 0.7, 'max_tokens': 6000}, timeout=120)
        if resp.status_code != 200: return {'error': f'API error {resp.status_code}: {resp.text}'}
        return resp.json()
    except Exception as e:
        return {'error': f'LLM request failed: {str(e)[:200]}'}

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
        is_choice = q.get('type') == 'single_choice'
        max_score = 5 if is_choice else 3  # non-choice: no option checks
        if q.get('question') and len(q['question']) >= 10: score += 1
        else: issues.append('question too short')
        if q.get('explanation') and len(q['explanation']) >= 10: score += 1
        else: issues.append('explanation too short')
        if is_choice:
            opts = q.get('options', [])
            if len(opts) == 4: score += 1
            else: issues.append(f'expected 4 options, got {len(opts)}')
            if q.get('correct_answer') in [o.get('label', '') for o in opts]: score += 1
            else: issues.append('correct_answer not in options')
        if q.get('knowledge_point'): score += 1
        else: issues.append('missing knowledge_point')
        qs = score / max_score
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
    memory_context = _memory_enhance(args.topic)
    prompt = build_prompt(args.topic, args.count, types, args.difficulty, notes, memory_context)
    response = call_llm(prompt)
    result = parse_response(response)
    if 'error' in result: print(json.dumps(result, ensure_ascii=False)); sys.exit(1)
    questions = result.get('questions', [])
    if not questions:
        # Log raw LLM response for debugging empty questions
        raw_content = response.get('choices', [{}])[0].get('message', {}).get('content', '')[:800]
        print(f'[DEBUG] LLM returned 0 questions. Raw content (first 800 chars):\n{raw_content}', file=sys.stderr)
    checked = qa_check(questions)
    # Collect actual topics from matched notes (not the query string — may be empty)
    session_topics = set()
    for n in notes:
        for t in n.get('topics', []):
            if t and t.strip():
                session_topics.add(t.strip())
    if not session_topics and args.topic:
        session_topics.add(args.topic)
    output = {'status': 'success', 'session_name': f'{args.topic or "随机"}测验 {datetime.now().strftime("%Y-%m-%d %H:%M")}', 'topics': list(session_topics)[:5], 'difficulty': args.difficulty, 'source_notes': [{'title': n['title'], 'path': n['path'], 'hash': n['file_hash']} for n in notes], 'questions': checked, 'total': len(checked), 'passed_qa': sum(1 for q in checked if q['quality_passed']), 'generated_at': datetime.now().isoformat()}
    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
