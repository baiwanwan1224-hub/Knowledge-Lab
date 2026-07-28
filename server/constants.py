"""Global constants & endpoint registry. Register new LLM endpoints here."""
ENDPOINT_NOTES_IMPORT = "notes.import"
ENDPOINT_NOTES_PASTE = "notes.paste"
ENDPOINT_NOTES_TRANSCRIBE = "notes.transcribe"
ENDPOINT_NOTES_OCR = "notes.screenshot_ocr"
ENDPOINT_QUIZ_GENERATE = "quiz.generate"
ENDPOINT_QUIZ_GRADE = "quiz.grade"

REGISTERED_ENDPOINTS = frozenset({
    ENDPOINT_NOTES_IMPORT, ENDPOINT_NOTES_PASTE, ENDPOINT_NOTES_TRANSCRIBE,
    ENDPOINT_NOTES_OCR, ENDPOINT_QUIZ_GENERATE, ENDPOINT_QUIZ_GRADE,
})

MODEL_VERSION = "1.0"

CACHE_DB = "data/cache.db"
STATS_DB = "data/stats.db"
