#!/usr/bin/env python3
"""
Knowledge Lab · Quiz API Server
HTTP API for quiz generation, grading, note management, competency assessment.
"""
import json, sys, os, subprocess, hashlib, uuid, re, requests, tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
from collections import defaultdict

# === CONFIG (all from env vars) ===
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
if not DEEPSEEK_API_KEY:
    print('[WARN] DEEPSEEK_API_KEY not set. Quiz generation/grading will fail.')
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'
DEEPSEEK_MODEL = 'deepseek-v4-pro'

# PostgreSQL (optional)
try:
    import psycopg2; import psycopg2.extras
    HAS_PG = True
except ImportError:
    HAS_PG = False

PG_CONFIG = {
    'host': os.environ.get('PG_HOST', 'localhost'),
    'port': int(os.environ.get('PG_PORT', '5432')),
    'dbname': os.environ.get('PG_DATABASE', 'n8n_scraper'),
    'user': os.environ.get('PG_USER', 'n8n'),
    'password': os.environ.get('PG_PASSWORD', ''),
}

# Paths
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_BASE = os.environ.get('VAULT_PATH', os.path.join(os.path.dirname(SCRIPTS_DIR), 'vault'))
NOTES_DIR = os.path.join(VAULT_BASE, '00_学习笔记')
WRONG_DIR = os.path.join(VAULT_BASE, '01_错题本')
STANDARDS_DIR = os.path.join(VAULT_BASE, '06_产品层')

# === DATABASE ===
def get_db():
    if not HAS_PG: return None
    return psycopg2.connect(**PG_CONFIG)

def json_safe(val):
    from decimal import Decimal
    if isinstance(val, Decimal): return float(val)
    if isinstance(val, datetime): return val.isoformat()
    return val

def db_exec(sql, params=None, fetch=True):
    if not HAS_PG: return []
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute(sql, params or ())
        if fetch and cur.description:
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, [json_safe(v) for v in row])) for row in cur.fetchall()]
        else:
            conn.commit(); rows = []
        cur.close(); conn.close()
        return rows
    except Exception as e:
        print(f'DB Error: {e}')
        return []

def save_session(session_uuid, session_name, topics, difficulty, total):
    db_exec("""INSERT INTO quiz_sessions (session_uuid, session_name, topics, question_types, question_count, difficulty, status, total_questions, started_at)
               VALUES (%s, %s, %s, %s, %s, %s, 'ready', %s, NOW())""",
            (session_uuid, session_name, json.dumps(topics), json.dumps(['single_choice','short_answer']), total, difficulty), fetch=False)

def save_answer(session_uuid, question_text, user_answer, score, max_score, is_correct, feedback, weakness_tags, misunderstanding):
    db_exec("""INSERT INTO answers (session_id, question_id, user_answer, score, max_score, is_correct, grader_feedback, weakness_tags, misunderstanding, answer_timestamp)
               SELECT qs.id, q.id, %s, %s, %s, %s, %s, %s, %s, NOW()
               FROM quiz_sessions qs, questions q
               WHERE qs.session_uuid = %s AND q.question_text = %s LIMIT 1""",
            (user_answer[:500], score, max_score, is_correct, feedback[:2000], json.dumps(weakness_tags), misunderstanding[:500], session_uuid, question_text[:300]), fetch=False)

# === STANDARDS ===
STANDARDS = {}

def load_standards():
    global STANDARDS
    if not os.path.exists(STANDARDS_DIR):
        print(f'[WARN] Standards directory not found: {STANDARDS_DIR}')
        return
    for fname in sorted(os.listdir(STANDARDS_DIR)):
        if fname.startswith('_STANDARD_') and fname.endswith('.md'):
            fpath = os.path.join(STANDARDS_DIR, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f: content = f.read()
                fm = {}; body = content
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        for line in parts[1].split('\n'):
                            if ':' in line: k, v = line.split(':', 1); fm[k.strip()] = v.strip()
                        body = parts[2]
                key = fname.replace('.md', '')
                STANDARDS[key] = {'frontmatter': fm, 'body': body.strip(), 'version': fm.get('version', '0'), 'title': fm.get('title', ''), 'file': fname}
                print(f'[STANDARD] Loaded {fname} v{fm.get("version","?")}')
            except Exception as e:
                print(f'[WARN] Failed to load {fname}: {e}')

def get_standard(name):
    return STANDARDS.get(name, {}).get('body', '')

def get_standard_version(name):
    return STANDARDS.get(name, {}).get('version', '0')

load_standards()

# === SERVER ===
class QuizHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))

    def do_OPTIONS(self):
        self._send_json({}, 200)

    def do_POST(self):
        path = urlparse(self.path).path
        content_type = self.headers.get('Content-Type', '')
        length = int(self.headers.get('Content-Length', 0))
        if 'multipart/form-data' in content_type:
            raw_body = self.rfile.read(length) if length > 0 else b''
            if path == '/notes/upload': self._handle_upload_file(raw_body, content_type)
            else: self._send_json({'error': 'Unexpected file upload'}, 400)
            return
        body = json.loads(self.rfile.read(length)) if length > 0 else {}
        if path == '/quiz/generate': self._handle_generate(body)
        elif path == '/quiz/grade': self._handle_grade(body)
        elif path == '/notes/import': self._handle_import_url(body)
        elif path == '/notes/verify': self._handle_verify_note(body)
        elif path == '/notes/delete': self._handle_delete_note(body)
        elif path == '/notes/transcribe': self._handle_transcribe(body)
        else: self._send_json({'error': 'Not found', 'path': path}, 404)

    def do_GET(self):
        parsed = urlparse(self.path); path = parsed.path
        if path == '/': self._serve_dashboard()
        elif path == '/health': self._send_json({'status': 'ok', 'time': datetime.now().isoformat(), 'pg': HAS_PG})
        elif path == '/topics': self._handle_topics()
        elif path == '/notes': self._handle_notes()
        elif path == '/note': self._handle_note(parsed)
        elif path == '/notes/drafts': self._handle_drafts()
        elif path == '/competency': self._handle_competency()
        elif path == '/history': self._handle_history()
        elif path == '/wrong-answers': self._handle_wrong_answers()
        elif path == '/dashboard': self._handle_dashboard()
        else: self._send_json({'error': 'Not found'}, 404)

    def _serve_dashboard(self):
        html_path = os.path.join(os.path.dirname(SCRIPTS_DIR), 'dashboard', 'dashboard_v2.html')
        try:
            with open(html_path, 'r', encoding='utf-8') as f: html = f.read()
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        except FileNotFoundError:
            self._send_json({'error': 'dashboard_v2.html not found'}, 404)

    # -- Generate --
    def _handle_generate(self, body):
        topic = body.get('topic', 'AI'); count = body.get('question_count', 5)
        types = ','.join(body.get('types', ['single_choice', 'short_answer']))
        difficulty = body.get('difficulty', 'medium')
        script = os.path.join(SCRIPTS_DIR, 'quiz_generator.py')
        cmd = f'{sys.executable} "{script}" --topic "{topic}" --count {count} --types {types} --difficulty {difficulty}'
        try:
            env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'}
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600, encoding='utf-8', errors='replace', cwd=SCRIPTS_DIR, env=env)
            data = json.loads(result.stdout) if result.returncode == 0 else (json.loads(result.stdout) if result.stdout else {'error': result.stderr or 'Unknown error'})
            if 'error' in data:
                self._send_json(data, 500); return
            session_uuid = hashlib.md5(f'{topic}{datetime.now().isoformat()}'.encode()).hexdigest()[:16]
            data['session_uuid'] = session_uuid
            if HAS_PG: save_session(session_uuid, data.get('session_name', f'{topic}测验'), data.get('topics', [topic]), difficulty, data.get('total', 0))
            self._send_json(data)
        except subprocess.TimeoutExpired:
            self._send_json({'error': 'Generation timed out'}, 504)
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    # -- Grade --
    def _handle_grade(self, body):
        script = os.path.join(SCRIPTS_DIR, 'quiz_grader.py')
        input_json = json.dumps(body, ensure_ascii=False)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write(input_json); tmp_path = f.name
        try:
            cmd = f'{sys.executable} "{script}" --input-file "{tmp_path}"'
            env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'}
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600, encoding='utf-8', errors='replace', cwd=SCRIPTS_DIR, env=env)
            data = json.loads(result.stdout) if result.returncode == 0 else (json.loads(result.stdout) if result.stdout else {'error': result.stderr or 'Unknown error'})
            if HAS_PG:
                session_uuid = body.get('session_uuid', '')
                questions = body.get('questions', []); answers = body.get('answers', [])
                for i, res in enumerate(data.get('results', [])):
                    q_text = questions[i].get('question', '') if i < len(questions) else ''
                    save_answer(session_uuid, q_text, answers[i][:500] if i < len(answers) else '', res.get('score', 0), res.get('max_score', 5), not res.get('is_wrong', True), res.get('feedback', ''), res.get('weakness_tags', []), res.get('misunderstanding', ''))
                db_exec("""UPDATE quiz_sessions SET status='completed', score_percentage=%s, questions_correct=%s, questions_wrong=%s, completed_at=NOW() WHERE session_uuid=%s""",
                        (data.get('score_pct', 0), data.get('correct_count', 0), data.get('wrong_count', 0), session_uuid), fetch=False)
            self._send_json(data)
        except subprocess.TimeoutExpired:
            self._send_json({'error': 'Grading timed out'}, 504)
        except Exception as e:
            self._send_json({'error': str(e)}, 500)
        finally:
            try: os.unlink(tmp_path)
            except: pass

    # -- Topics --
    def _handle_topics(self):
        topics = set(); note_count = 0
        try:
            for f in os.listdir(NOTES_DIR):
                if f.endswith('.md') and not f.startswith('模板'):
                    note_count += 1
                    try:
                        with open(os.path.join(NOTES_DIR, f), 'r', encoding='utf-8') as fh:
                            for line in fh:
                                if line.startswith('topic:') or line.startswith('topics:'):
                                    raw = line.split(':', 1)[1].strip().strip('"[]')
                                    for t in raw.split(','): topics.add(t.strip())
                                    break
                    except: pass
            self._send_json({'topics': sorted(list(topics)), 'notes_count': note_count})
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    # -- Notes list --
    def _handle_notes(self):
        notes = []
        try:
            for fname in sorted(os.listdir(NOTES_DIR), reverse=True):
                if fname.endswith('.md') and not fname.startswith('模板'):
                    fpath = os.path.join(NOTES_DIR, fname)
                    with open(fpath, 'r', encoding='utf-8') as fh: content = fh.read()
                    title = fname.replace('.md', ''); topics = []; status = 'ready'
                    for line in content.split('\n'):
                        if line.startswith('topic:') or line.startswith('topics:'):
                            raw = line.split(':', 1)[1].strip().strip('"[]')
                            topics = [t.strip() for t in raw.split(',') if t.strip()]
                        if line.startswith('status:'): status = line.split(':', 1)[1].strip()
                        if line.startswith('# '): title = line[2:].strip()
                    body = content.split('---', 2)[-1] if content.startswith('---') else content
                    preview = body.strip()[:200].replace('\n', ' ')
                    notes.append({'title': title, 'file': fname, 'topics': topics, 'status': status, 'preview': preview, 'path': fname})
            self._send_json({'notes': notes, 'total': len(notes)})
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    # -- Note detail --
    def _handle_note(self, parsed):
        params = parse_qs(parsed.query); note_path = params.get('path', [None])[0]
        if not note_path: self._send_json({'error': 'Missing ?path=filename.md'}, 400); return
        full_path = os.path.join(NOTES_DIR, note_path)
        if not os.path.realpath(full_path).startswith(os.path.realpath(NOTES_DIR)):
            self._send_json({'error': 'Invalid path'}, 403); return
        try:
            with open(full_path, 'r', encoding='utf-8') as fh: content = fh.read()
            fm = {}; body = content
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    for line in parts[1].split('\n'):
                        if ':' in line: k, v = line.split(':', 1); fm[k.strip()] = v.strip()
                    body = parts[2]
            self._send_json({'file': note_path, 'frontmatter': fm, 'content': body.strip(), 'raw': content})
        except FileNotFoundError:
            self._send_json({'error': f'Note not found: {note_path}'}, 404)
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    # -- Verify note --
    def _handle_verify_note(self, body):
        file_name = body.get('file', '').strip(); action = body.get('action', 'approve')
        if not file_name: self._send_json({'error': 'Missing file'}, 400); return
        fpath = os.path.join(NOTES_DIR, file_name)
        if not os.path.exists(fpath): self._send_json({'error': f'Note not found: {file_name}'}, 404); return
        try:
            with open(fpath, 'r', encoding='utf-8') as f: content = f.read()
            if action == 'approve':
                new_content = re.sub(r'status:\s*draft', 'status: ready', content)
                new_content = re.sub(r'verified:\s*.*', f'verified: {datetime.now().strftime("%Y-%m-%d")}', new_content)
                if 'verified:' not in new_content: new_content = new_content.replace('status: ready', f'status: ready\nverified: {datetime.now().strftime("%Y-%m-%d")}')
            elif action == 'reject':
                new_content = re.sub(r'status:\s*draft', 'status: needs_revision', content)
            else:
                self._send_json({'error': f'Unknown action: {action}'}, 400); return
            with open(fpath, 'w', encoding='utf-8') as f: f.write(new_content)
            self._send_json({'status': 'success', 'file': file_name, 'new_status': 'ready' if action == 'approve' else 'needs_revision'})
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    # -- Delete note --
    def _handle_delete_note(self, body):
        file_name = body.get('file', '').strip()
        if not file_name: self._send_json({'error': 'Missing file'}, 400); return
        fpath = os.path.join(NOTES_DIR, file_name)
        if not os.path.realpath(fpath).startswith(os.path.realpath(NOTES_DIR)):
            self._send_json({'error': 'Invalid file path'}, 403); return
        if not os.path.exists(fpath): self._send_json({'error': f'Note not found: {file_name}'}, 404); return
        try:
            os.remove(fpath)
            self._send_json({'status': 'deleted', 'file': file_name})
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    # -- Drafts --
    def _handle_drafts(self):
        drafts = []
        try:
            for fname in os.listdir(NOTES_DIR):
                if fname.endswith('.md') and not fname.startswith('模板'):
                    fpath = os.path.join(NOTES_DIR, fname)
                    with open(fpath, 'r', encoding='utf-8') as f: content = f.read()
                    if 'status: draft' in content or 'status: needs_revision' in content:
                        title = fname.replace('.md', ''); topics = []; source_url = ''; status = 'draft'
                        for line in content.split('\n'):
                            if line.startswith('topic:') or line.startswith('topics:'):
                                raw = line.split(':', 1)[1].strip().strip('"[]')
                                topics = [t.strip() for t in raw.split(',') if t.strip()]
                            if line.startswith('source_url:'): source_url = line.split(':', 1)[1].strip()
                            if line.startswith('status:'): status = line.split(':', 1)[1].strip()
                            if line.startswith('# '): title = line[2:].strip()
                        drafts.append({'title': title, 'file': fname, 'topics': topics, 'source_url': source_url, 'status': status})
            self._send_json({'drafts': drafts, 'total': len(drafts)})
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    # -- Import URL --
    def _handle_import_url(self, body):
        url = body.get('url', '').strip()
        if not url: self._send_json({'error': '请提供有效的URL'}, 400); return
        is_youtube = 'youtube.com' in url or 'youtu.be' in url
        try:
            resp = requests.get(url, timeout=25, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            if resp.status_code >= 400:
                self._send_json({'error': f'网页返回错误 ({resp.status_code})'}, 500); return
            resp.encoding = resp.apparent_encoding or 'utf-8'; html = resp.text
        except requests.exceptions.Timeout:
            self._send_json({'error': '请求超时'}, 500); return
        except requests.exceptions.ConnectionError:
            self._send_json({'error': '无法连接到该网站'}, 500); return
        except Exception as e:
            self._send_json({'error': f'抓取失败：{str(e)[:100]}'}, 500); return

        if is_youtube:
            video_id = None; yt_match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
            if yt_match: video_id = yt_match.group(1)
            transcript_text = ''
            if video_id:
                try:
                    from youtube_transcript_api import YouTubeTranscriptApi
                    transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['zh-Hans', 'zh', 'en'])
                    transcript_text = ' '.join([t['text'] for t in transcript])
                except: pass
            title_match = re.search(r'<meta\s+name="title"\s+content="([^"]+)"', html, re.IGNORECASE)
            if not title_match: title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
            title = title_match.group(1).replace(' - YouTube', '').strip() if title_match else 'YouTube视频'
            desc_match = re.search(r'"shortDescription":"([^"]+)"', html); desc = desc_match.group(1) if desc_match else ''
            if transcript_text:
                text = f'[YouTube视频·含字幕]\n标题：{title}\n链接：{url}\n\n字幕内容：\n{transcript_text[:6000]}'
            elif desc and len(desc.strip()) > 50:
                text = f'[YouTube视频·无字幕]\n标题：{title}\n描述：{desc}\n链接：{url}\n\n以下内容基于视频简介整理。'
            else:
                self._send_json({'error': '该YouTube视频无字幕且无描述信息，无法自动生成笔记。\n建议：手动观看后撰写笔记，或使用本地文件导入整理好的内容。', 'status': 'no_content'}, 422); return
        else:
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text); text = re.sub(r'\s+', ' ', text).strip()
        if len(text.strip()) < 100:
            self._send_json({'error': '页面内容太少，可能是JS动态加载的页面。建议手动复制内容后使用本地文件导入。', 'status': 'low_content'}, 500); return
        text = text[:8000]

        existing_topics = set()
        for fname in os.listdir(NOTES_DIR):
            if fname.endswith('.md') and not fname.startswith('模板'):
                try:
                    with open(os.path.join(NOTES_DIR, fname), 'r', encoding='utf-8') as fh:
                        for line in fh:
                            if line.startswith('topic:') or line.startswith('topics:'):
                                for t in line.split(':', 1)[1].strip().strip('"[]').split(','):
                                    if t.strip(): existing_topics.add(t.strip())
                                break
                except: pass

        prompt = f"""你是知识管理助手。请阅读以下内容，整理为一篇学习笔记。

## 内容
{text[:6000]}

## 现有主题
{', '.join(sorted(existing_topics)) if existing_topics else 'AI技术理解, 产品设计能力, 商业化思维, 工程协作能力, 评测体系搭建, 数据驱动决策'}

## 任务
1. 整理为一篇结构化学习笔记（Markdown）
2. 从现有主题中选1-2个最匹配的分类

## 输出格式（严格JSON）
{{"title":"标题","topics":["分类1"],"content":"笔记内容...","summary":"一句话摘要"}}"""
        try:
            resp = requests.post(DEEPSEEK_API_URL, headers={'Authorization': f'Bearer {DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'},
                json={'model': DEEPSEEK_MODEL, 'messages': [{'role': 'system', 'content': '严格按JSON格式输出。'}, {'role': 'user', 'content': prompt}], 'temperature': 0.3, 'max_tokens': 4000}, timeout=120)
            if resp.status_code != 200: self._send_json({'error': f'LLM API error: {resp.status_code}'}, 500); return
            content = resp.json()['choices'][0]['message']['content'].strip()
            if content.startswith('```'): content = content.split('\n', 1)[1]
            if content.endswith('```'): content = content[:-3]
            data = json.loads(content)
        except Exception as e:
            self._send_json({'error': f'LLM处理失败: {str(e)[:100]}'}, 500); return

        date_str = datetime.now().strftime('%Y%m%d')
        safe_title = data.get('title', 'imported').replace('/', '-').replace(':', '-')[:40]
        topics = data.get('topics', ['AI产品经理'])
        note = f"""---
type: study-note
source: URL导入
source_url: {url}
topic: {topics[0] if topics else 'AI产品经理'}
topics: {json.dumps(topics, ensure_ascii=False)}
difficulty: medium
status: draft
created: {datetime.now().strftime('%Y-%m-%d')}
imported: {datetime.now().isoformat()}
quality_score: unverified
---

# {data.get('title', 'Imported Note')}

> 来源：{url}
> 导入日期：{datetime.now().strftime('%Y-%m-%d')}
> 状态：待确认（draft）
> 摘要：{data.get('summary', '')}

{data.get('content', '')}
"""
        filename = f'{date_str}_{safe_title}_URL.md'; filepath = os.path.join(NOTES_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f: f.write(note)
        self._send_json({'status': 'success', 'title': data.get('title', ''), 'topics': topics, 'file': filename, 'summary': data.get('summary', '')})

    # -- File upload --
    def _handle_upload_file(self, raw_body, content_type):
        boundary = None
        for part in content_type.split(';'):
            if 'boundary=' in part: boundary = part.split('=', 1)[1].strip('"'); break
        if not boundary: self._send_json({'error': 'No boundary found'}, 400); return
        body = raw_body; boundary_bytes = boundary.encode('utf-8')
        parts = body.split(b'--' + boundary_bytes)
        file_content = None; filename = None
        for part in parts:
            if b'Content-Disposition' not in part: continue
            header_end = part.find(b'\r\n\r\n')
            if header_end < 0: continue
            headers_raw = part[:header_end].decode('utf-8', errors='replace')
            data = part[header_end + 4:]
            if data.endswith(b'\r\n'): data = data[:-2]
            if data.endswith(b'--'): data = data[:-2]
            if 'name="file"' in headers_raw:
                file_content = data
                fn_match = re.search(r'filename="([^"]+)"', headers_raw)
                if fn_match: filename = fn_match.group(1)
        if not file_content or not filename:
            self._send_json({'error': '未找到文件'}, 400); return
        ext = os.path.splitext(filename)[1].lower(); text = ''; source_type = '本地文件'
        if ext == '.pdf':
            try:
                from PyPDF2 import PdfReader; import io
                reader = PdfReader(io.BytesIO(file_content))
                text = '\n'.join(page.extract_text() or '' for page in reader.pages)
                source_type = 'PDF导入'
            except ImportError:
                self._send_json({'error': 'PDF需要PyPDF2: pip install PyPDF2'}, 500); return
            except Exception as e:
                self._send_json({'error': f'PDF解析失败: {str(e)[:100]}'}, 500); return
        elif ext in ['.md', '.txt', '.markdown']:
            text = file_content.decode('utf-8', errors='replace')
            source_type = 'MD导入' if ext == '.md' else 'TXT导入'
        else:
            self._send_json({'error': f'不支持: {ext}。支持 .md/.txt/.pdf'}, 400); return
        if len(text.strip()) < 50:
            self._send_json({'error': '文件内容太少'}, 400); return
        existing_topics = set()
        for fname in os.listdir(NOTES_DIR):
            if fname.endswith('.md') and not fname.startswith('模板'):
                try:
                    with open(os.path.join(NOTES_DIR, fname), 'r', encoding='utf-8') as fh:
                        for line in fh:
                            if line.startswith('topic:') or line.startswith('topics:'):
                                for t in line.split(':', 1)[1].strip().strip('"[]').split(','):
                                    if t.strip(): existing_topics.add(t.strip())
                                break
                except: pass
        prompt = f"""你是知识管理助手。请阅读以下文件内容，整理为一篇学习笔记。

## 内容
{text[:6000]}

## 现有主题
{', '.join(sorted(existing_topics)) if existing_topics else 'AI技术理解, 产品设计能力, 商业化思维, 工程协作能力, 评测体系搭建, 数据驱动决策'}

输出格式（严格JSON）：{{"title":"标题","topics":["分类1"],"content":"笔记...","summary":"摘要"}}"""
        try:
            resp = requests.post(DEEPSEEK_API_URL, headers={'Authorization': f'Bearer {DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'},
                json={'model': DEEPSEEK_MODEL, 'messages': [{'role': 'system', 'content': '严格按JSON格式输出。'}, {'role': 'user', 'content': prompt}], 'temperature': 0.3, 'max_tokens': 4000}, timeout=120)
            if resp.status_code != 200: self._send_json({'error': f'LLM API error: {resp.status_code}'}, 500); return
            content = resp.json()['choices'][0]['message']['content'].strip()
            if content.startswith('```'): content = content.split('\n', 1)[1]
            if content.endswith('```'): content = content[:-3]
            data = json.loads(content)
        except Exception as e:
            self._send_json({'error': f'LLM处理失败: {str(e)[:100]}'}, 500); return
        date_str = datetime.now().strftime('%Y%m%d')
        safe_title = data.get('title', filename)[:40].replace('/', '-').replace(':', '-')
        topics = data.get('topics', ['AI产品经理'])
        note = f"""---
type: study-note
source: {source_type}
source_url: (本地文件: {filename})
topic: {topics[0] if topics else 'AI产品经理'}
topics: {json.dumps(topics, ensure_ascii=False)}
difficulty: medium
status: draft
created: {datetime.now().strftime('%Y-%m-%d')}
imported: {datetime.now().isoformat()}
quality_score: unverified
---

# {data.get('title', 'Imported Note')}

> 来源：本地文件 `{filename}`
> 导入日期：{datetime.now().strftime('%Y-%m-%d')}
> 状态：待确认（draft）

{data.get('content', text[:3000])}
"""
        note_filename = f'{date_str}_{safe_title}_本地.md'; filepath = os.path.join(NOTES_DIR, note_filename)
        with open(filepath, 'w', encoding='utf-8') as f: f.write(note)
        self._send_json({'status': 'success', 'title': data.get('title', ''), 'topics': topics, 'file': note_filename, 'format': ext, 'source': f'本地文件: {filename}'})

    # -- Whisper transcribe --
    def _handle_transcribe(self, body):
        url = body.get('url', '').strip()
        if not url: self._send_json({'error': '请提供视频链接'}, 400); return
        is_yt = 'youtube.com' in url or 'youtu.be' in url
        if not is_yt: self._send_json({'error': '目前仅支持YouTube链接'}, 400); return
        audio_path = None; title = '转录笔记'
        try:
            try:
                import yt_dlp
                with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get('title', '转录笔记')[:80]
            except: pass
            audio_path = os.path.join(tempfile.gettempdir(), f'whisper_audio_{uuid.uuid4().hex[:8]}.wav')
            try:
                opts = {'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}], 'outtmpl': audio_path.replace('.wav', ''), 'quiet': True}
                with yt_dlp.YoutubeDL(opts) as ydl: ydl.download([url])
                base = audio_path.replace('.wav', '')
                for ext in ['.wav', '.m4a', '.opus', '.webm']:
                    if os.path.exists(base + ext): audio_path = base + ext; break
            except Exception as e:
                self._send_json({'error': f'音频下载失败：{str(e)[:150]}'}, 500); return
            if not os.path.exists(audio_path): self._send_json({'error': '音频文件未找到'}, 500); return
            from faster_whisper import WhisperModel
            model = WhisperModel('tiny', device='cpu', compute_type='int8')
            segments, info = model.transcribe(audio_path, beam_size=5, language=None)
            transcript = ' '.join([seg.text for seg in segments])
            if not transcript or len(transcript.strip()) < 20:
                self._send_json({'error': '未能识别到有效语音内容'}, 422); return
            existing_topics = set()
            for fname in os.listdir(NOTES_DIR):
                if fname.endswith('.md') and not fname.startswith('模板'):
                    try:
                        with open(os.path.join(NOTES_DIR, fname), 'r', encoding='utf-8') as fh:
                            for line in fh:
                                if line.startswith('topic:') or line.startswith('topics:'):
                                    for t in line.split(':', 1)[1].strip().strip('"[]').split(','):
                                        if t.strip(): existing_topics.add(t.strip())
                                    break
                    except: pass
            prompt = f"""你是知识管理助手。请阅读以下视频转录内容，整理为一篇学习笔记。

## 视频标题
{title}

## 转录内容
{transcript[:6000]}

## 现有主题
{', '.join(sorted(existing_topics)) if existing_topics else 'AI技术理解, 产品设计能力, 商业化思维, 工程协作能力, 评测体系搭建, 数据驱动决策'}

输出格式（严格JSON）：{{"title":"标题","topics":["分类1"],"content":"笔记...","summary":"摘要"}}"""
            resp = requests.post(DEEPSEEK_API_URL, headers={'Authorization': f'Bearer {DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'},
                json={'model': DEEPSEEK_MODEL, 'messages': [{'role': 'system', 'content': '严格按JSON格式输出。'}, {'role': 'user', 'content': prompt}], 'temperature': 0.3, 'max_tokens': 4000}, timeout=120)
            if resp.status_code != 200: self._send_json({'error': f'LLM API error: {resp.status_code}'}, 500); return
            content = resp.json()['choices'][0]['message']['content'].strip()
            if content.startswith('```'): content = content.split('\n', 1)[1]
            if content.endswith('```'): content = content[:-3]
            data = json.loads(content)
            date_str = datetime.now().strftime('%Y%m%d')
            safe_title = data.get('title', title)[:40].replace('/', '-').replace(':', '-')
            topics = data.get('topics', ['AI产品经理'])
            note = f"""---
type: study-note
source: 视频转录(Whisper)
source_url: {url}
topic: {topics[0] if topics else 'AI产品经理'}
topics: {json.dumps(topics, ensure_ascii=False)}
difficulty: medium
status: draft
created: {datetime.now().strftime('%Y-%m-%d')}
imported: {datetime.now().isoformat()}
quality_score: whisper_auto
---

# {data.get('title', title)}

> 来源：视频转录 · {url}
> 转录方式：Whisper (tiny) 语音转文字
> 状态：待确认（draft）· AI转录可能存在误差

{data.get('content', transcript[:3000])}
"""
            note_filename = f'{date_str}_{safe_title}_Whisper.md'; filepath = os.path.join(NOTES_DIR, note_filename)
            with open(filepath, 'w', encoding='utf-8') as f: f.write(note)
            self._send_json({'status': 'success', 'title': data.get('title', title), 'topics': topics, 'file': note_filename, 'transcript_length': len(transcript), 'source': f'Whisper转录: {title}'})
        except Exception as e:
            self._send_json({'error': f'转录失败：{str(e)[:200]}'}, 500)
        finally:
            if audio_path and os.path.exists(audio_path):
                try: os.remove(audio_path)
                except: pass

    # -- Competency --
    COMPETENCY_DIMS = {
        'AI技术理解': ['AI技术', 'LLM', 'GPT', 'Claude', 'embedding', 'RAG', 'token', 'context', 'prompt', 'agent', 'orchestration', 'model'],
        '评测体系搭建': ['评测', '评估', 'evaluation', 'benchmark', 'golden', 'metric', 'accuracy', 'quality'],
        '数据驱动决策': ['数据', 'data', 'analytics', 'A/B', 'ab test', 'metric', 'NSM', 'north star', 'SaaS'],
        '产品设计能力': ['用户故事', 'user story', 'PRD', 'JTBD', '优先级', 'prioriti', '路线图', 'roadmap', 'discovery', '产品设计', 'positioning', '定位', 'problem framing'],
        '商业化思维': ['商业化', 'TAM', 'SAM', 'SOM', 'revenue', '收入', '定价', 'pricing', '市场', 'competitive', '竞争', '战略'],
        '工程协作能力': ['工程', 'stakeholder', '协作', 'epic', 'story mapping', '开发'],
    }

    def _handle_competency(self):
        scores = {dim: {'correct': 0, 'total': 0, 'score': 50.0} for dim in self.COMPETENCY_DIMS}
        if HAS_PG:
            rows = db_exec("""SELECT wa.weakness_tags, wa.topics, wa.review_count FROM wrong_answers wa WHERE wa.review_status != 'mastered'""")
            for row in rows:
                tags = row.get('weakness_tags', []); topics = row.get('topics', [])
                if isinstance(tags, str):
                    try: tags = json.loads(tags)
                    except: tags = [tags]
                if isinstance(topics, str):
                    try: topics = json.loads(topics)
                    except: topics = [topics]
                all_text = ' '.join(tags + topics).lower()
                for dim, keywords in self.COMPETENCY_DIMS.items():
                    if any(kw.lower() in all_text for kw in keywords):
                        scores[dim]['total'] += 1
                        review_count = row.get('review_count', 0) or 0
                        scores[dim]['correct'] += max(0, 1 - review_count * 0.15)
        if os.path.exists(WRONG_DIR):
            for root, dirs, files in os.walk(WRONG_DIR):
                for f in files:
                    if f.endswith('.md') and not f.startswith('模板'):
                        try:
                            with open(os.path.join(root, f), 'r', encoding='utf-8') as fh: content = fh.read()
                            fm = {}
                            if content.startswith('---'):
                                parts = content.split('---', 2)
                                if len(parts) >= 3:
                                    for line in parts[1].split('\n'):
                                        if ':' in line: k, v = line.split(':', 1); fm[k.strip()] = v.strip()
                            all_text = (content + ' ' + fm.get('weakness_tags', '') + ' ' + fm.get('topics', '')).lower()
                            for dim, keywords in self.COMPETENCY_DIMS.items():
                                if any(kw.lower() in all_text for kw in keywords):
                                    score_val = float(fm.get('score', 0) or 0)
                                    scores[dim]['total'] += 1; scores[dim]['correct'] += min(5, score_val)
                        except: pass
        result = {}
        for dim, data in scores.items():
            result[dim] = round(max(10, min(95, (data['correct'] / max(1, data['total'] * 5)) * 100))) if data['total'] > 0 else 50
        weakest = sorted(result.items(), key=lambda x: x[1])[:2]
        strengths = sorted(result.items(), key=lambda x: x[1], reverse=True)[:2]
        rec_prompt = f"""你是AI产品经理学习教练。基于以下6维能力评估给出简短学习建议（2-3句话中文）。

{json.dumps(result, ensure_ascii=False, indent=2)}
最弱领域：{weakest[0][0]}({weakest[0][1]}分), {weakest[1][0]}({weakest[1][1]}分)
最强领域：{strengths[0][0]}({strengths[0][1]}分), {strengths[1][0]}({strengths[1][1]}分)"""
        recommendation = ''
        try:
            resp = requests.post(DEEPSEEK_API_URL, headers={'Authorization': f'Bearer {DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'},
                json={'model': DEEPSEEK_MODEL, 'messages': [{'role': 'system', 'content': '简短直接，2-3句话。'}, {'role': 'user', 'content': rec_prompt}], 'temperature': 0.5, 'max_tokens': 200}, timeout=30)
            if resp.status_code == 200: recommendation = resp.json()['choices'][0]['message']['content'].strip()
        except: pass
        if not recommendation and weakest[0][1] < 40:
            recommendation = f'今日重点：{weakest[0][0]}得分较低，建议从知识库选择该主题做一次测验。'
        elif not recommendation:
            recommendation = '各维度能力均衡发展，建议每日保持测验节奏。'

        self._send_json({'competency': result, 'weakest': [{'dim': d, 'score': s} for d, s in weakest], 'strengths': [{'dim': d, 'score': s} for d, s in strengths], 'recommendation': recommendation, 'standard_version': get_standard_version('_STANDARD_能力维度'), 'assessed_at': datetime.now().isoformat()})

    # -- History / Wrong Answers / Dashboard (simplified) --
    def _handle_history(self):
        rows = db_exec("""SELECT session_uuid, session_name, topics, difficulty, total_questions, questions_correct, questions_wrong, score_percentage, status, created_at, completed_at FROM quiz_sessions ORDER BY created_at DESC LIMIT 30""") if HAS_PG else []
        obsidian_wrong = []
        if os.path.exists(WRONG_DIR):
            for root, dirs, files in os.walk(WRONG_DIR):
                for f in files:
                    if f.endswith('.md') and not f.startswith('模板'):
                        obsidian_wrong.append({'topic': os.path.basename(root), 'file': f, 'path': os.path.join(root, f).replace(WRONG_DIR, '')})
        self._send_json({'sessions': rows, 'total_sessions': len(rows), 'obsidian_wrong_cards': len(obsidian_wrong)})

    def _handle_wrong_answers(self):
        obsidian_cards = []
        if os.path.exists(WRONG_DIR):
            for root, dirs, files in os.walk(WRONG_DIR):
                for f in files:
                    if f.endswith('.md') and not f.startswith('模板'):
                        filepath = os.path.join(root, f)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as fh: content = fh.read()
                            fm = {}
                            if content.startswith('---'):
                                parts = content.split('---', 2)
                                if len(parts) >= 3:
                                    for line in parts[1].split('\n'):
                                        if ':' in line: k, v = line.split(':', 1); fm[k.strip()] = v.strip()
                            obsidian_cards.append({'topic': os.path.basename(root), 'file': f, 'frontmatter': fm, 'path': filepath.replace(WRONG_DIR, '')})
                        except: pass
        today = datetime.now().strftime('%Y-%m-%d')
        due = sum(1 for c in obsidian_cards if (c.get('frontmatter', {}).get('next_review', '')[:10]) <= today)
        self._send_json({'obsidian_cards_total': len(obsidian_cards), 'obsidian_cards_due_today': due, 'obsidian_cards': obsidian_cards})

    def _handle_dashboard(self):
        stats = {}; topic_rows = []
        if HAS_PG:
            stats_rows = db_exec("""SELECT COUNT(DISTINCT qs.id) as total_quizzes, COALESCE(ROUND(AVG(qs.score_percentage), 1), 0) as avg_score, COALESCE(SUM(qs.total_questions), 0) as total_questions_answered, COUNT(DISTINCT CASE WHEN qs.completed_at >= NOW() - INTERVAL '7 days' THEN qs.id END) as quizzes_this_week FROM quiz_sessions qs WHERE qs.status = 'completed'""")
            if stats_rows: stats = stats_rows[0]
            topic_rows = db_exec("SELECT topic_name, mastery_score, recent_accuracy, total_attempted, review_urgency FROM topic_mastery ORDER BY mastery_score ASC LIMIT 10")
        wrong_count = 0
        if os.path.exists(WRONG_DIR):
            for root, dirs, files in os.walk(WRONG_DIR):
                wrong_count += len([f for f in files if f.endswith('.md') and not f.startswith('模板')])
        note_count = len([f for f in os.listdir(NOTES_DIR) if f.endswith('.md') and not f.startswith('模板')]) if os.path.exists(NOTES_DIR) else 0
        self._send_json({'stats': stats, 'notes_count': note_count, 'wrong_answers_count': wrong_count, 'topic_mastery': topic_rows, 'pg_connected': HAS_PG})

    def log_message(self, format, *args):
        print(f'[{datetime.now().strftime("%H:%M:%S")}] {args[0]}')

def main():
    port = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == '--port' else 5050
    server = HTTPServer(('0.0.0.0', port), QuizHandler)
    print(f'Knowledge Lab API v4 · http://localhost:{port}')
    print(f'PG: {"connected" if HAS_PG else "file-only mode"}')
    print(f'Standards: {len(STANDARDS)} loaded')
    try: server.serve_forever()
    except KeyboardInterrupt: print('\nShutting down...'); server.shutdown()

if __name__ == '__main__':
    main()
