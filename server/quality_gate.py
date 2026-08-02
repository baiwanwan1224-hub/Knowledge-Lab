"""Quality Gate — L0-003 content quality enforcement.

Enforces the L0-003 standard that only `status: ready` notes may
be used for quiz generation. Provides:
  - Status validation and normalization
  - Batch promotion from draft/imported → ready
  - Startup statistics (ready/draft/total counts)
  - L0-003 content quality checklist
"""

import os
import sys

# ── Valid statuses per L0-003 ──
VALID_STATUSES = {'draft', 'ready', 'imported', 'needs_revision', 'archived', 'outdated'}
QUIZ_ELIGIBLE_STATUSES = {'ready'}

# ── L0-003 Quality Checklist (5 criteria) ──
QUALITY_CRITERIA = [
    {
        'id': 'concept_accuracy',
        'label': '概念准确度',
        'description': '核心概念定义正确，无事实错误',
        'weight': 0.30,
    },
    {
        'id': 'has_example',
        'label': '案例存在性',
        'description': '包含至少一个具体案例或应用场景',
        'weight': 0.20,
    },
    {
        'id': 'quiz_generatable',
        'label': '可出题性',
        'description': '内容足够丰富，可以生成有意义的测验问题',
        'weight': 0.25,
    },
    {
        'id': 'source_traceable',
        'label': '来源可追溯',
        'description': '来源信息完整，可以回溯到原始内容',
        'weight': 0.15,
    },
    {
        'id': 'format_standard',
        'label': '格式规范性',
        'description': 'Markdown格式规范，frontmatter完整，有标题和分段',
        'weight': 0.10,
    },
]


def validate_status(status: str) -> str:
    """Normalize and validate note status."""
    status = status.strip().lower() if status else 'draft'
    return status if status in VALID_STATUSES else 'draft'


def is_quiz_eligible(status: str) -> bool:
    """Check if a note status qualifies for quiz generation."""
    return validate_status(status) in QUIZ_ELIGIBLE_STATUSES


def scan_vault_stats(notes_dir: str = None) -> dict:
    """Scan vault notes and return quality statistics.

    Returns:
        {'total': int, 'ready': int, 'draft': int, 'imported': int,
         'needs_revision': int, 'other': int, 'ready_pct': float}
    """
    if notes_dir is None:
        notes_dir = os.path.join(
            os.environ.get('VAULT_PATH', 'vault'),
            'Knowledge Lab', '00_学习笔记'
        )

    stats = {
        'total': 0, 'ready': 0, 'draft': 0,
        'imported': 0, 'needs_revision': 0, 'other': 0,
        'ready_pct': 0.0,
    }

    if not os.path.exists(notes_dir):
        return stats

    for root, dirs, files in os.walk(notes_dir):
        for fname in files:
            if not fname.endswith('.md') or fname.startswith('模板_'):
                continue
            stats['total'] += 1
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read(2000)  # Read first 2KB for frontmatter
            except Exception:
                stats['other'] += 1
                continue

            # Extract status from frontmatter
            status = 'draft'
            in_fm = False
            for line in content.split('\n'):
                if line.strip() == '---':
                    if not in_fm:
                        in_fm = True
                        continue
                    else:
                        break
                if in_fm and line.startswith('status:'):
                    status = line.split(':', 1)[1].strip().strip('"').strip("'")
                    break

            status = validate_status(status)
            if status in stats:
                stats[status] += 1
            else:
                stats['other'] += 1

    if stats['total'] > 0:
        stats['ready_pct'] = round(stats['ready'] / stats['total'] * 100, 1)

    return stats


def print_startup_stats(notes_dir: str = None):
    """Print quality gate stats on startup."""
    stats = scan_vault_stats(notes_dir)
    print(
        f'[QualityGate] {stats["ready"]}/{stats["total"]} notes ready '
        f'({stats["ready_pct"]}%). '
        f'{stats["draft"]} draft, {stats["imported"]} imported, '
        f'{stats["needs_revision"]} needs_revision.',
        file=sys.stderr,
    )
    if stats['ready'] == 0 and stats['total'] > 0:
        print(
            f'[QualityGate] WARNING: 0 of {stats["total"]} notes are ready. '
            f'Quiz generation will return empty results. '
            f'Use the dashboard to review and approve draft notes.',
            file=sys.stderr,
        )
    return stats


def batch_promote(notes_dir: str = None, source_filter: str = None, dry_run: bool = False) -> int:
    """Batch-promote draft/imported notes to ready status.

    Args:
        notes_dir: Path to notes directory
        source_filter: Only promote notes matching this source substring
        dry_run: If True, only count without modifying files

    Returns:
        Number of notes promoted
    """
    if notes_dir is None:
        notes_dir = os.path.join(
            os.environ.get('VAULT_PATH', 'vault'),
            'Knowledge Lab', '00_学习笔记'
        )

    promoted = 0
    for root, dirs, files in os.walk(notes_dir):
        for fname in sorted(files):
            if not fname.endswith('.md') or fname.startswith('模板_'):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                continue

            # Check source filter
            if source_filter and source_filter not in content:
                continue

            # Only promote non-ready notes
            if 'status: ready' in content.split('---')[1] if '---' in content else False:
                continue

            if dry_run:
                promoted += 1
                continue

            # Perform the promotion
            new_content = content.replace('status: draft', 'status: ready')
            new_content = new_content.replace('status: imported', 'status: ready')
            new_content = new_content.replace('status: needs_revision', 'status: ready')

            if new_content != content:
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                promoted += 1

    return promoted
