# Knowledge Lab · API Reference

> Target audience: Frontend developers & AI Agents (Claude Code) · ~1.5 pages

---

## 1. API Overview

| Setting | Value |
|---------|-------|
| **Base URL** | `http://localhost:5050` |
| **Content-Type** | `application/json; charset=utf-8` |
| **Authentication** | None (single-user local tool) |
| **CORS** | All origins allowed (`Access-Control-Allow-Origin: *`) |
| **Streaming** | Not currently used (all responses are complete JSON) |
| **Version** | Unversioned (single local deployment, no backward compat concerns) |

### Response Envelope

**Success:**
```json
{"status": "success", "...data fields..."}
```

**Error:**
```json
{"error": "ERROR_CODE", "detail": "Human-readable description"}
```

### Standard Error Codes

| Code | HTTP Status | Meaning |
|------|------------|---------|
| `LLM_API_ERROR` | 502 | LLM provider returned error or timed out |
| `NO_CONTENT` | 200 | No notes matched the query (not an error, but no results) |
| `VAULT_INTEGRITY_FAIL` | 500 | Vault file integrity check failed |
| `TRANSCRIBE_FAILED` | 422 | Audio transcription failed (no captions + whisper failed) |
| `INVALID_JSON` | 400 | Request body is not valid JSON |
| `NOT_FOUND` | 404 | Endpoint or resource not found |

Error codes are 1:1 aligned with `docs/architecture.md` §7 Failure Modes.

---

## 2. Common Schema

### Note Object
```json
{
  "title": "AI Product Strategy",
  "path": "2026-07-26_AI_Product_Strategy_LENNY.md",
  "topics": ["ai", "product-strategy"],
  "status": "ready",
  "source": "Lenny's Podcast",
  "difficulty": "medium",
  "file_hash": "sha256..."
}
```

### Quiz Question Object
```json
{
  "type": "single_choice | short_answer | scenario",
  "question": "Question text",
  "options": [{"label": "A", "text": "..."}],
  "correct_answer": "B",
  "explanation": "Why correct, why wrong",
  "difficulty": "medium",
  "knowledge_point": "RAG architecture",
  "competency_dimension": "AI技术理解",
  "quality_score": 0.8,
  "quality_passed": true
}
```

---

## 3. Endpoint Reference

### Quiz

| # | Method | Path | Description |
|---|--------|------|-------------|
| 1 | `POST` | `/quiz/generate` | Generate quiz questions from vault notes |
| 2 | `POST` | `/quiz/grade` | Grade user answers, generate wrong-answer cards |

#### `POST /quiz/generate`
Generate quiz questions by scanning vault for matching notes and calling LLM.

**Request:**
```json
{"topic": "AI产品策略", "count": 5, "types": "single_choice,short_answer", "difficulty": "medium"}
```

**Response:**
```json
{
  "status": "success",
  "session_name": "AI产品策略测验 2026-07-27 15:30",
  "questions": [{...quiz question objects...}],
  "total": 5,
  "passed_qa": 4,
  "source_notes": [{"title": "...", "path": "..."}]
}
```

#### `POST /quiz/grade`
Grade user answers via LLM. Answers scoring < 60% trigger wrong-answer card generation with SM-2 scheduling.

**Request:**
```json
{
  "session_uuid": "uuid",
  "questions": [{...question objects...}],
  "answers": ["user answer 1", "user answer 2"],
  "source_notes": [{"title": "..."}]
}
```

**Response:**
```json
{
  "status": "success",
  "total_score": 12.5,
  "total_max": 15,
  "score_pct": 83.3,
  "wrong_count": 1,
  "results": [{
    "score": 2.5, "max_score": 5, "is_correct": false,
    "feedback": "...", "weakness_tags": ["概念理解不清"],
    "sm2": {"next_review_at": "2026-07-28", "review_interval_days": 1}
  }]
}
```

### Notes

| # | Method | Path | Description |
|---|--------|------|-------------|
| 3 | `POST` | `/notes/import` | Import from URL (web page or YouTube) |
| 4 | `POST` | `/notes/upload` | Upload local file (PDF/MD/TXT) |
| 5 | `POST` | `/notes/transcribe` | Transcribe YouTube video via yt-dlp + Whisper |
| 6 | `POST` | `/notes/paste` | Paste raw text for LLM structuring |
| 7 | `POST` | `/notes/verify` | Verify note: draft → ready or needs_revision |
| 8 | `POST` | `/notes/delete` | Delete a note from vault |
| 9 | `POST` | `/notes/screenshot_ocr` | OCR screenshot via MiniMax M3 |

#### `POST /notes/import`
Import content from URL. YouTube URLs auto-detect captions or fall back to transcription.

**Request:**
```json
{"url": "https://www.youtube.com/watch?v=...", "topic": "growth"}
```

#### `POST /notes/verify`
Change note status.

**Request:**
```json
{"file": "20260726_xxx_URL.md", "action": "approve"}
```
Actions: `approve` → draft→ready · `reject` → draft→needs_revision

### Read Endpoints

| # | Method | Path | Description |
|---|--------|------|-------------|
| 10 | `GET` | `/` | Serve dashboard SPA |
| 11 | `GET` | `/health` | Health check (`{"status":"ok","time":"...","pg":false}`) |
| 12 | `GET` | `/topics` | List all unique topics with note counts |
| 13 | `GET` | `/notes` | List all notes with metadata |
| 14 | `GET` | `/notes/drafts` | List draft/revision notes (review queue) |
| 15 | `GET` | `/note?path=...` | Get single note content by path |
| 16 | `GET` | `/competency` | 6-dimension radar chart data with LLM recommendations |
| 17 | `GET` | `/history` | Quiz history (PostgreSQL or file-based fallback) |
| 18 | `GET` | `/wrong-answers` | List wrong-answer cards with due dates |
| 19 | `GET` | `/dashboard` | Aggregated stats (quiz count, avg score, notes, wrong answers) |

---

## 4. Error Code ↔ Architecture Alignment

Per cross-document consistency rule: every non-500 error code in this document must have a corresponding entry in `docs/architecture.md` §7 Failure Modes.

| API Error Code | Architecture § | Detection Point |
|----------------|---------------|-----------------|
| `LLM_API_ERROR` | §7.1 | `quiz_generator.py → call_llm()` |
| `NO_CONTENT` | §7.2 | `quiz_generator.py → find_notes()` |
| `VAULT_INTEGRITY_FAIL` | §7.3 | `vault_core.py → verify_integrity()` |
| `TRANSCRIBE_FAILED` | §7.4 | `quiz_server.py → _handle_transcribe()` |

**Sync rule**: When adding a new error code, update both `api.md` §1 and `architecture.md` §7 simultaneously. PR review checklist includes verifying this alignment.
