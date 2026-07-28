"""Blueprint registry."""
from .quiz import quiz_bp
from .notes import notes_bp
from .web import web_bp

BLUEPRINTS = [quiz_bp, notes_bp, web_bp]
