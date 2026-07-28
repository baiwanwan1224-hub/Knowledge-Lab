"""SQLite response cache — lightweight, single-user, TTL-based."""
import os, sqlite3, json, hashlib, time, logging
from .constants import MODEL_VERSION

logger = logging.getLogger(__name__)
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'cache.db')
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)

def _conn():
    c = sqlite3.connect(_DB_PATH)
    c.execute('''CREATE TABLE IF NOT EXISTS cache (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        model_version TEXT NOT NULL,
        created_at REAL NOT NULL,
        ttl INTEGER DEFAULT 2592000
    )''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_cache_prefix ON cache(key)')
    c.commit()
    return c

def _make_key(prefix: str, **parts) -> str:
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False)
    h = hashlib.sha1(raw.encode()).hexdigest()[:12]
    return f"{prefix}:{h}"

def get(prefix: str, model_version: str = None, **parts):
    key = _make_key(prefix, **parts)
    mv = model_version or MODEL_VERSION
    try:
        c = _conn()
        row = c.execute('SELECT value, model_version, created_at, ttl FROM cache WHERE key=?', (key,)).fetchone()
        c.close()
        if not row: return None
        if row[1] != mv: return None
        if time.time() - row[2] > row[3]: return None
        return json.loads(row[0])
    except sqlite3.Error as e:
        logger.warning(f"Cache read failed: {e}")
        return None
    except Exception:
        return None

def set(prefix: str, value, model_version: str = None, ttl: int = 2592000, **parts):
    key = _make_key(prefix, **parts)
    mv = model_version or MODEL_VERSION
    try:
        c = _conn()
        c.execute('INSERT OR REPLACE INTO cache (key,value,model_version,created_at,ttl) VALUES (?,?,?,?,?)',
                  (key, json.dumps(value, ensure_ascii=False), mv, time.time(), ttl))
        c.commit(); c.close()
    except sqlite3.Error as e:
        logger.warning(f"Cache write failed: {e}")

def invalidate(prefix: str, **parts):
    key = _make_key(prefix, **parts)
    try:
        c = _conn(); c.execute('DELETE FROM cache WHERE key=?', (key,)); c.commit(); c.close()
    except sqlite3.Error:
        pass

def invalidate_by_prefix(prefix: str):
    try:
        c = _conn(); c.execute('DELETE FROM cache WHERE key LIKE ?', (f'{prefix}:%',)); c.commit(); c.close()
    except sqlite3.Error:
        pass

def stats():
    try:
        c = _conn()
        total = c.execute('SELECT COUNT(*) FROM cache').fetchone()[0]
        c.close()
        return {'total_entries': total}
    except Exception:
        return {'total_entries': 0}
