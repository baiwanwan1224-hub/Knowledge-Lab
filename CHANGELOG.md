# Changelog

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
- Demo video pending
