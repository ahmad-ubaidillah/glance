"""Tests for auto-fix functionality."""

from __future__ import annotations

import pytest


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self, response_content: str = '{"fixes": []}'):
        self.response_content = response_content

    async def chat(self, messages: list, **kwargs):
        class MockResponse:
            content = self.response_content

        return MockResponse()


class TestAutoFixGenerator:
    """Test AutoFixGenerator."""

    @pytest.fixture
    def mock_client(self):
        return MockLLMClient()

    def test_suggested_change_dataclass(self):
        """Test SuggestedChange dataclass."""
        from glance.auto_fix import SuggestedChange

        fix = SuggestedChange(
            file_path="test.py",
            line_number=10,
            original_code="x = 1",
            fixed_code="x = 2",
            description="Fix logic",
            category="logic",
        )

        assert fix.file_path == "test.py"
        assert fix.line_number == 10
        assert fix.category == "logic"

    @pytest.mark.asyncio
    async def test_generate_fixes_empty(self, mock_client):
        """Test generate_fixes with no findings."""
        from glance.auto_fix import AutoFixGenerator

        generator = AutoFixGenerator(mock_client)
        fixes = await generator.generate_fixes([], "diff content")

        assert fixes == []

    @pytest.mark.asyncio
    async def test_generate_fixes_with_findings(self, mock_client):
        """Test generate_fixes with findings."""
        from glance.auto_fix import AutoFixGenerator, SuggestedChange
        from glance.agents.base import Finding

        # Mock LLM response
        mock_client.response_content = """{"fixes": [
            {"file_path": "test.py", "line_number": 10, "original_code": "x=1", "fixed_code": "x = 1", "description": "Add spacing", "category": "style"}
        ]}"""

        generator = AutoFixGenerator(mock_client)
        findings = [
            Finding(
                file_path="test.py",
                line_number=10,
                severity="warning",
                category="style",
                message="Missing spaces around equals",
                suggestion="Add spaces around =",
            )
        ]

        fixes = await generator.generate_fixes(findings, "x=1")

        assert len(fixes) == 1
        assert fixes[0].file_path == "test.py"
        assert fixes[0].category == "style"

    def test_format_github_suggestion(self, mock_client):
        """Test GitHub suggestion formatting."""
        from glance.auto_fix import AutoFixGenerator, SuggestedChange

        generator = AutoFixGenerator(mock_client)
        fix = SuggestedChange(
            file_path="test.py",
            line_number=10,
            original_code="x=1",
            fixed_code="x = 1",
            description="Add spacing",
            category="style",
        )

        suggestion = generator.format_github_suggestion(fix)

        assert "suggested" in suggestion.lower()
        assert "test.py" in suggestion

    def test_format_review_comment(self, mock_client):
        """Test review comment formatting."""
        from glance.auto_fix import AutoFixGenerator, SuggestedChange

        generator = AutoFixGenerator(mock_client)
        fix = SuggestedChange(
            file_path="test.py",
            line_number=10,
            original_code="x=1",
            fixed_code="x = 1",
            description="Add spacing",
            category="style",
        )

        comment = generator._format_review_comment(fix)

        assert "Suggested Fix" in comment
        assert "style" in comment
        assert "Before" in comment
        assert "After" in comment
