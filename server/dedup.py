"""Content Deduplication — SHA-256 fingerprinting + 5-gram Jaccard similarity.

Prevents duplicate notes from being created during import. Uses two strategies:
  1. Exact match: SHA-256 hash of normalized content
  2. Near-duplicate: 5-gram character-level Jaccard similarity >= threshold

Also provides migration tools:
  --scan: scan existing notes and report duplicates
  --merge: merge duplicate pairs (keep older, delete newer)
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── Config ──
DEFAULT_THRESHOLD = float(os.environ.get('DEDUP_THRESHOLD', '0.85'))


# ── Fingerprint ──

def _normalize(text: str) -> str:
    """Normalize text for fingerprinting: lowercase, collapse whitespace."""
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def compute_fingerprint(text: str) -> str:
    """Compute SHA-256 fingerprint of normalized text."""
    normalized = _normalize(text)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def _char_ngrams(text: str, n: int = 5) -> set[str]:
    """Extract character n-grams from text."""
    text = _normalize(text)
    if len(text) < n:
        return {text}
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def jaccard_similarity(text_a: str, text_b: str, n: int = 5) -> float:
    """Compute Jaccard similarity of character n-grams between two texts."""
    ngrams_a = _char_ngrams(text_a, n)
    ngrams_b = _char_ngrams(text_b, n)
    if not ngrams_a or not ngrams_b:
        return 0.0
    intersection = ngrams_a & ngrams_b
    union = ngrams_a | ngrams_b
    return len(intersection) / len(union)


# ── Dedup Check ──

def is_duplicate(
    content: str,
    existing_dir: str,
    threshold: float = DEFAULT_THRESHOLD,
) -> tuple[bool, Optional[str]]:
    """Check if content is a duplicate of any existing note.

    Args:
        content: The new note content to check
        existing_dir: Directory containing existing notes
        threshold: Jaccard similarity threshold (0.0-1.0)

    Returns:
        (is_duplicate, matched_file) — matched_file is the path of the
        existing note if duplicate, None otherwise.
    """
    if not os.path.exists(existing_dir):
        return False, None

    fp = compute_fingerprint(content)

    for root, dirs, files in os.walk(existing_dir):
        for fname in files:
            if not fname.endswith('.md') or fname.startswith('模板_'):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    existing = f.read()
            except Exception:
                continue

            # Check 1: Exact fingerprint match
            existing_fp = compute_fingerprint(existing)
            if fp == existing_fp:
                return True, fpath

            # Check 2: Near-duplicate via Jaccard
            similarity = jaccard_similarity(content, existing)
            if similarity >= threshold:
                return True, fpath

    return False, None


# ── Migration Tools ──

def scan_duplicates(notes_dir: str, threshold: float = DEFAULT_THRESHOLD) -> list[dict]:
    """Scan all notes and find duplicate pairs.

    Returns list of {'file_a': path, 'file_b': path, 'similarity': float}
    """
    if not os.path.exists(notes_dir):
        return []

    # Load all notes
    notes = []
    for root, dirs, files in os.walk(notes_dir):
        for fname in sorted(files):
            if not fname.endswith('.md') or fname.startswith('模板_'):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
                notes.append({
                    'path': fpath,
                    'content': content,
                    'mtime': os.path.getmtime(fpath),
                })
            except Exception:
                continue

    duplicates = []
    checked = set()

    for i, note_a in enumerate(notes):
        fp_a = compute_fingerprint(note_a['content'])
        if fp_a in checked:
            continue
        checked.add(fp_a)

        for j, note_b in enumerate(notes):
            if j <= i:
                continue

            similarity = jaccard_similarity(note_a['content'], note_b['content'])
            if similarity >= threshold:
                duplicates.append({
                    'file_a': note_a['path'],
                    'file_b': note_b['path'],
                    'similarity': round(similarity, 3),
                })

    return duplicates


def merge_duplicates(notes_dir: str, threshold: float = DEFAULT_THRESHOLD, dry_run: bool = True) -> int:
    """Find duplicates and merge: keep the older file, delete the newer.

    When merging, topics from the deleted file are merged into the kept file.

    Returns:
        Number of files deleted.
    """
    pairs = scan_duplicates(notes_dir, threshold)
    deleted = set()
    merged = 0

    for pair in pairs:
        file_a = pair['file_a']
        file_b = pair['file_b']

        if file_a in deleted or file_b in deleted:
            continue

        # Keep older file, delete newer
        mtime_a = os.path.getmtime(file_a)
        mtime_b = os.path.getmtime(file_b)

        if mtime_a <= mtime_b:
            keep, delete = file_a, file_b
        else:
            keep, delete = file_b, file_a

        if dry_run:
            print(f'  [DRY RUN] Would merge: {os.path.basename(delete)} → {os.path.basename(keep)} (sim={pair["similarity"]})')
            merged += 1
            continue

        # Merge topics from deleted into kept
        try:
            with open(keep, 'r', encoding='utf-8') as f:
                keep_content = f.read()
            with open(delete, 'r', encoding='utf-8') as f:
                delete_content = f.read()

            # Extract topics from both
            import re as _re
            def extract_topics(text):
                match = _re.search(r'topics:\s*(\[.*?\])', text)
                if match:
                    try:
                        return json.loads(match.group(1))
                    except Exception:
                        return []
                return []

            keep_topics = extract_topics(keep_content)
            delete_topics = extract_topics(delete_content)
            merged_topics = list(set(keep_topics + delete_topics))

            # Update topics in kept file
            new_topics_str = json.dumps(merged_topics, ensure_ascii=False)
            keep_content = _re.sub(
                r'topics:\s*\[.*?\]',
                f'topics: {new_topics_str}',
                keep_content,
                count=1,
            )

            with open(keep, 'w', encoding='utf-8') as f:
                f.write(keep_content)

            os.remove(delete)
            deleted.add(delete)
            merged += 1
            print(f'  [MERGE] {os.path.basename(delete)} → {os.path.basename(keep)} (sim={pair["similarity"]})')

        except Exception as e:
            print(f'  [ERROR] Failed to merge {os.path.basename(delete)}: {e}', file=sys.stderr)

    return merged


# ── CLI ──

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Knowledge Lab Dedup Tool')
    parser.add_argument('--scan', action='store_true', help='Scan for duplicates')
    parser.add_argument('--merge', action='store_true', help='Merge duplicates (keep older, delete newer)')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Dry run (default True for --merge)')
    parser.add_argument('--execute', action='store_true', help='Actually execute merge (disable dry-run)')
    parser.add_argument('--threshold', type=float, default=DEFAULT_THRESHOLD, help=f'Similarity threshold (default: {DEFAULT_THRESHOLD})')
    parser.add_argument('--dir', type=str, help='Notes directory path')

    args = parser.parse_args()

    notes_dir = args.dir
    if not notes_dir:
        vault_path = os.environ.get('VAULT_PATH', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'vault'))
        notes_dir = os.path.join(vault_path, 'Knowledge Lab', '00_学习笔记')

    if not os.path.exists(notes_dir):
        print(f'Notes directory not found: {notes_dir}')
        sys.exit(1)

    if args.scan:
        print(f'Scanning {notes_dir} for duplicates (threshold={args.threshold})...')
        pairs = scan_duplicates(notes_dir, args.threshold)
        if not pairs:
            print('  No duplicates found.')
        else:
            print(f'  Found {len(pairs)} duplicate pair(s):')
            for p in pairs:
                print(f'    {os.path.basename(p["file_a"])} ≈ {os.path.basename(p["file_b"])} (sim={p["similarity"]})')
    elif args.merge:
        dry_run = not args.execute
        print(f'{"[DRY RUN] " if dry_run else ""}Merging duplicates (threshold={args.threshold})...')
        merged = merge_duplicates(notes_dir, args.threshold, dry_run=dry_run)
        print(f'  {"Would merge" if dry_run else "Merged"} {merged} files.')
    else:
        parser.print_help()
