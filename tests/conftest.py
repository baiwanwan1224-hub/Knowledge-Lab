"""Pytest fixtures for Knowledge Lab tests."""
import os
import sys
import json
import tempfile
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

# ── Test vault with sample notes (CI has no Obsidian vault) ──
_TEST_VAULT = None


def _setup_test_vault():
    """Create a temporary vault with sample notes for quiz generation tests."""
    global _TEST_VAULT
    if _TEST_VAULT:
        return _TEST_VAULT

    _TEST_VAULT = tempfile.mkdtemp(prefix='kl_test_vault_')
    notes_dir = os.path.join(_TEST_VAULT, 'Knowledge Lab', '00_学习笔记')
    os.makedirs(notes_dir, exist_ok=True)

    sample_notes = {
        'AI产品经理': {
            'title': 'AI产品经理入门方法',
            'topics': ['AI产品经理', 'AI PM'],
        },
        '产品管理': {
            'title': '产品管理完全指南',
            'topics': ['产品管理', 'AI PM'],
        },
        '产品策略': {
            'title': '产品策略与路线图',
            'topics': ['产品策略', '产品管理'],
        },
    }

    for slug, info in sample_notes.items():
        topic_json = json.dumps(info['topics'], ensure_ascii=False)
        content = f"""---
title: "{info['title']}"
topics: {topic_json}
source: "test"
date: 2026-07-26
status: ready
---

# {info['title']}

## 核心概念

这是一篇测试笔记，用于 CI 自动化测试。

## 详细内容

{info['title']}的核心内容包括以下几个方面：

1. 需求分析与用户研究方法
2. 产品路线图与优先级排序
3. 跨团队协作与沟通技巧
4. 数据驱动决策框架

## 可出题的知识点

- 产品经理的核心能力模型
- T型人才结构
- 需求分析的五步法
- 路线图优先级排序框架
"""
        with open(os.path.join(notes_dir, f'{slug}.md'), 'w', encoding='utf-8') as f:
            f.write(content)

    os.environ['VAULT_PATH'] = _TEST_VAULT
    return _TEST_VAULT


@pytest.fixture(scope='module')
def app():
    """Create Flask app for testing."""
    _setup_test_vault()
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
