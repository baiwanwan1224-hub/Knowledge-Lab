"""Test Pydantic schemas — regression tests for type validation bugs."""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server.schemas import GenerateRequest, GradeRequest, DeleteRequest, PasteRequest


class TestGenerateRequest:
    """Core: quiz generation schema — the 'types' array/string bug fix."""

    def test_types_string(self):
        """types as comma-separated string (original format)."""
        body = GenerateRequest.model_validate({
            'topic': '测试', 'count': 5,
            'types': 'single_choice,short_answer',
            'difficulty': 'medium'
        })
        assert body.types == 'single_choice,short_answer'

    def test_types_list(self):
        """types as list — the browser sends this, was the INVALID_JSON bug."""
        body = GenerateRequest.model_validate({
            'topic': '测试', 'count': 5,
            'types': ['single_choice', 'short_answer'],
            'difficulty': 'medium'
        })
        assert body.types == 'single_choice,short_answer'

    def test_types_default(self):
        """types not provided — should use default."""
        body = GenerateRequest.model_validate({
            'topic': '测试', 'count': 5, 'difficulty': 'medium'
        })
        assert body.types == 'single_choice,short_answer'

    def test_minimal(self):
        """Only required field (topic)."""
        body = GenerateRequest.model_validate({
            'topic': 'AI产品经理'
        })
        assert body.topic == 'AI产品经理'
        assert body.count == 5
        assert body.difficulty == 'medium'

    def test_count_bounds(self):
        """Count must be between 1 and 20."""
        GenerateRequest.model_validate({'topic': '测试', 'count': 1})
        GenerateRequest.model_validate({'topic': '测试', 'count': 20})
        with pytest.raises(Exception):
            GenerateRequest.model_validate({'topic': '测试', 'count': 0})
        with pytest.raises(Exception):
            GenerateRequest.model_validate({'topic': '测试', 'count': 21})

    def test_topic_required(self):
        """Topic is required."""
        with pytest.raises(Exception):
            GenerateRequest.model_validate({})
        with pytest.raises(Exception):
            GenerateRequest.model_validate({'count': 5})

    def test_nocache_ignored(self):
        """nocache field should be silently ignored (not in schema)."""
        body = GenerateRequest.model_validate({
            'topic': '测试', 'nocache': True
        })
        assert body.topic == '测试'


class TestDeleteRequest:
    """Delete schema — file field must be non-empty."""

    def test_valid(self):
        body = DeleteRequest.model_validate({'file': 'test-note.md'})
        assert body.file == 'test-note.md'

    def test_empty_file(self):
        with pytest.raises(Exception):
            DeleteRequest.model_validate({'file': ''})

    def test_missing_file(self):
        with pytest.raises(Exception):
            DeleteRequest.model_validate({})


class TestPasteRequest:
    """Paste schema — content field."""

    def test_valid(self):
        body = PasteRequest.model_validate({'content': 'some text'})
        assert body.content == 'some text'

    def test_empty_content(self):
        with pytest.raises(Exception):
            PasteRequest.model_validate({'content': ''})
