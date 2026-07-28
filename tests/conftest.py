"""Pytest fixtures for Knowledge Lab tests."""
import os
import sys
import pytest

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load .env before importing app (same as server/app.py)
_ENV_FILE = os.path.join(PROJECT_ROOT, '.env')
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())


@pytest.fixture(scope='module')
def app():
    """Create Flask app for testing."""
    from server.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture(scope='module')
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture(scope='module')
def runner(app):
    """Flask CLI runner."""
    return app.test_cli_runner()
