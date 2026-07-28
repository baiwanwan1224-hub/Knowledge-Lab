"""Knowledge Lab · Flask Application Factory"""
import os, sys

def create_app():
    from flask import Flask, redirect, request
    from flasgger import Swagger

    # Load .env
    _ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(_ENV_FILE):
        with open(_ENV_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())

    app = Flask(__name__, static_folder=None)

    # ── CORS ──
    @app.after_request
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
        return response

    # ── Swagger / OpenAPI ──
    app.config['SWAGGER'] = {
        'title': 'Knowledge Lab API',
        'description': 'RAG-powered self-test learning platform · Quiz generation, note management, competency assessment',
        'version': '0.1.0',
        'uiversion': 3,
    }
    swagger = Swagger(app, template_file=None)

    # ── Auth middleware ──
    from .middleware.auth import init_api_key_auth
    init_api_key_auth(app)

    # ── Blueprints with /v1 prefix ──
    from .blueprints import BLUEPRINTS
    for bp in BLUEPRINTS:
        app.register_blueprint(bp, url_prefix='/v1')

    # ── Root: serve dashboard ──
    DASHBOARD_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'apps', 'web', 'dashboard_v2.html')

    @app.route('/')
    def index():
        if os.path.exists(DASHBOARD_FILE):
            with open(DASHBOARD_FILE, 'r', encoding='utf-8') as f:
                return f.read(), 200, {'Content-Type': 'text/html; charset=utf-8'}
        return redirect('/v1/', code=302)

    # ── 301 redirect: old paths → /v1 ──
    @app.route('/<path:path>', methods=['GET'])
    def legacy_redirect(path):
        if path in ('health', 'apidocs', 'flasgger') or path.startswith('apidocs') or path.startswith('flasgger'):
            if path == 'health':
                from flask import jsonify
                from datetime import datetime
                try: import psycopg2; pg = True
                except ImportError: pg = False
                return jsonify({'status': 'ok', 'time': datetime.now().isoformat(), 'pg': pg})
            return app.view_functions.get(path, lambda: ('Not Found', 404))()
        new_path = f'/v1/{path}'
        if request.query_string:
            new_path += f'?{request.query_string.decode("utf-8")}'
        return redirect(new_path, code=301)

    # ── Root paths (no /v1 prefix) ──
    @app.route('/health')
    def health():
        from flask import jsonify
        from datetime import datetime
        try: import psycopg2; pg = True
        except ImportError: pg = False
        return jsonify({'status': 'ok', 'time': datetime.now().isoformat(), 'pg': pg})

    # Global error handlers
    from .errors import ErrorCode, error_response

    @app.errorhandler(404)
    def not_found(e):
        return error_response(ErrorCode.NOT_FOUND, "Endpoint not found", 404)

    @app.errorhandler(500)
    def server_error(e):
        return error_response(ErrorCode.INTERNAL_ERROR, "Internal server error", 500)

    print(f'[LLM] {os.environ.get("LLM_MODEL", "deepseek-v4-pro")} @ {os.environ.get("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")}')
    print(f'[API]  Swagger UI → http://localhost:5050/apidocs')
    print(f'[API]  API Base   → http://localhost:5050/v1')
    print(f'[Auth] {"Enabled" if os.environ.get("API_KEY", "").strip() else "Disabled (local dev mode)"}')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='127.0.0.1', port=5050, debug=False)
