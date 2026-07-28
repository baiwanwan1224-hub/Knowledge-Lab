"""Unified error codes and response builder."""
from enum import Enum
from flask import jsonify

class ErrorCode(str, Enum):
    OK = "OK"
    INVALID_JSON = "INVALID_JSON"
    MISSING_FIELD = "MISSING_FIELD"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOTE_NOT_FOUND = "NOTE_NOT_FOUND"
    FILE_MISSING = "FILE_MISSING"
    FILE_TYPE_UNSUPPORTED = "FILE_TYPE_UNSUPPORTED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    TRANSCRIBE_FAILED = "TRANSCRIBE_FAILED"
    LLM_API_ERROR = "LLM_API_ERROR"
    NO_CONTENT = "NO_CONTENT"
    VAULT_INTEGRITY_FAIL = "VAULT_INTEGRITY_FAIL"

def error_response(code: ErrorCode, detail: str = "", status: int = 400):
    return jsonify({"error": code.value, "detail": detail}), status
