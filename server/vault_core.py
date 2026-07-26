"""
Knowledge Lab Vault Core — 原子写入 + WAL + 完整性校验
Provides: atomic_write(), make_note_filename(), vault_integrity_check()
"""
import os, json, hashlib, re, time
from datetime import datetime
from pathlib import Path

# ── Config ──
VAULT_DIR = Path(os.environ.get('VAULT_PATH', os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'vault')))
# Notes live in Knowledge Lab/ subfolder within the vault (shared with Obsidian)
NOTES_DIR = VAULT_DIR / 'Knowledge Lab' / '00_学习笔记'
WRONG_DIR = VAULT_DIR / 'Knowledge Lab' / '01_错题本'
STANDARDS_DIR = VAULT_DIR / 'Knowledge Lab' / '06_产品层'
# Also scan Obsidian-managed folders for notes
EXTRA_NOTE_DIRS = [
    str(VAULT_DIR / 'Clippings'),
    str(VAULT_DIR / '网页提取'),
]
META_DIR = VAULT_DIR / 'Knowledge Lab' / '.vault-meta'
WAL_PATH = META_DIR / 'wal.log'
INTEGRITY_DIR = META_DIR / 'integrity'
LOCK_PATH = META_DIR / '.lock'

# Ensure dirs
for d in [NOTES_DIR, WRONG_DIR, STANDARDS_DIR, META_DIR, INTEGRITY_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════
# 1. Atomic Write
# ═══════════════════════════════════════════════
def atomic_write(filepath: Path, content: str) -> bool:
    """
    Write to .tmp → flush → rename. If crash mid-write, .tmp is orphaned,
    original is intact. No half-written files.
    """
    tmp = filepath.with_suffix(filepath.suffix + '.tmp')
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, filepath)  # atomic on same filesystem
        return True
    except Exception as e:
        print(f'[atomic_write] FAILED: {filepath} — {e}')
        if tmp.exists(): tmp.unlink()
        return False


# ═══════════════════════════════════════════════
# 2. Write-Ahead Log (WAL)
# ═══════════════════════════════════════════════
def wal_append(op: str, filepath: str, content_hash: str = ''):
    """Log operation BEFORE executing write."""
    entry = {
        'ts': datetime.now().isoformat(),
        'op': op,                # CREATE | UPDATE | DELETE
        'path': filepath,
        'hash': content_hash
    }
    with open(WAL_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


def wal_replay() -> list:
    """Replay incomplete WAL entries on startup. Returns list of orphaned .tmp files."""
    if not WAL_PATH.exists():
        return []
    orphaned = []
    with open(WAL_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                fn = Path(entry['path'])
                tmp = fn.with_suffix(fn.suffix + '.tmp')
                if tmp.exists():
                    if entry['op'] == 'CREATE' and not fn.exists():
                        os.replace(tmp, fn)
                        orphaned.append(str(fn))
                    else:
                        tmp.unlink()
            except: pass
    # Archive completed WAL
    archive = META_DIR / f'wal-archived-{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    WAL_PATH.rename(archive)
    return orphaned


# ═══════════════════════════════════════════════
# 3. Naming Convention
# ═══════════════════════════════════════════════
TYPE_MAP = {
    'URL': 'URL', 'WHISPER': 'WHISPR', 'SKILL': 'SKILL',
    'LOCAL': 'LOCAL', 'NOTE': 'NOTE', 'BOOK': 'BOOK'
}

def make_note_filename(note_type: str, title: str, content: str) -> str:
    """Generate M3-designed filename: {YYYYMMDD}_{HHMMSS}_{TYPE}_{SLUG}_{HASH4}.md"""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    t = TYPE_MAP.get(note_type.upper(), 'NOTE')
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower().strip())[:50].strip('-')
    h4 = hashlib.sha256(content.encode('utf-8')).hexdigest()[:4]
    return f'{ts}_{t}_{slug}_{h4}.md'


# ═══════════════════════════════════════════════
# 4. Integrity Check
# ═══════════════════════════════════════════════
def compute_hash(filepath: Path) -> str:
    return hashlib.sha256(filepath.read_bytes()).hexdigest()


def save_integrity_snapshot():
    """Generate integrity snapshot of all notes."""
    files = {}
    for root, _, fnames in os.walk(NOTES_DIR):
        for fn in fnames:
            if fn.endswith('.md') and not fn.startswith('模板_') and '.tmp' not in fn:
                fp = Path(root) / fn
                rel = str(fp.relative_to(VAULT_DIR))
                files[rel] = compute_hash(fp)[:16]

    snap = {
        'timestamp': datetime.now().isoformat(),
        'note_count': len(files),
        'files': files
    }
    snapfile = INTEGRITY_DIR / f'{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(snapfile, 'w', encoding='utf-8') as f:
        json.dump(snap, f, indent=2, ensure_ascii=False)
    return snap


def verify_integrity() -> dict:
    """Check current files against latest integrity snapshot. Returns report."""
    snaps = sorted(INTEGRITY_DIR.glob('*.json'))
    report = {'status': 'ok', 'missing': [], 'changed': [], 'new': [], 'snapshot_used': None}
    if not snaps:
        report['status'] = 'no_snapshot'
        return report

    with open(snaps[-1], 'r', encoding='utf-8') as f:
        prev = json.load(f)
    report['snapshot_used'] = str(snaps[-1].name)

    prev_files = prev.get('files', {})
    current = {}
    if NOTES_DIR.exists():
        for root, _, fnames in os.walk(NOTES_DIR):
            for fn in fnames:
                if fn.endswith('.md') and not fn.startswith('模板_'):
                    fp = Path(root) / fn
                    rel = str(fp.relative_to(VAULT_DIR))
                    current[rel] = compute_hash(fp)[:16]

    for path, h in prev_files.items():
        if path not in current:
            report['missing'].append(path)
        elif current[path] != h:
            report['changed'].append(path)

    for path in current:
        if path not in prev_files:
            report['new'].append(path)

    if report['missing'] or report['changed']:
        report['status'] = 'dirty'
    return report


# ═══════════════════════════════════════════════
# 5. Safe Note Save (orchestrates WAL + atomic_write)
# ═══════════════════════════════════════════════
def safe_save_note(filename: str, content: str) -> bool:
    """Full safe save pipeline: WAL → atomic write → update snapshot."""
    filepath = NOTES_DIR / filename
    content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

    wal_append('CREATE', str(filepath), content_hash)
    ok = atomic_write(filepath, content)
    if ok:
        save_integrity_snapshot()
    return ok
