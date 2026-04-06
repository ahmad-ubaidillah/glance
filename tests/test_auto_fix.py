"""Tests for auto-fix functionality."""

from __future__ import annotations

import pytest


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self, response_content: str = '{"fixes": []}'):
        self.response_content = response_content

    async def chat(self, model: str, messages: list, temperature: float, max_tokens: int, **kwargs):
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

        assert "suggestion" in suggestion.lower()
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


class TestLocalKnowledgeBase:
    """Test LocalKnowledgeBase."""

    @pytest.fixture
    def temp_kb(self, tmp_path):
        """Create temporary knowledge base."""
        from glance.knowledge.base import LocalKnowledgeBase

        kb = LocalKnowledgeBase(storage_path=tmp_path / "kb")
        return kb

    def test_add_pattern(self, temp_kb):
        """Test adding a pattern."""
        pattern_id = temp_kb.add_pattern(
            pattern_type="bad",
            description="Missing null check",
            code_snippet="def foo(x): return x.value",
            language="python",
        )

        assert pattern_id is not None
        # Verify pattern was added by searching
        similar = temp_kb.find_similar_patterns("null check")
        assert len(similar) >= 1

    def test_find_similar_patterns(self, temp_kb):
        """Test finding similar patterns."""
        temp_kb.add_pattern(
            pattern_type="bad",
            description="SQL injection risk",
            code_snippet="query.execute(user_input)",
            language="python",
        )

        similar = temp_kb.find_similar_patterns(
            "SQL injection in query",
            pattern_type="bad",
        )

        assert len(similar) >= 1

    def test_add_review_history(self, temp_kb):
        """Test adding review history."""
        temp_kb.add_review_history(
            pr_number=123,
            pr_title="Fix bug",
            repository="owner/repo",
            files_changed=["src/main.py"],
            findings_count=5,
            verdict="concerns",
            key_patterns=["null_check"],
        )

        similar = temp_kb.get_similar_reviews(["src/main.py"], limit=1)
        assert len(similar) >= 1

    def test_get_similar_reviews(self, temp_kb):
        """Test getting similar reviews."""
        for i in range(3):
            temp_kb.add_review_history(
                pr_number=i,
                pr_title=f"PR {i}",
                repository="owner/repo",
                files_changed=["file.py"],
                findings_count=1,
                verdict="pass",
                key_patterns=[],
            )

        similar = temp_kb.get_similar_reviews(["file.py"], limit=2)
        assert len(similar) >= 1
