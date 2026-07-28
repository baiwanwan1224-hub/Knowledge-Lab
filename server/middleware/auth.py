"""Lightweight API Key Authentication Middleware."""
import os, logging
from functools import wraps
from flask import request, jsonify

logger = logging.getLogger(__name__)

SKIP_PATHS = {'/health', '/apidocs', '/flasgger', '/favicon.ico'}

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.path in SKIP_PATHS or request.path.startswith('/apidocs') or request.path.startswith('/flasgger'):
            return f(*args, **kwargs)

        api_key = os.environ.get('API_KEY', '').strip()
        if not api_key:
            return f(*args, **kwargs)

        provided = request.headers.get('X-API-Key', '')
        if not provided or provided != api_key:
            return jsonify({'error': 'UNAUTHORIZED', 'detail': 'Invalid or missing API key'}), 401

        return f(*args, **kwargs)
    return decorated


def init_api_key_auth(app):
    api_key = os.environ.get('API_KEY', '').strip()
    if api_key:
        app.before_request(lambda: _check_auth())
        logger.info('[Auth] API Key authentication enabled')
    else:
        logger.info('[Auth] No API_KEY set — running without authentication (local dev mode)')

def _check_auth():
    from flask import request, jsonify
    if request.path in SKIP_PATHS or request.path.startswith('/apidocs') or request.path.startswith('/flasgger'):
        return None
    api_key = os.environ.get('API_KEY', '').strip()
    if not api_key:
        return None
    provided = request.headers.get('X-API-Key', '')
    if not provided or provided != api_key:
        return jsonify({'error': 'UNAUTHORIZED', 'detail': 'Invalid or missing API key'}), 401
    return None
