"""LLM call statistics — SQLite-based, zero-config."""
import os, sqlite3, time
from datetime import datetime

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'stats.db')
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)

def _conn():
    c = sqlite3.connect(_DB_PATH)
    c.execute('''CREATE TABLE IF NOT EXISTS calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        endpoint TEXT NOT NULL,
        model TEXT NOT NULL,
        prompt_tokens INTEGER DEFAULT 0,
        completion_tokens INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0,
        latency_ms INTEGER DEFAULT 0,
        retries INTEGER DEFAULT 0,
        cached INTEGER DEFAULT 0,
        error TEXT
    )''')
    c.commit()
    return c

def record(endpoint: str, model: str, usage: dict, latency_ms: int, retries: int = 0, cached: int = 0, error: str = None):
    try:
        c = _conn()
        c.execute('INSERT INTO calls (ts,endpoint,model,prompt_tokens,completion_tokens,total_tokens,latency_ms,retries,cached,error) VALUES (?,?,?,?,?,?,?,?,?,?)',
                  (datetime.now().isoformat(), endpoint, model,
                   usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0), usage.get('total_tokens', 0),
                   latency_ms, retries, cached, error))
        c.commit(); c.close()
    except Exception:
        pass

def summary(days: int = 7):
    try:
        c = _conn()
        rows = c.execute('SELECT endpoint, COUNT(*) as n, SUM(total_tokens) as tok, SUM(latency_ms) as lat, SUM(cached) as hits FROM calls WHERE ts >= date("now", ?) GROUP BY endpoint', (f'-{days} days',)).fetchall()
        c.close()
        return [{'endpoint': r[0], 'calls': r[1], 'tokens': r[2] or 0, 'latency_ms': r[3] or 0, 'cache_hits': r[4] or 0} for r in rows]
    except Exception:
        return []
