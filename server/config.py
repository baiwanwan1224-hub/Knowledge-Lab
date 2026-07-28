"""Knowledge Lab · Centralized Config"""
import os
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SERVER_ROOT.parent
DASHBOARD_HTML = PROJECT_ROOT / "apps" / "web" / "dashboard_v2.html"

ALLOWED_FILE_EXTENSIONS = frozenset({".pdf", ".wav", ".mp3", ".m4a", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".md"})
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
DEFAULT_PORT = 5050
DEFAULT_HOST = "127.0.0.1"

def is_allowed_extension(filename: str) -> bool:
    if not filename: return False
    return Path(filename).suffix.lower() in ALLOWED_FILE_EXTENSIONS
