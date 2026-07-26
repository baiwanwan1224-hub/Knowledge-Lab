"""Decompose PM skills from 3 repos into Knowledge Lab notes."""
import os, re, json, sys
from datetime import datetime

VAULT = r'C:\Users\27224\Documents\Obsidian Vault\Knowledge Lab\00_学习笔记'
DATE = '2026-07-26'

TEMP_DIR = os.environ.get('TEMP', os.environ.get('TMPDIR', '/tmp'))
REPOS = {
    'phuryn': os.path.join(TEMP_DIR, 'pm-skills'),
    'kalyvask': os.path.join(TEMP_DIR, 'pm-evaluation-framework'),
    'amplitude': os.path.join(TEMP_DIR, 'amplitude-skills'),
}

def read_skill(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        raw = f.read()
    fm = {}; body = raw
    if raw.startswith('---'):
        parts = raw.split('---', 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split('\n'):
                if ':' in line:
                    k, v = line.split(':', 1)
                    fm[k.strip()] = v.strip()
            body = parts[2].strip()
    return fm, body

def extract_methodology(body):
    """Extract key methodology: steps, principles, framework."""
    lines = body.strip().split('\n')
    result = []; in_section = False
    for line in lines:
        s = line.strip()
        if not s: continue
        if s.startswith('#') and len(s) < 60:
            result.append(s); in_section = True; continue
        if s.startswith('##') and len(s) < 60:
            result.append(s); in_section = True; continue
        if re.match(r'\d+\.?\s+\*\*', s):
            result.append(s); continue
        if s.startswith('- ') and len(s) < 200:
            result.append(s); continue
        if s.startswith('* ') and len(s) < 200:
            result.append(s); continue
    return '\n'.join(result[:80])

def make_title(name):
    """Convert kebab-case to readable title."""
    t = name.replace('-', ' ').replace('_', ' ')
    # Common PM term mapping
    for k, v in [('prd', 'PRD'), ('okr', 'OKR'), ('swot', 'SWOT'),
                  ('jtbd', 'JTBD'), ('gtm', 'GTM'), ('pmf', 'PMF'),
                  ('ai', 'AI'), ('ui', 'UI'), ('ux', 'UX'),
                  ('mcp', 'MCP'), ('sop', 'SOP'), ('kpi', 'KPI')]:
        t = re.sub(r'\b' + k + r'\b', v, t, flags=re.I)
    return t.title()

count = 0; skipped = 0

for repo_name, repo_path in REPOS.items():
    if not os.path.exists(repo_path): continue
    print(f'\n--- {repo_name} ---')

    for root, dirs, files in os.walk(repo_path):
        for fn in files:
            if fn != 'SKILL.md': continue
            fpath = os.path.join(root, fn)

            # Determine skill name from parent dir
            skill_dir = os.path.basename(os.path.dirname(fpath))
            if skill_dir in ('skills', '.claude'): continue

            try:
                fm, body = read_skill(fpath)
            except:
                skipped += 1; continue

            # Get description and title
            desc = fm.get('description', '')
            # Use description as title if short, otherwise skill dir name
            if desc and len(desc) < 80:
                title = desc
            else:
                title = make_title(skill_dir)

            # Extract core methodology
            core = extract_methodology(body)
            if len(core) < 80:
                # Too short - use full body trimmed
                core = body[:1500]

            # Build note
            if repo_name == 'phuryn':
                source_tag = 'PM Skills Marketplace'
                plugin = os.path.basename(os.path.dirname(os.path.dirname(fpath))) if 'skills' in root else ''
            elif repo_name == 'kalyvask':
                source_tag = 'PM Evaluation Framework'
                plugin = ''
            else:
                source_tag = 'Amplitude Skills'
                plugin = os.path.basename(os.path.dirname(os.path.dirname(fpath))) if 'skills' in root else ''

            full_source = f'{source_tag} ({plugin})' if plugin else source_tag

            note = f"""---
title: {title}
topics: [产品管理, AI PM]
status: imported
source: {full_source}
date: {DATE}
---

# {title}

> 来源: {full_source}
> 原始技能: {skill_dir}

{core}
"""
            # Save
            slug = re.sub(r'[^a-z0-9]+', '-', skill_dir.lower())[:40].strip('-')
            fname = f'{DATE}_PM_{repo_name}_{slug}.md'
            fpath_out = os.path.join(VAULT, fname)

            with open(fpath_out, 'w', encoding='utf-8') as f:
                f.write(note)

            count += 1
            if count % 20 == 0: print(f'  {count} skills processed...')

print(f'\nTotal: {count} skills imported, {skipped} skipped')
