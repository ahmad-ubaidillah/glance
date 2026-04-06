"""Tests for GR-Review agents."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(
        self, response_content: str = '{"findings": [], "summary": "OK", "verdict": "pass"}'
    ):
        self.response_content = response_content

    async def chat(self, model: str, messages: list, temperature: float, max_tokens: int, **kwargs):
        """Mock chat method."""

        class MockResponse:
            content = self.response_content

        return MockResponse()


class TestArchitectAgent:
    """Test Architect agent."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        from glance.agents.base import GlanceConfig

        return GlanceConfig(
            llm_model="test-model",
            temperature=0.3,
            max_tokens=1000,
            enable_caching=False,
        )

    @pytest.mark.asyncio
    async def test_architect_review_basic(self, mock_config):
        """Test basic architect review."""
        from glance.agents.architect import Architect

        mock_client = MockLLMClient()
        agent = Architect(config=mock_config, client=mock_client)

        diff = """--- a/test.py
+++ b/test.py
@@ -1,3 +1,3 @@
-def add(a, b):
-    return a + b
+def multiply(a, b):
+    return a * b
"""
        result = await agent.review(diff_content=diff, file_path="test.py", ci_context="")

        assert result is not None
        assert result.verdict in ["pass", "concerns", "critical"]

    @pytest.mark.asyncio
    async def test_architect_with_ci_context(self, mock_config):
        """Test architect with CI context."""
        from glance.agents.architect import Architect

        mock_client = MockLLMClient()
        agent = Architect(config=mock_config, client=mock_client)

        diff = "def test(): pass"
        ci_context = '{"ci_status": {"status": "success"}}'

        result = await agent.review(diff_content=diff, ci_context=ci_context)

        assert result is not None


class TestBugHunterAgent:
    """Test BugHunter agent."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        from glance.agents.base import GlanceConfig

        return GlanceConfig(
            llm_model="test-model",
            temperature=0.3,
            max_tokens=1000,
            enable_caching=False,
        )

    @pytest.mark.asyncio
    async def test_bug_hunter_review(self, mock_config):
        """Test bug hunter review."""
        from glance.agents.bug_hunter import BugHunterAgent

        mock_client = MockLLMClient()
        agent = BugHunterAgent(config=mock_config, client=mock_client)

        diff = "if x = 1: pass"  # Syntax-like error
        result = await agent.review(diff_content=diff, file_path="test.py")

        assert result is not None


class TestWhiteHatAgent:
    """Test WhiteHat agent."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        from glance.agents.base import GlanceConfig

        return GlanceConfig(
            llm_model="test-model",
            temperature=0.3,
            max_tokens=1000,
            enable_caching=False,
        )

    @pytest.mark.asyncio
    async def test_white_hat_review(self, mock_config):
        """Test white hat security review."""
        from glance.agents.white_hat import WhiteHatAgent

        mock_client = MockLLMClient()
        agent = WhiteHatAgent(config=mock_config, client=mock_client)

        diff = 'password = "hardcoded"'
        result = await agent.review(diff_content=diff, file_path="test.py")

        assert result is not None


class TestArbitratorAgent:
    """Test Arbitrator agent."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        from glance.agents.base import GlanceConfig

        return GlanceConfig(
            llm_model="test-model",
            temperature=0.3,
            max_tokens=1000,
            enable_caching=False,
        )

    @pytest.fixture
    def mock_findings(self):
        """Create mock agent reviews."""
        from glance.agents.base import AgentReview, Finding

        architect_review = AgentReview(
            findings=[
                Finding(
                    file_path="test.py",
                    line_number=10,
                    severity="warning",
                    category="complexity",
                    message="Function too long",
                    suggestion="Split into smaller functions",
                )
            ],
            summary="Some complexity issues",
            verdict="concerns",
        )

        bug_hunter_review = AgentReview(
            findings=[],
            summary="No bugs found",
            verdict="pass",
        )

        white_hat_review = AgentReview(
            findings=[],
            summary="No security issues",
            verdict="pass",
        )

        return architect_review, bug_hunter_review, white_hat_review

    @pytest.mark.asyncio
    async def test_arbitrator_consolidate(self, mock_config, mock_findings):
        """Test arbitrator consolidation."""
        from glance.agents.arbitrator import ArbitratorAgent

        mock_client = MockLLMClient()
        agent = ArbitratorAgent(config=mock_config, client=mock_client)

        architect_review, bug_hunter_review, white_hat_review = mock_findings

        result = await agent.arbitrate(architect_review, bug_hunter_review, white_hat_review)

        assert result is not None
        assert result.verdict in ["pass", "concerns", "critical"]

    @pytest.mark.asyncio
    async def test_arbitrator_security_block(self, mock_config):
        """Test arbitrator blocks on critical security."""
        from glance.agents.arbitrator import ArbitratorAgent
        from glance.agents.base import AgentReview, Finding

        mock_client = MockLLMClient()
        agent = ArbitratorAgent(config=mock_config, client=mock_client)

        architect_review = AgentReview(findings=[], summary="OK", verdict="pass")
        bug_hunter_review = AgentReview(findings=[], summary="OK", verdict="pass")
        white_hat_review = AgentReview(
            findings=[
                Finding(
                    file_path="auth.py",
                    severity="critical",
                    category="security",
                    message="SQL Injection vulnerability",
                )
            ],
            summary="Critical security issue",
            verdict="critical",
        )

        result = await agent.arbitrate(architect_review, bug_hunter_review, white_hat_review)

        assert result.verdict == "critical"


class TestTokenTracker:
    """Test token tracking functionality."""

    def test_estimate_tokens_english(self):
        """Test token estimation for English text."""
        from glance.agents.base import TokenTracker

        text = "This is a test sentence."
        tokens = TokenTracker.estimate_tokens(text)

        assert tokens > 0

    def test_estimate_tokens_code(self):
        """Test token estimation for code."""
        from glance.agents.base import TokenTracker

        code = "def add(a, b): return a + b"
        tokens = TokenTracker.estimate_tokens(code, is_code=True)

        assert tokens > 0
        # Code uses CODE_TOKEN_RATIO (3), so should be len/3 or similar

    def test_truncate_for_context(self):
        """Test truncation."""
        from glance.agents.base import TokenTracker

        long_text = "line1\n" * 1000
        truncated = TokenTracker.truncate_for_context(long_text, max_tokens=100, is_code=True)

        assert "truncated" in truncated.lower() or len(truncated) < len(long_text)


class TestPromptCache:
    """Test prompt caching."""

    def test_cache_set_get(self):
        """Test cache basic operations."""
        from glance.agents.base import PromptCache

        cache = PromptCache(max_size=3)
        prompt_hash = "test123"
        response = "Test response"

        cache.set(prompt_hash, response)
        assert cache.get(prompt_hash) == response

    def test_cache_miss(self):
        """Test cache miss."""
        from glance.agents.base import PromptCache

        cache = PromptCache()
        assert cache.get("nonexistent") is None

    def test_cache_eviction(self):
        """Test cache eviction (FIFO)."""
        from glance.agents.base import PromptCache

        cache = PromptCache(max_size=2)
        cache.set("hash1", "response1")
        cache.set("hash2", "response2")
        cache.set("hash3", "response3")  # Should evict hash1

        assert cache.get("hash1") is None
        assert cache.get("hash2") == "response2"
        assert cache.get("hash3") == "response3"
