"""YAML Frontmatter Utilities — unified parsing for all Markdown notes.

Provides a single source of truth for frontmatter parsing, replacing the
ad-hoc line-by-line parsing scattered across notes.py and dashboard_v2.html.
"""

import json
import re
from typing import Any


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from Markdown content.

    Args:
        content: Full Markdown text (may or may not start with ---)

    Returns:
        (metadata_dict, body_text)
        - metadata_dict: Parsed frontmatter as dict (empty if none found)
        - body_text: Content after frontmatter closing --- (full content if no frontmatter)
    """
    if not content:
        return {}, ""

    if not content.startswith('---'):
        return {}, content

    # Find closing ---
    end_idx = content.find('---', 3)
    if end_idx == -1:
        return {}, content

    fm_text = content[3:end_idx].strip()
    body = content[end_idx + 3:].lstrip('\n')

    meta = {}
    for line in fm_text.split('\n'):
        line = line.strip()
        if not line or ':' not in line:
            continue

        key, _, value = line.partition(':')
        key = key.strip()
        value = value.strip()

        # Remove surrounding quotes
        if len(value) >= 2:
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]

        # Try parsing as JSON (for arrays like ["a", "b"])
        if value.startswith('['):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass

        meta[key] = value

    return meta, body


def build_frontmatter(
    title: str = "",
    topics: list[str] | None = None,
    source: str = "",
    date: str = "",
    status: str = "draft",
    author: str = "",
    extra: dict[str, Any] | None = None,
) -> str:
    """Build a YAML frontmatter block string.

    Args:
        title: Note title
        topics: List of topic strings
        source: Source URL or identifier
        date: Date string (YYYY-MM-DD)
        status: Note status per L0-003 (draft/ready/imported/needs_revision/archived)
        author: Author name
        extra: Additional fields to include

    Returns:
        Formatted frontmatter block with opening/closing ---
    """
    lines = ['---']

    if title:
        escaped_title = title.replace('"', '\\"')
        lines.append(f'title: "{escaped_title}"')

    if topics:
        lines.append(f'topics: {json.dumps(topics, ensure_ascii=False)}')
    else:
        lines.append('topics: []')

    if source:
        lines.append(f'source: "{source}"')

    if date:
        lines.append(f'date: {date}')

    lines.append(f'status: {status}')

    if author:
        lines.append(f'author: "{author}"')

    if extra:
        for k, v in extra.items():
            if isinstance(v, (list, dict)):
                lines.append(f'{k}: {json.dumps(v, ensure_ascii=False)}')
            elif isinstance(v, str):
                lines.append(f'{k}: "{v}"')
            else:
                lines.append(f'{k}: {v}')

    lines.append('---')
    return '\n'.join(lines)


def validate_status(status: str) -> str:
    """Normalize and validate note status per L0-003.

    Valid statuses: draft, ready, imported, needs_revision, archived, outdated
    """
    VALID_STATUSES = {'draft', 'ready', 'imported', 'needs_revision', 'archived', 'outdated'}
    status = status.strip().lower()
    if status not in VALID_STATUSES:
        return 'draft'  # Default fallback
    return status


def is_ready_note(content: str) -> bool:
    """Check if a note has status: ready."""
    meta, _ = parse_frontmatter(content)
    return meta.get('status', 'draft') == 'ready'
