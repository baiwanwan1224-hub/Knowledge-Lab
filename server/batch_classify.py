#!/usr/bin/env python3
"""
Batch Topic Classifier — backfill L0-005 topics for all existing notes.
Reads every .md note in the vault, auto-classifies with DS + M3, updates frontmatter.
Usage: python batch_classify.py [--dry-run] [--no-m3] [--limit N]
"""
import os, sys, json, re, argparse
from pathlib import Path
from datetime import datetime

# Load .env
_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE, 'r', encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from classifier import TopicClassifier

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VAULT_PATH = os.environ.get('VAULT_PATH', str(PROJECT_ROOT / 'vault'))
NOTES_DIR = os.path.join(VAULT_PATH, 'Knowledge Lab', '00_学习笔记')
EXTRA_DIRS = [os.path.join(VAULT_PATH, 'Clippings'), os.path.join(VAULT_PATH, '网页提取')]


def find_all_notes() -> list[str]:
    """Find all .md notes in vault."""
    paths = []
    for search_dir in [NOTES_DIR] + EXTRA_DIRS:
        if not os.path.exists(search_dir):
            continue
        for root, dirs, files in os.walk(search_dir):
            for f in files:
                if f.endswith('.md') and not f.startswith('模板_'):
                    paths.append(os.path.join(root, f))
    return sorted(paths)


def read_note(filepath: str) -> tuple[str, str, str]:
    """Read a note, return (frontmatter, body, full_content)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            return parts[1], parts[2], content
    return '', content, content


def update_topics(filepath: str, topics: list[str], dry_run: bool = False) -> bool:
    """Update topics in a note's frontmatter. Returns True if changed."""
    frontmatter, body, full = read_note(filepath)

    # Check existing topics
    existing = []
    for line in frontmatter.split('\n'):
        if line.startswith('topics:'):
            raw = line.split(':', 1)[1].strip()
            if raw.startswith('['):
                try:
                    existing = json.loads(raw)
                except Exception:
                    existing = [t.strip().strip('"') for t in raw.strip('[]').split(',') if t.strip()]
            break

    # Normalize and compare
    existing_set = set(existing)
    new_set = set(topics)

    if existing_set == new_set:
        return False  # No change

    # Build new frontmatter
    new_topics_line = f'topics: {json.dumps(topics, ensure_ascii=False)}'
    new_frontmatter_lines = []
    replaced = False
    for line in frontmatter.split('\n'):
        if line.startswith('topics:'):
            new_frontmatter_lines.append(new_topics_line)
            replaced = True
        else:
            new_frontmatter_lines.append(line)

    if not replaced:
        # Add topics after title line
        inserted = False
        result_lines = []
        for line in new_frontmatter_lines:
            result_lines.append(line)
            if line.startswith('title:') and not inserted:
                result_lines.append(new_topics_line)
                inserted = True
        new_frontmatter_lines = result_lines

    new_frontmatter = '\n'.join(new_frontmatter_lines)
    new_content = f'---{new_frontmatter}---{body}'

    if dry_run:
        print(f'  [DRY-RUN] {os.path.basename(filepath)}: {existing} → {topics}')
        return True

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    return True


def main():
    parser = argparse.ArgumentParser(description='Batch classify notes with L0-005 topics')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without writing')
    parser.add_argument('--no-m3', action='store_true', help='Skip M3 review (faster)')
    parser.add_argument('--limit', type=int, default=0, help='Limit to first N notes')
    args = parser.parse_args()

    paths = find_all_notes()
    if args.limit:
        paths = paths[:args.limit]

    print(f'Found {len(paths)} notes to classify')
    if args.dry_run:
        print('[DRY-RUN MODE] No files will be modified')

    classifier = TopicClassifier()
    stats = {'total': len(paths), 'classified': 0, 'changed': 0, 'skipped': 0, 'errors': 0}

    for i, path in enumerate(paths):
        name = os.path.basename(path)
        try:
            _, body, _ = read_note(path)
            topics = classifier.classify(body, use_m3_review=not args.no_m3)

            if not topics:
                print(f'[{i+1}/{len(paths)}] {name}: ⚠️ No topics classified, skipping')
                stats['skipped'] += 1
                continue

            stats['classified'] += 1
            changed = update_topics(path, topics, dry_run=args.dry_run)
            if changed:
                stats['changed'] += 1
                marker = '📝' if not args.dry_run else '🔍'
                print(f'[{i+1}/{len(paths)}] {name}: {marker} {topics}')
            else:
                print(f'[{i+1}/{len(paths)}] {name}: ✅ Unchanged ({topics})')

        except Exception as e:
            stats['errors'] += 1
            print(f'[{i+1}/{len(paths)}] {name}: ❌ {e}')

    print(f'\n{"="*50}')
    print(f'Done. {stats["total"]} notes scanned')
    print(f'  Classified: {stats["classified"]}')
    print(f'  Changed:    {stats["changed"]}')
    print(f'  Skipped:    {stats["skipped"]}')
    print(f'  Errors:     {stats["errors"]}')
    if args.dry_run:
        print('  (Dry run — no files modified)')


if __name__ == '__main__':
    main()
