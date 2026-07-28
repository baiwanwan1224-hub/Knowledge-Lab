"""Web Blueprint — serve dashboard, health, dashboard stats"""
import os, json
from datetime import datetime, timedelta
from flask import Blueprint, send_file, jsonify, current_app
from ..errors import ErrorCode

web_bp = Blueprint('web', __name__)

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(SCRIPTS_DIR)
# Respect VAULT_PATH from .env (same as notes.py)
_VAULT_PATH = os.environ.get('VAULT_PATH', os.path.join(PROJECT_ROOT, 'vault'))
NOTES_DIR = os.path.join(_VAULT_PATH, 'Knowledge Lab', '00_学习笔记')
WRONG_DIR = os.path.join(_VAULT_PATH, 'Knowledge Lab', '01_错题本')

# PostgreSQL check
try:
    import psycopg2
    HAS_PG = True
except ImportError:
    HAS_PG = False

def _count_files(directory, ext='.md'):
    if not os.path.exists(directory): return 0
    return len([f for f in os.listdir(directory) if f.endswith(ext) and not f.startswith('模板_')])

@web_bp.route('/')
def index():
    html_path = os.path.join(PROJECT_ROOT, 'apps', 'web', 'dashboard_v2.html')
    return send_file(html_path)

@web_bp.route('/health')
def health():
    model = os.environ.get('LLM_MODEL', 'deepseek-v4-pro')
    provider = os.environ.get('LLM_PROVIDER', 'deepseek')
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat(), 'pg': HAS_PG,
                    'model': model, 'provider': provider})

@web_bp.route('/stats')
def pipeline_stats():
    """Pipeline monitoring — LLM call statistics."""
    from .. import stats as st
    from .. import cache as ch
    return jsonify({
        'calls_7d': st.summary(7),
        'calls_1d': st.summary(1),
        'cache': ch.stats(),
        'timestamp': datetime.now().isoformat()
    })

@web_bp.route('/dashboard')
def dashboard():
    # Note count
    notes = _count_files(NOTES_DIR)
    for d in [os.path.join(_VAULT_PATH, 'Clippings'), os.path.join(_VAULT_PATH, '网页提取')]:
        if os.path.exists(d):
            notes += _count_files(d)

    # Wrong answer count
    wrongs = 0
    if os.path.exists(WRONG_DIR):
        for root, dirs, files in os.walk(WRONG_DIR):
            wrongs += len([f for f in files if f.endswith('.md') and not f.startswith('模板_')])

    # Compute stats from history sessions
    sessions_dir = os.path.join(PROJECT_ROOT, 'data', 'sessions')
    sessions = []
    if os.path.exists(sessions_dir):
        for fname in os.listdir(sessions_dir):
            if fname.endswith('.json'):
                try:
                    with open(os.path.join(sessions_dir, fname), 'r', encoding='utf-8') as f:
                        sessions.append(json.load(f))
                except: pass

    total_quizzes = len([s for s in sessions if s.get('status') == 'completed'])
    total_answered = sum(s.get('total_questions', 0) for s in sessions)
    completed = [s for s in sessions if s.get('score_percentage') is not None and s.get('status') == 'completed']
    avg_score = round(sum(s.get('score_percentage', 0) for s in completed) / len(completed)) if completed else 0

    # This week
    now = datetime.now()
    week_start = (now - timedelta(days=now.weekday())).strftime('%Y-%m-%d')
    week_quizzes = len([s for s in sessions if (s.get('created_at', '') or '')[:10] >= week_start])

    # Topic mastery from wrong answer cards
    topic_mastery = []
    topic_stats = {}
    if os.path.exists(WRONG_DIR):
        for root, dirs, files in os.walk(WRONG_DIR):
            topic = os.path.basename(root)
            for fname in files:
                if fname.endswith('.md') and not fname.startswith('模板_'):
                    try:
                        with open(os.path.join(root, fname), 'r', encoding='utf-8') as f:
                            content = f.read()
                        fm = {}
                        if content.startswith('---'):
                            parts = content.split('---', 2)
                            if len(parts) >= 3:
                                for line in parts[1].strip().split('\n'):
                                    if ':' in line:
                                        k, v = line.split(':', 1)
                                        k, v = k.strip(), v.strip()
                                        try: fm[k] = json.loads(v)
                                        except: fm[k] = v
                        score = float(fm.get('score', 0))
                        max_score = 5.0
                        if topic not in topic_stats:
                            topic_stats[topic] = {'total': 0, 'correct': 0, 'count': 0}
                        topic_stats[topic]['total'] += 1
                        topic_stats[topic]['count'] += 1
                        if score > 0:
                            topic_stats[topic]['correct'] += 1
                    except: pass

    for topic, ts in topic_stats.items():
        mastery = round(ts['correct'] / max(ts['total'], 1) * 100)
        topic_mastery.append({
            'topic_name': topic, 'mastery_score': mastery,
            'recent_accuracy': mastery, 'total_attempted': ts['total']
        })

    return jsonify({
        'notes_count': notes,
        'wrong_answers_count': wrongs,
        'stats': {
            'total_quizzes': total_quizzes,
            'avg_score': avg_score,
            'total_questions_answered': total_answered,
            'quizzes_this_week': week_quizzes
        },
        'topic_mastery': topic_mastery,
        'timestamp': datetime.now().isoformat()
    })
