"""Quiz Blueprint — /quiz/generate, /quiz/grade · P0+P1: cache + retry + stats"""
import os, sys, json, subprocess, uuid, hashlib, time, logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from ..schemas import GenerateRequest, GradeRequest
from ..errors import ErrorCode, error_response
from ..constants import ENDPOINT_QUIZ_GENERATE, ENDPOINT_QUIZ_GRADE, MODEL_VERSION
from .. import stats, cache

logger = logging.getLogger(__name__)
quiz_bp = Blueprint('quiz', __name__)

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN_SCRIPT = os.path.join(SCRIPTS_DIR, 'quiz_generator.py')
GRADE_SCRIPT = os.path.join(SCRIPTS_DIR, 'quiz_grader.py')
SESSION_FILE = os.path.join(os.path.dirname(SCRIPTS_DIR), 'current_session.json')
SESSIONS_DIR = os.path.join(os.path.dirname(SCRIPTS_DIR), 'data', 'sessions')

RETRY_BACKOFF = [1, 2]  # seconds, max 2 retries (3 total attempts)

def _hash_notes(notes_data: list) -> str:
    return hashlib.sha1(json.dumps(notes_data, sort_keys=True).encode()).hexdigest()[:12]

@quiz_bp.route('/quiz/generate', methods=['POST'])
def generate():
    """Generate quiz questions from vault notes.
    ---
    tags:
      - Quiz
    parameters:
      - in: body
        name: body
        schema:
          id: GenerateRequest
          required: [topic]
          properties:
            topic: {type: string, description: Topic to generate questions for}
            count: {type: integer, default: 5, description: Number of questions (1-20)}
            types: {type: string, default: single_choice,short_answer}
            difficulty: {type: string, default: medium, enum: [easy, medium, hard]}
    responses:
      200: {description: Quiz questions generated}
      400: {description: Invalid request body}
      502: {description: LLM API error}
    """
    t0 = time.time()
    try:
        raw = request.get_json(force=True, cache=False) or {}
        body = GenerateRequest.model_validate(raw)
    except Exception as e:
        return error_response(ErrorCode.INVALID_JSON, str(e), 400)

    # ── P1: Cache check (skip if nocache) ──
    cached = None if raw.get('nocache') else cache.get('qgen', topic=body.topic, difficulty=body.difficulty,
                       count=body.count, types=body.types, model_version=MODEL_VERSION)
    if cached:
        stats.record(ENDPOINT_QUIZ_GENERATE, os.environ.get('LLM_MODEL',''), {}, int((time.time()-t0)*1000), cached=1)
        return jsonify(cached), 200

    # ── P0: Retry + stats ──
    last_error = None
    retries = 0
    for attempt in range(1 + len(RETRY_BACKOFF)):
        try:
            result = subprocess.run(
                [sys.executable, GEN_SCRIPT, '--topic', body.topic, '--count', str(body.count),
                 '--types', body.types, '--difficulty', body.difficulty],
                capture_output=True, text=True, timeout=120, cwd=SCRIPTS_DIR, stdin=subprocess.DEVNULL)
            data = json.loads(result.stdout)
            if 'error' in data:
                raise RuntimeError(data['error'])
            break
        except subprocess.TimeoutExpired as e:
            last_error = e; retries = attempt
            if attempt < len(RETRY_BACKOFF):
                logger.warning(f'LLM generate timeout → retry {attempt+1}/{len(RETRY_BACKOFF)}, reason: timeout')
                time.sleep(RETRY_BACKOFF[attempt])
        except Exception as e:
            last_error = e; retries = attempt
            if attempt < len(RETRY_BACKOFF):
                logger.warning(f'LLM generate failed → retry {attempt+1}/{len(RETRY_BACKOFF)}, reason: {e}')
                time.sleep(RETRY_BACKOFF[attempt])
    else:
        stats.record(ENDPOINT_QUIZ_GENERATE, os.environ.get('LLM_MODEL',''), {}, int((time.time()-t0)*1000), retries=retries, error=str(last_error))
        logger.error(f'LLM generate exhausted retries: {last_error}')
        return error_response(ErrorCode.LLM_API_ERROR, str(last_error), 502)

    latency_ms = int((time.time() - t0) * 1000)
    stats.record(ENDPOINT_QUIZ_GENERATE, os.environ.get('LLM_MODEL',''), {}, latency_ms, retries=retries)
    logger.info(f'[Pipeline] quiz.generate topic={body.topic} latency={latency_ms}ms retries={retries}')

    session_uuid = str(uuid.uuid4())
    data['session_uuid'] = session_uuid
    with open(SESSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # ── P1: Cache store ──
    cache.set('qgen', data, topic=body.topic, difficulty=body.difficulty,
              count=body.count, types=body.types, model_version=MODEL_VERSION)

    return jsonify(data), 200

@quiz_bp.route('/quiz/grade', methods=['POST'])
def grade():
    t0 = time.time()
    try:
        body = GradeRequest.model_validate(request.get_json(force=True, cache=False) or {})
    except Exception as e:
        return error_response(ErrorCode.INVALID_JSON, str(e), 400)

    session_uuid = body.session_uuid
    if not session_uuid and os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        session_uuid = session_data.get('session_uuid', '')

    grade_input = {'session_uuid': session_uuid, 'questions': body.questions,
                   'answers': body.answers, 'source_notes': body.source_notes}

    # ── P1: Cache check ──
    q_hash = hashlib.sha1(json.dumps(body.questions, sort_keys=True).encode()).hexdigest()[:12]
    a_hash = hashlib.sha1(json.dumps(body.answers, sort_keys=True).encode()).hexdigest()[:12]
    cached = cache.get('grade', question_hash=q_hash, answer_hash=a_hash, model_version=MODEL_VERSION)
    if cached:
        stats.record(ENDPOINT_QUIZ_GRADE, os.environ.get('LLM_MODEL',''), {}, int((time.time()-t0)*1000), cached=1)
        return jsonify(cached), 200

    # ── P0: Retry + stats ──
    last_error = None; retries = 0
    for attempt in range(1 + len(RETRY_BACKOFF)):
        try:
            result = subprocess.run(
                [sys.executable, GRADE_SCRIPT, '--input', json.dumps(grade_input, ensure_ascii=False)],
                capture_output=True, text=True, timeout=120, cwd=SCRIPTS_DIR, stdin=subprocess.DEVNULL)
            data = json.loads(result.stdout)
            if 'error' in data: raise RuntimeError(data['error'])
            break
        except subprocess.TimeoutExpired as e:
            last_error = e; retries = attempt
            if attempt < len(RETRY_BACKOFF):
                logger.warning(f'LLM grade timeout → retry {attempt+1}/{len(RETRY_BACKOFF)}')
                time.sleep(RETRY_BACKOFF[attempt])
        except Exception as e:
            last_error = e; retries = attempt
            if attempt < len(RETRY_BACKOFF):
                logger.warning(f'LLM grade failed → retry {attempt+1}/{len(RETRY_BACKOFF)}, reason: {e}')
                time.sleep(RETRY_BACKOFF[attempt])
    else:
        stats.record(ENDPOINT_QUIZ_GRADE, os.environ.get('LLM_MODEL',''), {}, int((time.time()-t0)*1000), retries=retries, error=str(last_error))
        logger.error(f'LLM grade exhausted retries: {last_error}')
        return error_response(ErrorCode.LLM_API_ERROR, str(last_error), 502)

    latency_ms = int((time.time() - t0) * 1000)
    stats.record(ENDPOINT_QUIZ_GRADE, os.environ.get('LLM_MODEL',''), {}, latency_ms, retries=retries)

    # ── Save session to history ──
    session_uuid = data.get('session_uuid', str(uuid.uuid4()))
    session_name = ''; difficulty = 'medium'; topics = []
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                gen_data = json.load(f)
            session_name = gen_data.get('session_name', '')
            difficulty = gen_data.get('difficulty', 'medium')
            topics = gen_data.get('topics', [])
        except: pass
    session_record = {
        'session_uuid': session_uuid,
        'session_name': session_name,
        'created_at': gen_data.get('generated_at', datetime.now().isoformat()) if os.path.exists(SESSION_FILE) else datetime.now().isoformat(),
        'completed_at': datetime.now().isoformat(),
        'total_questions': data.get('total_questions', 0),
        'questions_correct': data.get('correct_count', 0),
        'total_score': data.get('total_score', 0),
        'total_max': data.get('total_max', 0),
        'score_percentage': data.get('score_pct', 0),
        'difficulty': difficulty,
        'topics': topics,
        'status': 'completed'
    }
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    with open(os.path.join(SESSIONS_DIR, f'{session_uuid}.json'), 'w', encoding='utf-8') as f:
        json.dump(session_record, f, ensure_ascii=False, indent=2)
    logger.info(f'[Pipeline] quiz.grade latency={latency_ms}ms retries={retries}')

    # ── P1: Cache store ──
    cache.set('grade', data, question_hash=q_hash, answer_hash=a_hash, model_version=MODEL_VERSION)

    return jsonify(data), 200
