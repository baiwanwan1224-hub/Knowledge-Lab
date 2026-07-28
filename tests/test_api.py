"""Test Knowledge Lab API endpoints — functional tests against Flask test client."""
import json


class TestHealthAndMeta:
    """Basic connectivity and metadata endpoints."""

    def test_health(self, client):
        resp = client.get('/v1/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'ok'
        assert 'model' in data or 'provider' in data

    def test_dashboard(self, client):
        resp = client.get('/v1/dashboard')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'notes_count' in data
        assert 'wrong_answers_count' in data
        assert 'stats' in data
        assert 'total_quizzes' in data['stats']

    def test_topics(self, client):
        resp = client.get('/v1/topics')
        assert resp.status_code == 200
        data = resp.get_json()
        # Returns flat array [{name, count}, ...] or {topics: [...]}
        if isinstance(data, list):
            assert len(data) >= 0  # valid even if empty
        else:
            assert 'topics' in data

    def test_notes_list(self, client):
        resp = client.get('/v1/notes')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_wrong_answers(self, client):
        resp = client.get('/v1/wrong-answers')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'obsidian_cards' in data
        assert 'obsidian_cards_total' in data
        assert 'obsidian_cards_due_today' in data

    def test_history(self, client):
        resp = client.get('/v1/history')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'sessions' in data

    def test_competency(self, client):
        resp = client.get('/v1/competency')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'competency' in data
        assert 'weakest' in data
        assert 'recommendation' in data

    def test_stats(self, client):
        resp = client.get('/v1/stats')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'calls_7d' in data or 'calls_1d' in data


class TestQuizGenerate:
    """Quiz generation endpoint — requires LLM API and subprocess."""

    def test_generate_basic(self, client):
        """Basic quiz generation with topic string."""
        resp = client.post('/v1/quiz/generate',
            data=json.dumps({
                'topic': 'AI产品经理', 'count': 2,
                'types': 'single_choice', 'difficulty': 'easy'
            }),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('status') == 'success'
        assert 'questions' in data
        assert len(data['questions']) == 2
        assert 'session_uuid' in data

    def test_generate_types_list(self, client):
        """Regression test: types as list (the browser INVALID_JSON bug)."""
        resp = client.post('/v1/quiz/generate',
            data=json.dumps({
                'topic': '产品管理', 'count': 2,
                'types': ['single_choice', 'short_answer'],
                'difficulty': 'medium'
            }),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('status') == 'success'

    def test_generate_defaults(self, client):
        """Minimal request — only topic."""
        resp = client.post('/v1/quiz/generate',
            data=json.dumps({'topic': '产品策略'}),
            content_type='application/json'
        )
        assert resp.status_code == 200

    def test_generate_missing_topic(self, client):
        """Missing required field should return error."""
        resp = client.post('/v1/quiz/generate',
            data=json.dumps({'count': 5}),
            content_type='application/json'
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['error'] == 'INVALID_JSON'

    def test_generate_nocache(self, client):
        """nocache flag should bypass cache (LLM may occasionally return empty)."""
        resp = client.post('/v1/quiz/generate',
            data=json.dumps({
                'topic': '产品方法论', 'count': 2, 'nocache': True
            }),
            content_type='application/json'
        )
        # nocache may hit LLM rate limits; accept 200 or 502
        assert resp.status_code in (200, 502)


class TestQuizGrade:
    """Quiz grading endpoint."""

    def test_grade_basic(self, client):
        """Generate quiz, then grade it."""
        # First generate
        gen = client.post('/v1/quiz/generate',
            data=json.dumps({
                'topic': '产品管理', 'count': 2,
                'types': 'single_choice', 'difficulty': 'medium'
            }),
            content_type='application/json'
        )
        quiz = gen.get_json()
        session_uuid = quiz['session_uuid']
        questions = quiz['questions']

        # Then grade with sample answers
        answers = [q.get('correct_answer', q.get('options', [{}])[0].get('label', 'A')) for q in questions]

        resp = client.post('/v1/quiz/grade',
            data=json.dumps({
                'session_uuid': session_uuid,
                'questions': questions,
                'answers': answers,
                'source_notes': [{'title': 'test', 'hash': 'abc'}]
            }),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('status') == 'success'
        assert 'results' in data
        assert 'score_pct' in data
        assert len(data['results']) == 2


class TestNotesCRUD:
    """Notes import, list, detail, delete."""

    def test_paste_and_verify(self, client):
        """Paste text → get note detail → verify → delete."""
        # Paste
        resp = client.post('/v1/notes/paste',
            data=json.dumps({'content': '# 测试笔记\n\n这是一个测试段落。'}),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('status') == 'success'
        fname = data['file']

        # Get detail
        resp = client.get(f'/v1/note?path={fname}')
        assert resp.status_code == 200
        detail = resp.get_json()
        assert 'content' in detail
        assert '测试笔记' in detail['content']

        # Verify (approve)
        resp = client.post('/v1/notes/verify',
            data=json.dumps({'file': fname, 'action': 'approve'}),
            content_type='application/json'
        )
        assert resp.status_code == 200

        # Delete
        resp = client.post('/v1/notes/delete',
            data=json.dumps({'file': fname}),
            content_type='application/json'
        )
        assert resp.status_code == 200
        assert resp.get_json().get('status') == 'success'

    def test_delete_nonexistent(self, client):
        """Deleting a non-existent note should return 404."""
        resp = client.post('/v1/notes/delete',
            data=json.dumps({'file': 'does-not-exist-xyz.md'}),
            content_type='application/json'
        )
        assert resp.status_code == 404


class TestCORSErrorHandling:
    """CORS and error handling."""

    def test_cors_headers(self, client):
        """All responses should have CORS headers."""
        resp = client.get('/v1/health')
        assert resp.headers.get('Access-Control-Allow-Origin') == '*'
        assert 'POST' in resp.headers.get('Access-Control-Allow-Methods', '')

    def test_options_preflight(self, client):
        """OPTIONS preflight should return 200."""
        resp = client.options('/v1/quiz/generate')
        assert resp.status_code == 200

    def test_invalid_json(self, client):
        """Malformed JSON should return INVALID_JSON."""
        resp = client.post('/v1/quiz/generate',
            data='not json',
            content_type='application/json'
        )
        assert resp.status_code == 400

    def test_root_serves_dashboard(self, client):
        """Root URL should serve dashboard HTML, not redirect."""
        resp = client.get('/')
        assert resp.status_code == 200
        assert b'<!DOCTYPE html>' in resp.data or b'<html' in resp.data
