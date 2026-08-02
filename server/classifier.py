#!/usr/bin/env python3
"""
Topic Classifier — RAG pipeline for auto-classifying notes into L0-005 topic categories.
DS (DeepSeek) for primary classification · M3 (MiniMax) for review.
Vector embeddings via DeepSeek Embedding API with cosine similarity pre-filter.
"""
import os, sys, json, hashlib, time
from datetime import datetime
from pathlib import Path

import numpy as np
import requests

# Load .env first
_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE, 'r', encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# ── Config ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
TOPIC_VECTORS_FILE = DATA_DIR / 'topic_vectors.json'

LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
LLM_API_URL = os.environ.get('LLM_API_URL', 'https://api.deepseek.com/v1/chat/completions')
LLM_MODEL = os.environ.get('LLM_MODEL', 'deepseek-v4-pro')
EMBEDDING_API_URL = os.environ.get('EMBEDDING_API_URL', 'https://api.deepseek.com/v1/embeddings')
EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'deepseek-chat')  # DeepSeek chat model for embeddings
MINIMAX_API_KEY = os.environ.get('MINIMAX_API_KEY', '')
MINIMAX_API_URL = 'https://api.minimaxi.com/v1/text/chatcompletion_v2'
ZHIPU_API_KEY = os.environ.get('ZHIPU_API_KEY', '')
ZHIPU_API_URL = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
ZHIPU_MODEL = 'glm-4'

# ── L0-005 Topic Taxonomy ──────────────────────────────
TOPICS = {
    "AI Agent & 架构": {
        "desc": "AI Agent 系统架构、多 Agent 协作、工具调用、记忆系统、上下文管理、Agent 设计模式",
        "keywords": ["Agent", "架构", "上下文工程", "tool calling", "memory", "orchestration", "工作流"]
    },
    "LLM & Prompt 工程": {
        "desc": "大语言模型原理、Prompt 设计与优化、提示链、Few-shot、CoT、模型选择与对比",
        "keywords": ["Prompt", "LLM", "token", "提示词", "思维链", "few-shot", "temperature", "模型对比"]
    },
    "RAG & 检索系统": {
        "desc": "检索增强生成、向量数据库、Embedding、语义搜索、文档分块、HyDE、重排序",
        "keywords": ["RAG", "向量检索", "embedding", "知识库", "chunking", "语义搜索", "retrieval"]
    },
    "AI 产品设计": {
        "desc": "AI 产品 UX 设计、人机交互模式、AI 原生交互、原型设计、产品思维",
        "keywords": ["UX", "交互设计", "原型", "AI Native", "产品设计", "HMI", "用户体验"]
    },
    "AI 评测 & 质量": {
        "desc": "AI 系统评测方法、基准测试、质量门禁、A/B 测试、性能评估、LLM-as-Judge",
        "keywords": ["评测", "eval", "benchmark", "QA", "质量", "测试", "准确率", "召回率"]
    },
    "数据驱动决策": {
        "desc": "数据分析、指标体系、北极星指标、A/B 实验、用户行为分析、数据看板",
        "keywords": ["数据分析", "指标", "metric", "A/B测试", "实验", "dashboard", "增长模型"]
    },
    "商业化 & 定价": {
        "desc": "SaaS 定价策略、商业模式、变现、Freemium、PLG、定价心理学、价值度量",
        "keywords": ["定价", "商业化", "monetization", "freemium", "PLG", "变现", "revenue"]
    },
    "增长 & 发布": {
        "desc": "产品增长、发布策略、GTM、冷启动、渠道策略、增长循环、产品发布",
        "keywords": ["增长", "发布", "launch", "GTM", "冷启动", "渠道", "growth loop", "获客"]
    },
    "用户研究 & ICP": {
        "desc": "用户研究、客户访谈、JTBD、用户画像、ICP 定义、需求发现、Mom Test",
        "keywords": ["用户研究", "客户访谈", "JTBD", "ICP", "persona", "需求", "discovery"]
    },
    "产品策略 & 路线图": {
        "desc": "产品战略、路线图规划、优先级排序、OKR 设定、产品愿景、权衡决策",
        "keywords": ["产品策略", "路线图", "优先级", "OKR", "愿景", "trade-off", "战略"]
    },
    "工程协作 & 流程": {
        "desc": "PRD 撰写、敏捷开发、Sprint 规划、需求文档、技术规格、项目管理",
        "keywords": ["PRD", "敏捷", "sprint", "开发流程", "需求文档", "spec", "项目管理"]
    },
    "内容 & SEO/GEO": {
        "desc": "内容策略、SEO 优化、AI 搜索可见性（GEO/AEO）、内容营销、关键词研究",
        "keywords": ["SEO", "GEO", "内容策略", "关键词", "搜索优化", "content marketing"]
    },
    "组织 & 沟通": {
        "desc": "团队管理、利益相关者沟通、高管汇报、组织设计、跨部门协作、文化建设",
        "keywords": ["利益相关者", "沟通", "组织", "团队", "stakeholder", "culture", "汇报"]
    },
    "竞争 & 定位": {
        "desc": "竞争分析、市场定位、SWOT、Porter's Five Forces、差异化策略、市场研究",
        "keywords": ["竞争", "定位", "SWOT", "差异化", "市场分析", "positioning", "competitor"]
    },
    "AI 开发工具": {
        "desc": "AI 编程工具、Vibe Coding、Copilot、Cursor、Claude Code、开发效率、工具评估",
        "keywords": ["AI编程", "Vibe Coding", "Copilot", "开发工具", "IDE", "自动化", "效率"]
    },
}

TOPIC_NAMES = list(TOPICS.keys())


# ── Embedding ───────────────────────────────────────────
def _call_embedding_api(texts: list[str]) -> list[list[float]] | None:
    """Call DeepSeek Embedding API. Returns list of embedding vectors or None on failure."""
    try:
        resp = requests.post(
            EMBEDDING_API_URL,
            headers={'Authorization': f'Bearer {LLM_API_KEY}', 'Content-Type': 'application/json'},
            json={'model': EMBEDDING_MODEL, 'input': texts},
            timeout=30
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return [item['embedding'] for item in data.get('data', [])]
    except Exception:
        return None


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def _build_keyword_vector(text: str, topic_keywords: list[str]) -> np.ndarray:
    """Build a simple keyword-frequency vector for fallback similarity.
    Each dimension = normalized count of keyword matches in text."""
    text_lower = text.lower()
    vec = np.zeros(len(topic_keywords))
    for i, kw in enumerate(topic_keywords):
        vec[i] = text_lower.count(kw.lower())
    return vec


# ── Topic Vector Store ─────────────────────────────────
def load_or_build_topic_vectors() -> dict[str, np.ndarray]:
    """Load cached topic vectors, or build from embedding API."""
    if TOPIC_VECTORS_FILE.exists():
        try:
            with open(TOPIC_VECTORS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return {k: np.array(v) for k, v in data.items()}
        except Exception:
            pass

    # Try embedding API first
    topic_texts = [f"{name}: {info['desc']} {' '.join(info['keywords'])}" for name, info in TOPICS.items()]
    embeddings = _call_embedding_api(topic_texts)

    vectors = {}
    if embeddings and len(embeddings) == len(TOPIC_NAMES):
        for name, emb in zip(TOPIC_NAMES, embeddings):
            vectors[name] = np.array(emb)
    else:
        # Fallback: keyword-based vectors (all zeros, will skip vector pre-filter)
        for name in TOPIC_NAMES:
            vectors[name] = np.zeros(1)

    # Cache to disk
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(TOPIC_VECTORS_FILE, 'w', encoding='utf-8') as f:
        json.dump({k: v.tolist() for k, v in vectors.items()}, f, ensure_ascii=False)

    return vectors


# ── LLM Classification (DS) ────────────────────────────
def _ds_classify(note_content: str, candidates: list[str]) -> list[str]:
    """DeepSeek classifies note into 1-3 topics from candidate list."""
    topics_desc = '\n'.join([f"- {t}: {TOPICS[t]['desc']}" for t in candidates])
    prompt = f"""你是AI产品管理内容分类专家。请阅读以下笔记内容，判断它属于哪些主题类别。

## 候选主题（从向量相似度预筛选）
{topics_desc}

## 笔记内容
{note_content[:3000]}

## 要求
1. 从候选主题中选择 1-3 个最匹配的
2. 如果笔记确实不属于任何候选主题，可以从完整15个主题中选择
3. 只输出主题名称，JSON 格式：{{"topics": ["主题1", "主题2"]}}

直接输出JSON："""

    try:
        resp = requests.post(
            LLM_API_URL,
            headers={'Authorization': f'Bearer {LLM_API_KEY}', 'Content-Type': 'application/json'},
            json={'model': LLM_MODEL, 'messages': [
                {'role': 'system', 'content': '你是内容分类专家，严格按JSON格式输出。'},
                {'role': 'user', 'content': prompt}
            ], 'temperature': 0.2, 'max_tokens': 300},
            timeout=60
        )
        if resp.status_code != 200:
            return []
        content = resp.json()['choices'][0]['message']['content'].strip()
        # Parse JSON
        if content.startswith('```'): content = content.split('\n', 1)[1]
        if content.endswith('```'): content = content[:-3]
        import re
        match = re.search(r'\{.*\}', content, re.DOTALL)
        data = json.loads(match.group()) if match else json.loads(content)
        topics = data.get('topics', [])
        # Validate topics exist in taxonomy
        return [t for t in topics if t in TOPICS]
    except Exception:
        return []


# ── M3 Review ───────────────────────────────────────────
def _m3_review(note_content: str, ds_topics: list[str]) -> list[str]:
    """MiniMax M3 reviews DS classification for missing/incorrect topics."""
    if not MINIMAX_API_KEY:
        return ds_topics

    all_topics_desc = '\n'.join([f"- {t}: {TOPICS[t]['desc']}" for t in TOPIC_NAMES])
    prompt = f"""你是内容分类审核专家。DeepSeek 对以下笔记进行了主题分类，请审核结果。

## 完整主题列表（15个）
{all_topics_desc}

## 笔记内容
{note_content[:2000]}

## DS 分类结果
{json.dumps(ds_topics, ensure_ascii=False)}

## 审核要求
1. 检查是否有遗漏的主题（笔记讨论了但DS没标注的）
2. 检查是否有错误标注（DS标注了但笔记实际不相关的）
3. 输出修正后的主题列表，JSON 格式：{{"topics": ["主题1", "主题2"]}}

直接输出JSON："""

    try:
        resp = requests.post(
            MINIMAX_API_URL,
            headers={'Authorization': f'Bearer {MINIMAX_API_KEY}', 'Content-Type': 'application/json'},
            json={'model': 'MiniMax-M3', 'messages': [
                {'role': 'system', 'content': '你是内容审核专家，严格按JSON格式输出。'},
                {'role': 'user', 'content': prompt}
            ], 'temperature': 0.1, 'max_tokens': 300},
            timeout=60
        )
        if resp.status_code != 200:
            return ds_topics
        content = resp.json()['choices'][0]['message']['content'].strip()
        if content.startswith('```'): content = content.split('\n', 1)[1]
        if content.endswith('```'): content = content[:-3]
        import re
        match = re.search(r'\{.*\}', content, re.DOTALL)
        data = json.loads(match.group()) if match else json.loads(content)
        m3_topics = data.get('topics', [])
        validated = [t for t in m3_topics if t in TOPICS]
        return validated if validated else ds_topics
    except Exception:
        return ds_topics


# ── GLM Review (Zhipu) ─────────────────────────────────
def _glm_review(note_content: str, current_topics: list[str]) -> list[str]:
    """GLM-4 (Zhipu) third-level review: catches DS/M3 blind spots."""
    if not ZHIPU_API_KEY:
        return current_topics

    all_topics_desc = '\n'.join([f"- {t}: {TOPICS[t]['desc']}" for t in TOPIC_NAMES])
    prompt = f"""你是内容分类终审专家。请对以下笔记的主题分类进行最终审核。

## 完整主题列表（15个）
{all_topics_desc}

## 笔记内容
{note_content[:2000]}

## 当前分类结果（经 DS + M3 审核）
{json.dumps(current_topics, ensure_ascii=False)}

## 终审要求
1. 检查是否仍有遗漏的主题
2. 检查是否有误标（笔记不相关但被标记的）
3. 输出最终主题列表，JSON 格式：{{"topics": ["主题1", "主题2"]}}

直接输出JSON："""

    try:
        resp = requests.post(
            ZHIPU_API_URL,
            headers={'Authorization': f'Bearer {ZHIPU_API_KEY}', 'Content-Type': 'application/json'},
            json={'model': ZHIPU_MODEL, 'messages': [
                {'role': 'system', 'content': '你是内容分类终审专家，严格按JSON格式输出。'},
                {'role': 'user', 'content': prompt}
            ], 'temperature': 0.1, 'max_tokens': 300},
            timeout=60
        )
        if resp.status_code != 200:
            return current_topics
        content = resp.json()['choices'][0]['message']['content'].strip()
        if content.startswith('```'): content = content.split('\n', 1)[1]
        if content.endswith('```'): content = content[:-3]
        import re
        match = re.search(r'\{.*\}', content, re.DOTALL)
        data = json.loads(match.group()) if match else json.loads(content)
        glm_topics = data.get('topics', [])
        validated = [t for t in glm_topics if t in TOPICS]
        return validated if validated else current_topics
    except Exception:
        return current_topics


# ── Main Classification Pipeline ───────────────────────
class TopicClassifier:
    """RAG-based topic classifier with DS + M3 dual-model pipeline."""

    def __init__(self):
        self._vectors = None

    @property
    def vectors(self) -> dict[str, np.ndarray]:
        if self._vectors is None:
            self._vectors = load_or_build_topic_vectors()
        return self._vectors

    def classify(self, note_content: str, use_m3_review: bool = True, use_glm_review: bool = True) -> list[str]:
        """Classify a note into L0-005 topic categories.

        Pipeline: keyword pre-filter → DS classify → M3 review → GLM final audit
        """
        if not note_content or not LLM_API_KEY:
            return []

        # Step 1: Keyword pre-filter — find top-5 candidate topics
        candidates = self._vector_filter(note_content, top_k=5)

        # Fallback: if no keyword matches, use full taxonomy for LLM classification
        if not candidates:
            candidates = list(TOPICS.keys())

        # Step 2: DS primary classification
        ds_topics = _ds_classify(note_content, candidates)

        # Step 2b: If DS fails, try GLM as primary classifier
        if not ds_topics and ZHIPU_API_KEY:
            ds_topics = _glm_review(note_content, candidates[:5])
        # Step 2c: If both fail, use keyword pre-filter top results
        if not ds_topics:
            ds_topics = [c for c in candidates[:3] if c in TOPICS]

        # Step 3: M3 review
        if use_m3_review and MINIMAX_API_KEY and ds_topics:
            topics_after_m3 = _m3_review(note_content, ds_topics)
        else:
            topics_after_m3 = ds_topics

        # Step 4: GLM final audit
        if use_glm_review and ZHIPU_API_KEY and topics_after_m3:
            final_topics = _glm_review(note_content, topics_after_m3)
        else:
            final_topics = topics_after_m3

        return final_topics[:5]  # Max 5 topics per note

    def _vector_filter(self, note_content: str, top_k: int = 5, min_score: int = 1) -> list[str]:
        """Find top-k candidate topics via keyword similarity.

        Only returns topics with score >= min_score. Does NOT pad with
        zero-score topics — that would fabricate unrelated labels.
        """
        scores = []
        note_lower = note_content.lower()
        for name, info in TOPICS.items():
            score = sum(1 for kw in info['keywords'] if kw.lower() in note_lower)
            scores.append((name, score))
        scores.sort(key=lambda x: -x[1])
        result = [name for name, s in scores if s >= min_score]
        return result[:top_k]

    def batch_classify(self, note_paths: list[str], use_m3: bool = True) -> dict:
        """Batch classify multiple notes. Returns {path: [topics]}."""
        results = {}
        total = len(note_paths)
        for i, path in enumerate(note_paths):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Extract body (skip frontmatter)
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    body = parts[2] if len(parts) > 2 else content
                else:
                    body = content
                topics = self.classify(body, use_m3_review=use_m3)
                results[path] = topics
                print(f'[{i+1}/{total}] {Path(path).name}: {topics}')
            except Exception as e:
                print(f'[{i+1}/{total}] {Path(path).name}: ERROR - {e}')
                results[path] = []
        return results


# ── CLI ─────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Topic Classifier CLI')
    parser.add_argument('--file', help='Single note file to classify')
    parser.add_argument('--batch', help='Directory to batch classify')
    parser.add_argument('--no-m3', action='store_true', help='Skip M3 review')
    parser.add_argument('--text', help='Classify raw text (for testing)')
    args = parser.parse_args()

    classifier = TopicClassifier()

    if args.text:
        topics = classifier.classify(args.text, use_m3_review=not args.no_m3)
        print(json.dumps({'topics': topics}, ensure_ascii=False, indent=2))
    elif args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            content = f.read()
        if content.startswith('---'):
            parts = content.split('---', 2)
            body = parts[2] if len(parts) > 2 else content
        else:
            body = content
        topics = classifier.classify(body, use_m3_review=not args.no_m3)
        print(json.dumps({'file': args.file, 'topics': topics}, ensure_ascii=False, indent=2))
    elif args.batch:
        paths = list(Path(args.batch).glob('*.md'))
        results = classifier.batch_classify([str(p) for p in paths], use_m3=not args.no_m3)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        # Quick self-test: classify the L0-005 standard itself
        std_path = Path(__file__).resolve().parent.parent / 'standards' / '_STANDARD_主题分类.md'
        if std_path.exists():
            with open(std_path, 'r', encoding='utf-8') as f:
                content = f.read()
            body = content.split('---', 2)[2] if content.startswith('---') else content
            topics = classifier.classify(body, use_m3_review=not args.no_m3)
            print(f'Self-test: {std_path.name} → {topics}')
