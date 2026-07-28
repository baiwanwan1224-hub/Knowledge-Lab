"""Notes Blueprint — /notes/* (import, upload, transcribe, verify, delete, paste, ocr) + list/detail/drafts + /topics + /competency + /history + /wrong-answers + /ingest"""
import os, sys, json, re, tempfile, hashlib, requests
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from ..schemas import ImportRequest, PasteRequest, VerifyRequest, DeleteRequest, TranscribeRequest, ScreenshotOcrRequest, IngestRequest
from ..errors import ErrorCode, error_response
from ..config import is_allowed_extension, MAX_UPLOAD_BYTES

notes_bp = Blueprint('notes', __name__)

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS_DIR)

# Import vault_core
try:
    from vault_core import (
        safe_save_note, make_note_filename, wal_replay,
        save_integrity_snapshot, verify_integrity,
        VAULT_DIR, NOTES_DIR, WRONG_DIR, STANDARDS_DIR
    )
except ImportError:
    ROOT_DIR = os.path.dirname(SCRIPTS_DIR)
    VAULT_DIR = os.path.join(ROOT_DIR, 'vault')
    NOTES_DIR = os.path.join(VAULT_DIR, '00_学习笔记')
    WRONG_DIR = os.path.join(VAULT_DIR, '01_错题本')
    STANDARDS_DIR = os.path.join(VAULT_DIR, '06_产品层')
    for d in [NOTES_DIR, WRONG_DIR, STANDARDS_DIR]:
        os.makedirs(d, exist_ok=True)

IMPORTS_LOG = os.path.join(os.path.dirname(VAULT_DIR) if VAULT_DIR else os.path.join(SCRIPTS_DIR, '..', 'vault'), 'Knowledge Lab', '_imports.jsonl')
VAULT_BASE = VAULT_DIR
EXTRA_NOTE_DIRS = [os.path.join(VAULT_BASE, 'Clippings'), os.path.join(VAULT_BASE, '网页提取')]

# LLM config
_ENV_FILE = os.path.join(os.path.dirname(SCRIPTS_DIR), '.env')
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
LLM_API_URL = os.environ.get('LLM_API_URL', 'https://api.deepseek.com/v1/chat/completions')
LLM_MODEL = os.environ.get('LLM_MODEL', 'deepseek-v4-pro')

STANDARDS = {}
def load_standards():
    global STANDARDS
    if not os.path.exists(STANDARDS_DIR): return
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
                            if ':' in line:
                                k, v = line.split(':', 1); fm[k.strip()] = v.strip()
                        body = parts[2]
                key = fname.replace('.md', '')
                STANDARDS[key] = {'frontmatter': fm, 'body': body.strip()}
            except Exception as e:
                print(f'[WARN] Failed to load {fname}: {e}')

load_standards()

def log_import(import_type, source, title, topics, note_file):
    os.makedirs(os.path.dirname(IMPORTS_LOG), exist_ok=True)
    with open(IMPORTS_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'timestamp': datetime.now().isoformat(), 'type': import_type, 'source': source, 'title': title, 'topics': topics, 'file': note_file}, ensure_ascii=False) + '\n')

def _scan_notes(topic=None):
    notes = []
    for search_dir in [str(NOTES_DIR)] + EXTRA_NOTE_DIRS:
        if not os.path.exists(search_dir): continue
        for root, dirs, files in os.walk(str(search_dir)):
            for fname in files:
                if fname.endswith('.md') and not fname.startswith('模板_'):
                    path = os.path.join(root, fname)
                    try:
                        with open(path, 'r', encoding='utf-8') as f: content = f.read()
                    except: continue
                    title = fname.replace('.md', '')
                    topics = []; status = 'draft'; source = ''; date_str = ''; author = ''
                    body_start = 0
                    for i, line in enumerate(content.split('\n')):
                        if line.startswith('title:'): title = line.split(':',1)[1].strip().strip('"')
                        if line.startswith('topics:'):
                            topics = [t.strip().strip('"[]').replace('"','') for t in line.split(':',1)[1].split(',')]
                        if line.startswith('status:'): status = line.split(':',1)[1].strip()
                        if line.startswith('source:'): source = line.split(':',1)[1].strip()
                        if line.startswith('date:'): date_str = line.split(':',1)[1].strip()
                        if line.startswith('author:'): author = line.split(':',1)[1].strip()
                        if line.startswith('# ') and not title: title = line[2:].strip()
                        if line == '---': body_start = i+1
                    # Preview: first 120 chars of body after frontmatter
                    body_lines = content.split('\n')[body_start:] if body_start else content.split('\n')[6:]
                    preview = ' '.join([l.strip() for l in body_lines if l.strip() and not l.startswith('#')][:2])[:120]
                    mtime = os.path.getmtime(path)
                    notes.append({
                        'path': path.replace(str(search_dir) + os.sep, ''), 'title': title,
                        'topics': topics, 'status': status, 'source': source, 'date': date_str,
                        'author': author, 'preview': preview, 'content': content[:500],
                        'mtime': mtime, 'file_hash': hashlib.sha256(content.encode()).hexdigest()
                    })
    if topic:
        notes = [n for n in notes if topic in str(n.get('topics', [])) or topic.lower() in n['title'].lower() or topic.lower() in n.get('content', '').lower()]
    return notes

def _ai_structure(raw_text, filename):
    """Use LLM to structure raw text into markdown notes."""
    api_key = os.environ.get('LLM_API_KEY', '')
    api_url = os.environ.get('LLM_API_URL', 'https://api.deepseek.com/v1/chat/completions')
    model = os.environ.get('LLM_MODEL', 'deepseek-v4-pro')
    if not api_key:
        return raw_text
    try:
        # DeepSeek can handle ~16K chars comfortably. For longer docs, split.
        MAX_CHUNK = 30000
        if len(raw_text) <= MAX_CHUNK:
            chunks = [raw_text]
        else:
            chunks = []
            paras = raw_text.split('\n\n')
            current = ''
            for p in paras:
                if len(current) + len(p) > MAX_CHUNK and current:
                    chunks.append(current)
                    current = p
                else:
                    current = (current + '\n\n' + p).strip()
            if current:
                chunks.append(current)

        results = []
        for i, chunk in enumerate(chunks):
            try:
                prefix = f'(第{i+1}/{len(chunks)}部分) ' if len(chunks) > 1 else ''
                payload = {
                    'model': model,
                    'messages': [{'role': 'user', 'content': f'{prefix}请将以下文本整理为结构化的 Markdown 笔记。添加合适的标题、分段、列表。保留所有原始信息，只调整格式：\n\n{chunk}'}],
                    'temperature': 0.3
                }
                resp = requests.post(api_url,
                    headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                    json=payload, timeout=180)
                data = resp.json()
                structured = data['choices'][0]['message']['content']
                if structured and structured.strip():
                    results.append(structured)
                else:
                    results.append(chunk)  # LLM returned empty, keep raw
            except Exception:
                results.append(chunk)  # API call failed, keep raw
        return '\n\n---\n\n'.join(results) if results else raw_text
    except Exception:
        return raw_text

def _save_note(content, topic="", source_url="", original_name=""):
    title = ""
    for line in content.split('\n'):
        if line.startswith('# '): title = line[2:].strip(); break
    if not title:
        title = content[:80].replace('\n', ' ').strip()
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower().strip())[:50].strip('-')
    date_str = datetime.now().strftime('%Y-%m-%d')
    # Preserve original filename if provided
    if original_name:
        base = re.sub(r'\.[^.]+$', '', original_name)
        safe_orig = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff_-]', '-', base)[:60]
        fname = f'{date_str}_{safe_orig}.md'
    else:
        fname = f'{date_str}_{slug}.md'
    filepath = os.path.join(NOTES_DIR, fname)
    topics_list = [t.strip() for t in topic.split(',') if t.strip()]
    frontmatter = f'---\ntitle: "{title}"\ntopics: {json.dumps(topics_list, ensure_ascii=False)}\nsource: "{source_url}"\ndate: {date_str}\nstatus: draft\n---\n\n'
    final_content = frontmatter + content
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(final_content)
    return fname, title, topics_list

# ═══════════════════════════════════════
# POST endpoints
# ═══════════════════════════════════════

@notes_bp.route('/notes/import', methods=['POST'])
def import_note():
    try: body = ImportRequest(**(request.get_json(force=True, silent=True) or {}))
    except Exception as e: return error_response(ErrorCode.INVALID_JSON, str(e))
    return _do_import_url(body.url, body.topic)

def _do_import_url(url, topic=""):
    # Fetch URL content
    try:
        resp = requests.get(url, timeout=30, headers={'User-Agent': 'Knowledge-Lab/1.0'})
        resp.raise_for_status()
        raw = resp.text[:20000]
    except Exception as e:
        return error_response(ErrorCode.NOT_FOUND, f"Cannot fetch URL: {e}")

    # Call LLM to structure content
    prompt = f"""请将以下网页内容结构化为Markdown学习笔记。提取核心概念、关键框架、实践案例。原文：\n\n{raw[:10000]}"""
    try:
        llm_resp = requests.post(LLM_API_URL,
            headers={'Authorization': f'Bearer {LLM_API_KEY}', 'Content-Type': 'application/json'},
            json={'model': LLM_MODEL, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.5, 'max_tokens': 3000},
            timeout=120)
        structured = llm_resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return error_response(ErrorCode.LLM_API_ERROR, str(e), 502)

    fname, title, topics_list = _save_note(structured, topic, url)
    log_import('url', url, title, topics_list, fname)
    return jsonify({'status': 'success', 'file': fname, 'title': title, 'topics': topics_list})


@notes_bp.route('/notes/paste', methods=['POST'])
def paste_note():
    try: body = PasteRequest(**(request.get_json(force=True, silent=True) or {}))
    except Exception as e: return error_response(ErrorCode.INVALID_JSON, str(e))
    return _do_import_url("", body.topic) if not body.content else _handle_paste(body.content, body.topic)

def _handle_paste(content, topic=""):
    prompt = f"""请将以下文本结构化为Markdown学习笔记。提取核心概念、关键框架、实践案例。原文：\n\n{content[:10000]}"""
    try:
        llm_resp = requests.post(LLM_API_URL,
            headers={'Authorization': f'Bearer {LLM_API_KEY}', 'Content-Type': 'application/json'},
            json={'model': LLM_MODEL, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.5, 'max_tokens': 3000},
            timeout=120)
        structured = llm_resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return error_response(ErrorCode.LLM_API_ERROR, str(e), 502)

    fname, title, topics_list = _save_note(structured, topic, "paste")
    log_import('paste', 'paste', title, topics_list, fname)
    return jsonify({'status': 'success', 'file': fname, 'title': title, 'topics': topics_list})


@notes_bp.route('/notes/upload', methods=['POST'])
def upload_file():
    # Batch image OCR mode
    if request.form.get('mode') == 'ocr_batch':
        image_files = request.files.getlist('files')
        if not image_files:
            return error_response(ErrorCode.FILE_MISSING, "No image files provided")
        minimax_key = os.environ.get('MINIMAX_API_KEY', '')
        if not minimax_key:
            return error_response(ErrorCode.INTERNAL_ERROR,
                "OCR 需要多模态模型。请在 .env 中配置支持图片理解的 LLM 的 API Key", 500)
        ocr_results = []
        for i, img in enumerate(image_files):
            if not img.filename:
                continue
            try:
                import base64
                img_b64 = base64.b64encode(img.read()).decode()
                mime = img.mimetype or 'image/png'
                resp = requests.post('https://api.minimaxi.com/v1/text/chatcompletion_v2',
                    headers={'Authorization': f'Bearer {minimax_key}', 'Content-Type': 'application/json'},
                    json={
                        'model': 'MiniMax-M3',
                        'messages': [{'role': 'user', 'content': [
                            {'type': 'text', 'text': '请识别并提取这张截图中的所有文字内容。输出 Markdown 格式，保留标题层级和列表结构。'},
                            {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{img_b64}'}}
                        ]}],
                        'temperature': 0.1
                    }, timeout=120)
                data = resp.json()
                text = data['choices'][0]['message']['content'] if data.get('choices') else ''
                if text.strip():
                    ocr_results.append(f'## 截图 {i+1}\n\n{text.strip()}')
            except Exception as e:
                ocr_results.append(f'## 截图 {i+1}\n\n_(OCR 失败: {str(e)[:100]})_')
        if not ocr_results:
            return error_response(ErrorCode.NO_CONTENT, "所有截图 OCR 均失败")
        combined = '\n\n---\n\n'.join(ocr_results)
        fname, title, topics_list = _save_note(combined, '', 'screenshot-batch', f'截图_{len(image_files)}张')
        log_import('ocr', 'screenshot-batch', title, topics_list, fname)
        return jsonify({'status': 'success', 'file': fname, 'title': title, 'image_count': len(image_files)})

    # Single file upload
    f = request.files.get('file')
    if f is None or not f.filename:
        return error_response(ErrorCode.FILE_MISSING, "field 'file' is required")

    safe_name = secure_filename(f.filename)
    if not is_allowed_extension(safe_name):
        return error_response(ErrorCode.FILE_TYPE_UNSUPPORTED, f"Extension not allowed: {safe_name}")

    cl = request.content_length
    if cl and cl > MAX_UPLOAD_BYTES:
        return error_response(ErrorCode.FILE_TOO_LARGE, f"Max size: {MAX_UPLOAD_BYTES} bytes", 413)

    ext = os.path.splitext(safe_name)[1].lower()
    # Image files: OCR with MiniMax M3
    if ext in ('.png', '.jpg', '.jpeg', '.webp'):
        import base64
        img_b64 = base64.b64encode(f.read()).decode()
        minimax_key = os.environ.get('MINIMAX_API_KEY', '')
        if not minimax_key:
            return error_response(ErrorCode.INTERNAL_ERROR,
                "OCR 需要多模态模型。请在 .env 中配置支持图片理解的 LLM 的 API Key", 500)
        try:
            resp = requests.post('https://api.minimaxi.com/v1/text/chatcompletion_v2',
                headers={'Authorization': f'Bearer {minimax_key}', 'Content-Type': 'application/json'},
                json={
                    'model': 'MiniMax-M3',
                    'messages': [{'role': 'user', 'content': [
                        {'type': 'text', 'text': '请识别并提取这张截图中的所有文字内容。输出 Markdown 格式，保留标题层级和列表结构。'},
                        {'type': 'image_url', 'image_url': {'url': f'data:{f.mimetype or "image/png"};base64,{img_b64}'}}
                    ]}],
                    'temperature': 0.1
                }, timeout=120)
            data = resp.json()
            raw_text = data['choices'][0]['message']['content'] if data.get('choices') else ''
            if not raw_text.strip():
                return error_response(ErrorCode.NO_CONTENT, "截图未识别到文字")
        except Exception as e:
            return error_response(ErrorCode.LLM_API_ERROR, f"OCR 失败: {str(e)[:150]}", 502)
        fname, title, topics_list = _save_note(raw_text, '', f'ocr: {safe_name}', safe_name)
        log_import('ocr', safe_name, title, topics_list, fname)
        return jsonify({'status': 'success', 'file': fname, 'title': title, 'type': 'ocr'})

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    try:
        f.save(tmp.name)
        tmp.close()
        if ext == '.pdf':
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(tmp.name)
                raw_text = ''
                for page in reader.pages:
                    raw_text += page.extract_text() or ''
                if not raw_text.strip():
                    return error_response(ErrorCode.NO_CONTENT, "PDF 无法提取文字，可能是扫描版图片 PDF")
            except ImportError:
                return error_response(ErrorCode.INTERNAL_ERROR, "PyPDF2 not installed", 500)
        else:
            with open(tmp.name, 'r', encoding='utf-8', errors='ignore') as fh:
                raw_text = fh.read()
    finally:
        try: os.unlink(tmp.name)
        except OSError: pass

    # Split long PDFs into multiple notes (30000 chars each)
    SPLIT_AT = 30000
    if len(raw_text) > SPLIT_AT:
        paras = raw_text.split('\n\n')
        parts = []; current = ''
        for p in paras:
            if len(current) + len(p) > SPLIT_AT and current:
                parts.append(current)
                current = p
            else:
                current = (current + '\n\n' + p).strip()
        if current:
            parts.append(current)
    else:
        parts = [raw_text]

    topic = request.form.get('topic', '')
    results = []
    for i, part in enumerate(parts):
        content = _ai_structure(part, safe_name)
        # Add part number to filename for multi-part docs
        if len(parts) > 1:
            base = re.sub(r'\.[^.]+$', '', safe_name)
            part_name = f'{base}_part{i+1}of{len(parts)}.pdf'
            content = f'> 本文档共 {len(parts)} 篇，这是第 {i+1} 篇。\n\n{content}'
        else:
            part_name = safe_name
        fname, title, topics_list = _save_note(content, topic, f"upload: {part_name}", part_name)
        log_import('upload', part_name, title, topics_list, fname)
        results.append({'file': fname, 'title': title, 'topics': topics_list})

    if len(results) == 1:
        return jsonify({'status': 'success', **results[0]})
    return jsonify({'status': 'success', 'parts': results, 'total_parts': len(results),
                    'file': results[0]['file'], 'title': results[0]['title']})


@notes_bp.route('/notes/transcribe', methods=['POST'])
def transcribe():
    try: body = TranscribeRequest(**(request.get_json(force=True, silent=True) or {}))
    except Exception as e: return error_response(ErrorCode.INVALID_JSON, str(e))

    url = body.url
    # Try youtube-transcript-api first
    transcript_text = ""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        video_id = url.split('v=')[-1].split('&')[0] if 'v=' in url else url.split('/')[-1]
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'zh-Hans', 'zh'])
        transcript_text = ' '.join([t['text'] for t in transcript])
    except:
        pass

    if not transcript_text:
        try:
            import subprocess
            result = subprocess.run(['yt-dlp', '--write-auto-sub', '--sub-lang', 'en,zh-Hans', '--convert-subs', 'srt', '--skip-download', '-o', '%(id)s', url],
                                    capture_output=True, text=True, timeout=60, cwd=SCRIPTS_DIR)
        except:
            pass

    if not transcript_text:
        return error_response(ErrorCode.TRANSCRIBE_FAILED, "No captions available and transcription failed", 422)

    body.topic = body.topic or 'youtube'
    fname, title, topics_list = _save_note(transcript_text, body.topic, url)
    log_import('youtube', url, title, topics_list, fname)
    return jsonify({'status': 'success', 'file': fname, 'title': title, 'transcript_length': len(transcript_text)})


@notes_bp.route('/notes/verify', methods=['POST'])
def verify_note():
    try: body = VerifyRequest(**(request.get_json(force=True, silent=True) or {}))
    except Exception as e: return error_response(ErrorCode.INVALID_JSON, str(e))

    target_file = os.path.join(NOTES_DIR, body.file)
    if not os.path.exists(target_file):
        # Also search in EXTRA_NOTE_DIRS
        for d in EXTRA_NOTE_DIRS:
            candidate = os.path.join(d, body.file)
            if os.path.exists(candidate):
                target_file = candidate
                break
        else:
            return error_response(ErrorCode.NOTE_NOT_FOUND, f"Note not found: {body.file}", 404)

    try:
        with open(target_file, 'r', encoding='utf-8') as f: content = f.read()
    except Exception as e:
        return error_response(ErrorCode.INTERNAL_ERROR, str(e), 500)

    if body.action == 'approve':
        content = content.replace('status: draft', 'status: ready')
        content = content.replace('status: needs_revision', 'status: ready')
    elif body.action == 'reject':
        content = content.replace('status: draft', 'status: needs_revision')

    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(content)

    return jsonify({'status': 'success', 'action': body.action, 'file': body.file})


@notes_bp.route('/notes/delete', methods=['POST'])
def delete_note():
    try: body = DeleteRequest(**(request.get_json(force=True, silent=True) or {}))
    except Exception as e: return error_response(ErrorCode.INVALID_JSON, str(e))

    safe = os.path.basename(body.file)
    if '..' in safe or '/' in safe:
        return error_response(ErrorCode.INVALID_JSON, "Invalid file path")

    # Search across all note directories
    target = None
    for search_dir in [NOTES_DIR] + EXTRA_NOTE_DIRS:
        candidate = os.path.join(search_dir, safe)
        if os.path.exists(candidate):
            target = candidate
            break
        # Also search subdirectories
        if os.path.exists(search_dir):
            for root, dirs, files in os.walk(search_dir):
                if safe in files:
                    target = os.path.join(root, safe)
                    break
            if target: break

    if not target or not os.path.exists(target):
        return error_response(ErrorCode.NOTE_NOT_FOUND, f"Note not found: {safe}", 404)

    os.remove(target)
    return jsonify({'status': 'success', 'deleted': safe})


@notes_bp.route('/notes/screenshot_ocr', methods=['POST'])
def screenshot_ocr():
    try: body = ScreenshotOcrRequest(**(request.get_json(force=True, silent=True) or {}))
    except Exception as e: return error_response(ErrorCode.INVALID_JSON, str(e))

    try:
        minimax_key = os.environ.get('MINIMAX_API_KEY', '')
        if not minimax_key:
            return error_response(ErrorCode.INTERNAL_ERROR,
                "OCR 需要多模态模型。请在 .env 中配置支持图片理解的 LLM 的 API Key", 500)

        resp = requests.post('https://api.minimaxi.com/v1/text/chatcompletion_v2',
            headers={'Authorization': f'Bearer {minimax_key}', 'Content-Type': 'application/json'},
            json={
                'model': 'MiniMax-M3',
                'messages': [{
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': 'Extract all text from this screenshot. Output in markdown format.'},
                        {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{body.image_b64}'}}
                    ]
                }],
                'temperature': 0.1
            }, timeout=60)
        text = resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return error_response(ErrorCode.LLM_API_ERROR, str(e), 502)

    fname, title, topics_list = _save_note(text, '', "screenshot_ocr")
    log_import('ocr', 'screenshot', title, topics_list, fname)
    return jsonify({'status': 'success', 'file': fname, 'text': text[:500]})


@notes_bp.route('/ingest', methods=['POST'])
def ingest():
    try: body = IngestRequest(**(request.get_json(force=True, silent=True) or {}))
    except Exception as e: return error_response(ErrorCode.INVALID_JSON, str(e))
    fname, title, topics_list = _save_note(body.content, '', body.source)
    log_import('webhook', body.source, title, topics_list, fname)
    return jsonify({'status': 'success', 'file': fname})

# ═══════════════════════════════════════
# GET endpoints
# ═══════════════════════════════════════

@notes_bp.route('/topics')
def topics():
    notes = _scan_notes()
    topic_counts = defaultdict(int)
    for n in notes:
        for t in n.get('topics', []):
            topic_counts[t.strip()] += 1
    return jsonify([{'name': k, 'count': v} for k, v in sorted(topic_counts.items(), key=lambda x: -x[1])])

@notes_bp.route('/notes')
def list_notes():
    topic = request.args.get('topic', '')
    notes = _scan_notes(topic if topic else None)
    return jsonify(notes)

@notes_bp.route('/note')
def get_note():
    file_path = request.args.get('path', '')
    if not file_path:
        return error_response(ErrorCode.MISSING_FIELD, "?path= required")
    safe = os.path.basename(file_path)
    target = os.path.join(NOTES_DIR, safe)
    if not os.path.exists(target):
        for d in EXTRA_NOTE_DIRS:
            candidate = os.path.join(d, safe)
            if os.path.exists(candidate): target = candidate; break
        else:
            return error_response(ErrorCode.NOTE_NOT_FOUND, f"Note not found: {safe}", 404)
    with open(target, 'r', encoding='utf-8') as f:
        content = f.read()
    return jsonify({'path': safe, 'content': content})

@notes_bp.route('/notes/drafts')
def list_drafts():
    notes = _scan_notes()
    drafts = [n for n in notes if n.get('status') in ('draft', 'needs_revision')]
    return jsonify(drafts)

@notes_bp.route('/notes/imports')
def list_imports():
    if not os.path.exists(IMPORTS_LOG): return jsonify([])
    with open(IMPORTS_LOG, 'r', encoding='utf-8') as f:
        lines = f.readlines()[-50:]
    return jsonify([json.loads(l) for l in lines])

@notes_bp.route('/competency')
def competency():
    topic = request.args.get('topic', '')
    # Load competency dimensions from standards
    dims = ['AI技术理解', '评测体系搭建', '数据驱动决策', '产品设计能力', '商业化思维', '工程协作能力']
    wrong_cards = []
    if os.path.exists(WRONG_DIR):
        for root, dirs, files in os.walk(WRONG_DIR):
            for fname in files:
                if fname.endswith('.md'):
                    with open(os.path.join(root, fname), 'r', encoding='utf-8') as f:
                        wrong_cards.append(f.read())

    result = {}
    for dim in dims:
        score = 50
        # Check wrong cards for this dimension
        matching = [c for c in wrong_cards if dim in c]
        if matching:
            total_mentions = len(matching)
            mastered_mentions = len([c for c in matching if 'ease_factor: 2.5' in c or 'review_count: 0' not in c])
            score = max(10, min(95, int((1 - total_mentions / (total_mentions + 10)) * 100)))
        result[dim] = score

    # Sort by score: weakest first
    sorted_dims = sorted(result.items(), key=lambda x: x[1])
    weakest = [{'dim': d, 'score': s} for d, s in sorted_dims[:2]]
    rec = f"今日建议重点突破「{weakest[0]['dim']}」（当前 {weakest[0]['score']} 分）。从知识库选择该主题做一次测验，然后复习错题本中的相关卡片。"

    return jsonify({
        'competency': result,
        'weakest': weakest,
        'recommendation': rec,
        'standard_version': '1.0',
        'assessed_at': datetime.now().isoformat()
    })

@notes_bp.route('/history')
def history():
    sessions_dir = os.path.join(os.path.dirname(SCRIPTS_DIR), 'data', 'sessions')
    sessions = []
    if os.path.exists(sessions_dir):
        for fname in sorted(os.listdir(sessions_dir), reverse=True):
            if fname.endswith('.json'):
                try:
                    with open(os.path.join(sessions_dir, fname), 'r', encoding='utf-8') as f:
                        sessions.append(json.load(f))
                except: pass
    # Also include current session if it exists and not saved yet
    cur_session = os.path.join(os.path.dirname(SCRIPTS_DIR), 'current_session.json')
    if os.path.exists(cur_session) and not any(s.get('session_uuid') == 'current' for s in sessions):
        try:
            with open(cur_session, 'r', encoding='utf-8') as f:
                cur = json.load(f)
            sessions.insert(0, {
                'session_uuid': cur.get('session_uuid', 'current'),
                'session_name': cur.get('session_name', ''),
                'created_at': cur.get('generated_at', ''),
                'completed_at': None,
                'total_questions': cur.get('total', 0),
                'questions_correct': 0,
                'total_score': 0, 'total_max': cur.get('total', 0),
                'score_percentage': 0,
                'difficulty': cur.get('difficulty', 'medium'),
                'topics': cur.get('topics', []),
                'status': 'pending'
            })
        except: pass
    return jsonify({'sessions': sessions})

@notes_bp.route('/wrong-answers')
def wrong_answers():
    cards = []
    if os.path.exists(WRONG_DIR):
        for root, dirs, files in os.walk(WRONG_DIR):
            for fname in files:
                if fname.endswith('.md') and not fname.startswith('模板_'):
                    filepath = os.path.join(root, fname)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # Parse YAML frontmatter
                    fm = {}
                    body = content
                    if content.startswith('---'):
                        parts = content.split('---', 2)
                        if len(parts) >= 3:
                            for line in parts[1].strip().split('\n'):
                                line = line.strip()
                                if ':' in line:
                                    k, v = line.split(':', 1)
                                    k, v = k.strip(), v.strip()
                                    try: fm[k] = json.loads(v)
                                    except: fm[k] = v
                            body = parts[2]
                    cards.append({'file': fname, 'topic': os.path.basename(root),
                                  'content': body.strip()[:500],
                                  'frontmatter': fm, 'mtime': os.path.getmtime(filepath)})
    cards.sort(key=lambda c: c.get('mtime', 0), reverse=True)
    due = sum(1 for c in cards if c.get('frontmatter', {}).get('next_review', '9999')[:10] <= datetime.now().strftime('%Y-%m-%d'))
    return jsonify({'obsidian_cards': cards, 'obsidian_cards_total': len(cards),
                    'obsidian_cards_due_today': due})
