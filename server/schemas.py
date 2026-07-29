"""Pydantic request validation schemas."""
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional, Union

class GenerateRequest(BaseModel):
    topic: str = Field(default="", min_length=0, max_length=200)
    count: int = Field(default=5, ge=1, le=20)
    types: Union[str, list[str]] = "single_choice,short_answer"
    difficulty: Literal["easy", "medium", "hard"] = "medium"

    @field_validator('types', mode='before')
    @classmethod
    def normalize_types(cls, v):
        """Accept both comma-separated string and list[str], normalize to string."""
        if isinstance(v, list):
            return ','.join(v)
        return v

class GradeRequest(BaseModel):
    session_uuid: str = ""
    questions: list[dict] = Field(default_factory=list)
    answers: list[str] = Field(default_factory=list)
    source_notes: list[dict] = Field(default_factory=list)

class ImportRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    topic: str = ""

class VerifyRequest(BaseModel):
    file: str = Field(min_length=1)
    action: Literal["approve", "reject"] = "approve"

class DeleteRequest(BaseModel):
    file: str = Field(min_length=1)

class PasteRequest(BaseModel):
    content: str = Field(min_length=1, max_length=500_000)
    topic: str = ""

class TranscribeRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    topic: str = ""

class ScreenshotOcrRequest(BaseModel):
    image_b64: str = Field(min_length=8)
    lang: str = "zh+en"

class IngestRequest(BaseModel):
    content: str = Field(min_length=1)
    source: str = "webhook"
