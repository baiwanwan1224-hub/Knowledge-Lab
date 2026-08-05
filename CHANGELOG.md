# Changelog

## v0.2.1 (2026-08-05)

### New Features · 新功能
- **RAG 检索核心** (`server/rag_index.py`) — Markdown `##` 结构分块（216 篇→2582 chunks）+ 智谱 embedding-3 语义索引 + vector/keyword/hybrid 三路检索 + XML context 注入；评测 `scripts/rag_eval.py`（22 条黄金集：vector/hybrid Recall@1 **0.909** / MRR 0.955）
- **中文 keyword 检索增强** — 相邻汉字 bigram 命中加权（无依赖近似分词），keyword Recall@1 **0.273→0.409**
- **长/短记忆压缩** (`server/memory_core.py`) — 滚动摘要 + 关键信息提取 + 忠实度门禁（GLM-4-flash 逐断言校验，≥95% 才入库）+ 短记忆窗口 + XML memory 注入
- **quiz 记忆闭环**（`MEMORY_ENABLE=1`）— 批改后聚合答题表现（知识点/对错/薄弱点）写入学习者记忆（写侧），出题时注入薄弱点侧重（读侧）
- 整合演示 `scripts/rag_memory_demo.py` — 检索→记忆压缩→注入 prompt 全链路

### Bug Fixes · 缺陷修复
- **忠实度门禁原文截断修复** — 原 `source_text[-8000:]` 只取尾部，长对话时开头关键事实被切掉导致真实信息被误拒；改头尾保留、省略中段
- **quiz_generator f-string 语法错误** — f-string 表达式内反斜杠转义与未转义引号混合，在 Python 3.14 下无法编译

### Tests · 测试
- 57→68 pytest passed（截断/记忆集成/bigram 新增）

---

## v0.2.0 (2026-08-01)

### New Features · 新功能
- **七层数据清洗管线** — 5 个新模块（commit `d5f3b66`）：
  - `server/html_cleaner.py`：HTML→纯净文本（去 script/style/注释/tag/实体/样板）
  - `server/transcription_cleaner.py`：YouTube/WAV 转录稿清洗（去时间戳/说话人标签/字幕伪影/去重/合并碎行）
  - `server/frontmatter_utils.py`：YAML frontmatter 统一解析（替换 notes.py / dashboard 的散乱逐行解析）
  - `server/quality_gate.py`：L0-003 质量门禁（仅 `status: ready` 可出题 · 状态校验/批量提升/统计）
  - `server/dedup.py`：内容去重（SHA-256 精确 + 5-gram Jaccard 近似 · `--scan`/`--merge` 迁移工具）
- **修复 7 项 RAG 管线审计缺口**（基于 7/31 审计报告）
- 笔记上传流程（`server/blueprints/notes.py`）集成清洗管线
- 数据清洗管线 skill：`skills/08_data_cleaning_pipeline.md` + `RED_SKILL_KnowledgeLab.md`

### Tests · 测试
- 32/32 pytest passed

---

## v0.1.1 (2026-07-29)

### Bug Fixes · 缺陷修复
- **QA Gate scoring normalized by question type** — short-answer/scenario questions now scored /3 instead of /5, preventing false rejections
- **Empty questions no longer crashes UI** — frontend now shows toast + resets setup instead of zombie buttons
- **Topic dropdown fixed** — frontend-backend API format mismatch resolved; `/v1/topics` returns `{topics: [], counts: {}, notes_count: N}`
- **Subprocess encoding hardened** — all subprocess stdout/stderr forced to UTF-8; `errors='replace'` prevents UnicodeDecodeError on Windows GBK
- **WinError 206 fix** — grade endpoint now uses temp file (`--input-file`) instead of command-line JSON arg
- **Submit button stuck after retake** — `renderQuiz()` now forces `disabled=false` on last question; `exitQuiz()` and `resetQuizSetup()` clean up button state
- **CI vault fixture** — temp vault with sample notes created for GitHub Actions runners

### New Features · 新功能
- **RAG topic classification system (L0-005)** — 15 standardized topic categories; keyword pre-filter → DS classify → M3 review → GLM final audit
- **Auto-classification on import** — notes without user-provided topic get auto-classified via DS+M3+GLM pipeline
- **Batch classification script** (`server/batch_classify.py`) — backfilled 179/201 existing notes (86% coverage)
- **GLM-4 (Zhipu) third-level review** — integrated as fallback classifier and final auditor
- **Market validation + risk matrix report** (`docs/reports/market-validation-risk-matrix.html`) — TAM/SAM/SOM sizing, competitor user review analysis, 3×5 risk matrix

### Standards · 标准
- **L0-005 主题分类** — 15 categories: AI Agent & Architecture, LLM & Prompt Engineering, RAG & Retrieval, AI Product Design, AI Evaluation & Quality, Data-Driven Decisions, Monetization & Pricing, Growth & Launch, User Research & ICP, Product Strategy & Roadmap, Engineering Collaboration, Content & SEO/GEO, Org & Communication, Competition & Positioning, AI Dev Tools

### Tests · 测试
- 32/32 pytest passed (local + CI)
- test_schemas.py: `test_topic_optional` replaces `test_topic_required`
- test_api.py: `test_generate_missing_topic` updated for optional topic

### Demo · 演示视频
- YouTube: https://youtu.be/55a1-DYoH3E
- Bilibili: https://www.bilibili.com/video/BV1Gj3n6VEvQ/

---

## v0.1.0 (2026-07-28)

### Core Features · 核心功能
- RAG-powered quiz generation from Obsidian notes (5 QA Gate checks)
- LLM-based answer grading with L0-001 scoring rubric
- SM-2 spaced repetition algorithm for wrong answer review
- 6-dimension competency radar chart with learning recommendations
- Content import: URL / YouTube / Paste text / PDF / Screenshot OCR
- Batch screenshot OCR → single note (MiniMax M3 multimodal)

### Architecture · 架构
- Flask 3.0+ REST API with Blueprint modularization
- Pure HTML/CSS/JS SPA frontend (zero framework, zero build)
- Inter font + Indigo color scheme + SVG icon navigation
- 22 API endpoints under /v1 prefix with Swagger documentation
- SQLite response cache (SHA-1 key, 30-day TTL, 3-tier invalidation)
- SQLite LLM call statistics with cache hit rate monitoring
- Vault anti-loss engine: atomic writes + WAL + integrity snapshots
- Optional API Key authentication middleware
- DeepSeek V4 Pro as default LLM (switchable: GLM-4 / GPT-4.1 / MiniMax M3 / Ollama)

### Quality Assurance · 质量保障
- 32 automated tests (21 API + 11 Schema) with pytest
- GitHub Actions CI pipeline (Python 3.10/3.12)
- Unified frontend error handling with 30s request timeout
- Pydantic request validation (9 schemas, types array/string compatibility)
- 13 unified error codes

### Documentation · 文档
- README with 13 screenshots across 6 functional areas
- New user setup guide (docs/SETUP.md)
- API reference (docs/api.md) + System architecture (docs/architecture.md)
- Product requirements doc (spec/PRD.md) + Roadmap (spec/ROADMAP.md)
- User research + User journey maps (spec/)
- 7 AI skills documentation (skills/) — prompt templates + workflows
- Mobile responsive plan (spec/MOBILE_RESPONSIVE.md)
- Multi-user isolation plan (spec/MULTI_USER_ISOLATION.md)
- Directory migration record (spec/STRUCTURE_MIGRATION.md)

### UX Improvements · 体验优化
- Toast notifications (fixed positioning, no layout shift)
- Exit quiz button + Retry with nocache option
- One-click start script (auto-detect Python, install deps, open browser)
- File upload with progress feedback
- Delete note with instant DOM removal (no page rebuild)
- PDF import with AI structuring (PyPDF2 + DeepSeek, long doc chunking)

### Known Limitations · 已知限制
- Long PDF auto-split not yet working (spec/PDF_LONG_SPLIT.md)
- Mobile responsive adaptation pending (spec/MOBILE_RESPONSIVE.md)
- Multi-user isolation pending (spec/MULTI_USER_ISOLATION.md)
