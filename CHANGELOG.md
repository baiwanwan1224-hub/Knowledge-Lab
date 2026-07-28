# Changelog

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
- GitHub CI push + LLM_API_KEY secret pending
