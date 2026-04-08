"""Base agent class for GR-Review's multi-agent system.

Provides the abstract BaseAgent class that all review agents inherit from,
including async LLM call support via OpenAI-compatible APIs.
Includes token optimization, smart context, and caching.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("glance.agents")

# Try to import openai, but make it optional for flexibility
try:
    from openai import APIError, APITimeoutError, RateLimitError

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    APIError = Exception
    RateLimitError = Exception
    APITimeoutError = Exception


class TokenTracker:
    """Tracks and estimates token usage for LLM calls."""

    # Rough token estimation: 1 token ≈ 4 characters for English
    # Different languages have different ratios
    CHARS_PER_TOKEN = 4

    # Common programming tokens (keywords, symbols)
    CODE_TOKEN_RATIO = 3  # More tokens per char for code

    @staticmethod
    def estimate_tokens(text: str, is_code: bool = False) -> int:
        """Estimate token count for text.

        Args:
            text: Text to estimate.
            is_code: Whether text is code (uses different ratio).

        Returns:
            Estimated token count.
        """
        ratio = TokenTracker.CODE_TOKEN_RATIO if is_code else TokenTracker.CHARS_PER_TOKEN
        return len(text) // ratio

    @staticmethod
    def truncate_for_context(text: str, max_tokens: int, is_code: bool = False) -> str:
        """Truncate text to fit within token limit.

        Args:
            text: Text to truncate.
            max_tokens: Maximum tokens allowed.
            is_code: Whether text is code.

        Returns:
            Truncated text with indicator.
        """
        estimated = TokenTracker.estimate_tokens(text, is_code)
        if estimated <= max_tokens:
            return text

        # Calculate safe character limit
        ratio = TokenTracker.CODE_TOKEN_RATIO if is_code else TokenTracker.CHARS_PER_TOKEN
        safe_chars = (max_tokens * ratio) // 2  # Leave room for context

        # Try to truncate at line boundary
        lines = text.split("\n")
        result = []
        current_length = 0

        for line in lines:
            line_length = len(line) + 1  # +1 for newline
            if current_length + line_length > safe_chars:
                break
            result.append(line)
            current_length += line_length

        if not result and text:
            # If no lines fit, truncate raw
            result = [text[:safe_chars]]

        result.append(f"\n... [truncated {estimated - max_tokens} tokens]")

        return "\n".join(result)


class PromptCache:
    """Simple in-memory cache for LLM responses based on prompt hash."""

    def __init__(self, max_size: int = 100):
        """Initialize cache.

        Args:
            max_size: Maximum number of cached entries.
        """
        self._cache: dict[str, str] = {}
        self._max_size = max_size

    def get(self, prompt_hash: str) -> str | None:
        """Get cached response.

        Args:
            prompt_hash: Hash of the prompt.

        Returns:
            Cached response or None.
        """
        return self._cache.get(prompt_hash)

    def set(self, prompt_hash: str, response: str) -> None:
        """Cache a response.

        Args:
            prompt_hash: Hash of the prompt.
            response: LLM response to cache.
        """
        if len(self._cache) >= self._max_size:
            # Remove oldest entry (simple FIFO)
            oldest = next(iter(self._cache))
            del self._cache[oldest]

        self._cache[prompt_hash] = response

    @staticmethod
    def hash_prompt(prompt: str) -> str:
        """Create hash of prompt for cache key.

        Args:
            prompt: Prompt to hash.

        Returns:
            SHA256 hash of prompt.
        """
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()


class Finding(BaseModel):
    """Represents a single code review finding."""

    file_path: str | None = Field(default=None, description="Path to the file containing the issue")
    line_number: int | None = Field(default=None, description="Line number where the issue occurs")
    severity: str = Field(
        default="warning", description="Severity level: 'info', 'warning', or 'critical'"
    )
    category: str | None = Field(
        default=None, description="Category of the finding, e.g. 'solid', 'security', 'bug'"
    )
    message: str | None = Field(default=None, description="Description of the issue found")
    suggestion: str | None = Field(default=None, description="Suggested fix or improvement")
    code_snippet: str | None = Field(
        default=None, description="Relevant code snippet showing the issue"
    )
    auto_fix: str | None = Field(
        default=None, description="Suggested code change for auto-fix feature"
    )
    # Accept alternate field names
    type: str | None = Field(default=None, alias="type")
    description: str | None = Field(default=None, alias="description")
    path: str | None = Field(default=None, alias="path")
    line: int | None = Field(default=None, alias="line")
    lines: list[int] | None = Field(default=None, alias="lines")

    model_config = {"populate_by_name": True}

    def __init__(self, **data):
        # Handle alternate field mappings
        if "path" in data and "file_path" not in data:
            data["file_path"] = data.pop("path")
        if "line" in data and "line_number" not in data:
            data["line_number"] = data.pop("line")
        if "lines" in data and "line_number" not in data:
            lines = data.pop("lines")
            data["line_number"] = lines[0] if lines else None
        if "type" in data and "category" not in data:
            data["category"] = data.pop("type")
        if "description" in data and "message" not in data:
            data["message"] = data.pop("description")
        super().__init__(**data)


class AgentReview(BaseModel):
    """Complete review result from a single agent."""

    findings: list[Finding] = Field(
        default_factory=list, description="List of findings from the review"
    )
    summary: str = Field(description="Summary of the review results")
    verdict: str = Field(description="Review verdict: 'pass', 'concerns', or 'critical'")
    tokens_used: int | None = Field(default=None, description="Tokens consumed in this review")
    cached: bool = Field(default=False, description="Whether response was from cache")


class GlanceConfig(BaseModel):
    """Configuration for the GR-Review system - shared with config.py.

    This mirrors the main config but adds agent-specific settings.
    """

    # LLM settings (mirrored from config.py for agent use)
    llm_model: str = Field(
        default="glm-4-flash",
        alias="LLM_MODEL",
        description="LLM model to use for LLM calls",
    )
    temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="LLM temperature for response generation",
    )
    max_tokens: int = Field(
        default=4096,
        gt=0,
        description="Maximum tokens for LLM response",
    )

    # Token optimization settings
    enable_caching: bool = Field(
        default=True,
        description="Enable prompt caching for repeated patterns",
    )
    max_context_tokens: int = Field(
        default=8000,
        description="Max tokens to send in context (input)",
    )
    smart_truncation: bool = Field(
        default=True,
        description="Enable smart truncation for large diffs",
    )

    # Alias for backward compatibility
    @property
    def zhipuai_model(self) -> str:
        """Backward compatible alias for llm_model."""
        return self.llm_model


# Global cache instance
_global_cache: PromptCache | None = None


def get_cache() -> PromptCache:
    """Get global prompt cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = PromptCache()
    return _global_cache


class BaseAgent(ABC):
    """Abstract base class for all GR-Review agents.

    Subclasses must implement agent_name and system_prompt properties,
    and inherit the async review() method for LLM-based code analysis.
    Includes token optimization, smart context, and caching.
    """

    def __init__(
        self,
        config: GlanceConfig,
        client: Any,  # Flexible client type
        enable_cache: bool = True,
    ) -> None:
        """Initialize the base agent.

        Args:
            config: GR-Review configuration containing model and generation settings.
            client: Async LLM client for API calls.
            enable_cache: Whether to enable response caching.
        """
        self.config = config
        self.client = client
        self._cache = get_cache() if enable_cache and config.enable_caching else None

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Return the name of this agent."""

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt for this agent."""

    async def _call_llm(
        self,
        user_prompt: str,
        use_cache: bool = True,
    ) -> tuple[str, bool, int]:
        """Make an async call to the LLM with token optimization.

        Args:
            user_prompt: The user prompt to send to the LLM.
            use_cache: Whether to use cached response if available.

        Returns:
            Tuple of (response_content, was_cached, tokens_used).
        """
        # Check cache first
        if use_cache and self._cache:
            prompt_hash = PromptCache.hash_prompt(user_prompt)
            cached_response = self._cache.get(prompt_hash)
            if cached_response:
                logger.info(f"{self.agent_name}: Using cached response")
                return cached_response, True, 0  # Cached, tokens not counted

        # Estimate input tokens
        input_tokens = TokenTracker.estimate_tokens(self.system_prompt + user_prompt, is_code=True)

        # Truncate if needed (smart truncation)
        if self.config.smart_truncation:
            max_input = self.config.max_context_tokens - self.config.max_tokens
            user_prompt = TokenTracker.truncate_for_context(user_prompt, max_input, is_code=True)

        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.config.llm_model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                break
            except Exception as e:
                error_str = str(e)
                if "429" in error_str and attempt < max_retries - 1:
                    import asyncio
                    logger.warning(f"{self.agent_name}: Rate limited, retrying in {retry_delay * (attempt + 1)}s...")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                raise

        # Handle both dict response (from adapter) and object response
            if isinstance(response, dict):
                content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                content = response.choices[0].message.content

            if content is None:
                logger.warning("%s: Received empty response from LLM", self.agent_name)
                return (
                    '{"findings": [], "summary": "Empty response from LLM", "verdict": "concerns"}',
                    False,
                    input_tokens,
                )

            # Cache the response
            if use_cache and self._cache:
                prompt_hash = PromptCache.hash_prompt(user_prompt)
                self._cache.set(prompt_hash, content)

            # Estimate output tokens
            output_tokens = TokenTracker.estimate_tokens(content, is_code=False)
            total_tokens = input_tokens + output_tokens

            return content, False, total_tokens

        except RateLimitError as e:
            logger.error("%s: Rate limit exceeded: %s", self.agent_name, str(e))
            return (
                json.dumps(
                    {
                        "findings": [],
                        "summary": f"Rate limit exceeded: {e}",
                        "verdict": "concerns",
                    }
                ),
                False,
                0,
            )

        except APITimeoutError as e:
            logger.error("%s: Request timed out: %s", self.agent_name, str(e))
            return (
                json.dumps(
                    {
                        "findings": [],
                        "summary": f"Request timed out: {e}",
                        "verdict": "concerns",
                    }
                ),
                False,
                0,
            )

        except APIError as e:
            logger.error("%s: API error: %s", self.agent_name, str(e))
            return (
                json.dumps(
                    {
                        "findings": [],
                        "summary": f"API error: {e}",
                        "verdict": "concerns",
                    }
                ),
                False,
                0,
            )

        except Exception as e:
            logger.error("%s: Unexpected error: %s", self.agent_name, str(e))
            return (
                json.dumps(
                    {
                        "findings": [],
                        "summary": f"Unexpected error: {e}",
                        "verdict": "concerns",
                    }
                ),
                False,
                0,
            )

    async def review(
        self,
        diff_content: str,
        file_path: str = "",
        ci_context: str = "",
    ) -> AgentReview:
        """Perform an async code review with token optimization.

        Args:
            diff_content: Git diff string to analyze.
            file_path: Path to the file being reviewed.
            ci_context: Optional CI/CD context.

        Returns:
            AgentReview containing findings, summary, and verdict.
        """
        try:
            user_prompt = self._build_user_prompt(diff_content, file_path, ci_context)
            response, cached, tokens = await self._call_llm(user_prompt)
            return self._parse_response(response, cached, tokens)
        except Exception as e:
            logger.error(f"{self.agent_name}: Error in review: {e}")
            return AgentReview(
                findings=[],
                summary=f"Error: {str(e)[:100]}",
                verdict="concerns",
            )

    def _build_user_prompt(self, diff_content: str, file_path: str, ci_context: str) -> str:
        """Build the user prompt for the LLM with smart truncation.

        Args:
            diff_content: Git diff string to analyze.
            file_path: Path to the file being reviewed.
            ci_context: Optional CI/CD context.

        Returns:
            Formatted user prompt string.
        """
        prompt = f"File: {file_path}\n\n"
        prompt += f"Diff:\n```diff\n{diff_content}\n```\n"

        if ci_context:
            # Truncate CI context if too long
            ci_tokens = TokenTracker.estimate_tokens(ci_context)
            max_ci_tokens = 500  # Keep CI context small
            if ci_tokens > max_ci_tokens:
                ci_context = TokenTracker.truncate_for_context(ci_context, max_ci_tokens)
            prompt += f"\nCI Context:\n{ci_context}\n"

        prompt += "\nAnalyze the above diff and return your findings in JSON format."
        return prompt

    def _parse_response(
        self,
        content: str,
        cached: bool = False,
        tokens: int = 0,
    ) -> AgentReview:
        """Parse the LLM response into an AgentReview.

        Args:
            content: Raw string response from the LLM.
            cached: Whether response was from cache.
            tokens: Number of tokens used.

        Returns:
            Parsed AgentReview instance.
        """
        cleaned = content.strip()

        # Try to extract JSON from markdown code blocks
        if cleaned.startswith("```json"):
            cleaned = cleaned.removeprefix("```json").strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```").strip()

        if cleaned.endswith("```"):
            cleaned = cleaned.removesuffix("```").strip()

        # Try direct JSON parse first
        try:
            data = json.loads(cleaned)
            findings = []
            for item in data.get("findings", []):
                findings.append(Finding(**item))

            return AgentReview(
                findings=findings,
                summary=data.get("summary", ""),
                verdict=data.get("verdict", "concerns"),
                tokens_used=tokens,
                cached=cached,
            )
        except (json.JSONDecodeError, ValueError):
            pass

        # If JSON failed, try to extract from markdown
        # Look for verdict keyword
        verdict = "concerns"
        summary = ""

        content_lower = cleaned.lower()

        # Extract verdict
        if "verdict: critical" in content_lower or "verdict: **critical**" in content_lower:
            verdict = "critical"
        elif "verdict: pass" in content_lower or "verdict: **pass**" in content_lower:
            verdict = "pass"

        # Extract summary - take first few paragraphs
        lines = cleaned.split("\n")
        summary_lines = []
        in_summary = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Skip headers
            if line.startswith("#") or line.startswith("##"):
                continue
            # If line looks like a summary, capture it
            if len(line) > 20 and not line.startswith("-"):
                summary_lines.append(line)
                if len(summary_lines) >= 3:
                    break

        summary = " ".join(summary_lines) if summary_lines else cleaned[:200]

        return AgentReview(
            findings=[],
            summary=summary,
            verdict=verdict,
            tokens_used=tokens,
            cached=cached,
        )

    async def _parse_response_with_retry(
        self,
        user_prompt: str,
        content: str,
        cached: bool = False,
        tokens: int = 0,
    ) -> AgentReview:
        """Parse LLM response with robust retry on JSON failure.

        Tries up to 2 retries with stronger JSON enforcement prompts.
        """
        result = self._parse_response(content, cached, tokens)

        # If parsing succeeded with findings or valid verdict, return
        if result.findings or "Failed to parse" not in result.summary:
            return result

        # First retry with JSON correction
        logger.info("%s: First retry - enforcing JSON output", self.agent_name)
        retry_prompt = (
            "Your previous response was not valid JSON format. "
            "CRITICAL: You MUST output ONLY valid JSON, no markdown, no explanation. "
            "Output this exact schema:\n"
            '{"findings": [{"file_path": "string", "line_number": 1, "severity": "warning", "category": "string", "message": "string"}], "summary": "string", "verdict": "pass|concerns|critical"}\n'
            "Return ONLY the JSON, no text before or after."
        )

        try:
            retry_content, _, retry_tokens = await self._call_llm(
                user_prompt + "\n\n" + retry_prompt, use_cache=False
            )
            result = self._parse_response(retry_content, False, retry_tokens)
            if result.findings or "Failed to parse" not in result.summary:
                return result
        except Exception as e:
            logger.warning("%s: First retry failed: %s", self.agent_name, e)

        # Second retry with stronger enforcement
        logger.info("%s: Second retry - stricter JSON enforcement", self.agent_name)
        retry_prompt_2 = (
            "IMPORTANT: Previous responses were not proper JSON. "
            "You MUST follow these rules STRICTLY:\n"
            "1. Output ONLY valid JSON - no markdown code blocks\n"
            "2. Start with { and end with }\n"
            "3. Use exactly these keys: findings, summary, verdict\n"
            'Example: {"findings":[],"summary":"ok","verdict":"pass"}\n'
            "Do not add any explanation, headers, or markdown."
        )

        try:
            retry_content_2, _, retry_tokens_2 = await self._call_llm(
                user_prompt + "\n\n" + retry_prompt_2, use_cache=False
            )
            result = self._parse_response(retry_content_2, False, retry_tokens_2)
        except Exception as e:
            logger.warning("%s: Second retry failed: %s", self.agent_name, e)

        return result

    def _error_review(self, error_message: str) -> AgentReview:
        """Create a degraded AgentReview when an error occurs."""
        return AgentReview(
            findings=[],
            summary=f"Review failed due to error: {error_message}",
            verdict="concerns",
        )

    def clear_cache(self) -> None:
        """Clear the prompt cache for this agent."""
        if self._cache:
            self._cache.clear()
            logger.info(f"{self.agent_name}: Cache cleared")
