"""Auto-fix generator for GR-Review.

Generates suggested code changes that can be applied directly
via GitHub's "Suggested Changes" feature.
"""

from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("glance.auto_fix")


@dataclass
class SuggestedChange:
    """Represents a suggested code change."""

    file_path: str
    line_number: int
    original_code: str
    fixed_code: str
    description: str
    category: str  # "syntax", "style", "logic", "security", "performance"


class AutoFixGenerator:
    """Generates auto-fix suggestions for code issues."""

    # Prompt template for generating fixes
    FIX_PROMPT = """You are an expert code reviewer. For each issue found, provide a suggested fix.

For each finding, respond with this JSON format:
{
  "fixes": [
    {
      "file_path": "path/to/file.py",
      "line_number": 42,
      "original_code": "the problematic code",
      "fixed_code": "the corrected code",
      "description": "brief explanation of the fix",
      "category": "syntax|style|logic|security|performance"
    }
  ]
}

Focus on:
- Concrete, testable fixes
- Minimal changes that solve the issue
- Preserving the original code's intent
- Security fixes for vulnerabilities

Return ONLY valid JSON."""

    def __init__(self, llm_client: Any, model: str = "glm-4-flash") -> None:
        """Initialize auto-fix generator.

        Args:
            llm_client: LLM client for generating fixes.
            model: Model to use.
        """
        self.client = llm_client
        self.model = model

    async def generate_fixes(
        self,
        findings: list[Any],
        diff_content: str,
    ) -> list[SuggestedChange]:
        """Generate auto-fix suggestions for findings.

        Args:
            findings: List of findings from review.
            diff_content: Original diff content.

        Returns:
            List of suggested changes.
        """
        if not findings:
            return []

        # Build findings summary for the LLM
        findings_summary = self._build_findings_summary(findings)

        try:
            # Call LLM to generate fixes
            response = await self._call_llm(findings_summary, diff_content)
            return self._parse_fixes(response, diff_content)

        except Exception as e:
            logger.error(f"Failed to generate fixes: {e}")
            return []

    def _build_findings_summary(self, findings: list[Any]) -> str:
        """Build a summary of findings for the LLM."""
        lines = ["Issues to fix:"]

        for i, finding in enumerate(findings, 1):
            lines.append(f"{i}. {finding.category} - {finding.message}")
            if finding.code_snippet:
                lines.append(f"   Code: {finding.code_snippet[:100]}")
            if finding.suggestion:
                lines.append(f"   Suggestion: {finding.suggestion[:100]}")

        return "\n".join(lines)

    async def _call_llm(self, findings_summary: str, diff_content: str) -> str:
        """Call LLM to generate fixes."""
        try:
            # Try OpenAI-compatible interface
            if hasattr(self.client, "chat_completions"):
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.FIX_PROMPT},
                        {
                            "role": "user",
                            "content": f"{findings_summary}\n\nDiff:\n{diff_content[:5000]}",
                        },
                    ],
                    temperature=0.2,
                    max_tokens=2000,
                )
                return response.choices[0].message.content or ""
            # Try custom interface
            elif hasattr(self.client, "chat"):
                response = await self.client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.FIX_PROMPT},
                        {
                            "role": "user",
                            "content": f"{findings_summary}\n\nDiff:\n{diff_content[:5000]}",
                        },
                    ],
                    temperature=0.2,
                    max_tokens=2000,
                )
                return response.content
            else:
                return "{}"

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return "{}"

    def _parse_fixes(self, response: str, diff_content: str) -> list[SuggestedChange]:
        """Parse LLM response into suggested changes."""
        import json

        fixes = []

        try:
            # Clean response
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

            data = json.loads(cleaned)

            for fix_data in data.get("fixes", []):
                fixes.append(
                    SuggestedChange(
                        file_path=fix_data.get("file_path", "unknown"),
                        line_number=fix_data.get("line_number", 0),
                        original_code=fix_data.get("original_code", ""),
                        fixed_code=fix_data.get("fixed_code", ""),
                        description=fix_data.get("description", ""),
                        category=fix_data.get("category", "general"),
                    )
                )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse fixes: {e}")

        return fixes

    def format_github_suggestion(self, fix: SuggestedChange) -> str:
        """Format a fix as GitHub suggested change.

        Args:
            fix: The suggested change.

        Returns:
            Markdown-formatted suggestion for GitHub.
        """
        # Create unified diff format for GitHub suggestions
        diff = difflib.unified_diff(
            fix.original_code.splitlines(keepends=True),
            fix.fixed_code.splitlines(keepends=True),
            fromfile=fix.file_path,
            tofile=fix.file_path,
            lineterm="",
        )

        suggestion = f"```suggestion\n"
        suggestion += f"{fix.description}\n"
        suggestion += "---\n"
        suggestion += "```diff\n"
        for line in diff:
            suggestion += line
        suggestion += "```"

        return suggestion

    def post_suggestions_to_github(
        self,
        pr: Any,
        fixes: list[SuggestedChange],
    ) -> int:
        """Post suggested changes to GitHub PR.

        Args:
            pr: PyGithub PullRequest object.
            fixes: List of suggested changes.

        Returns:
            Number of suggestions posted.
        """
        posted = 0

        for fix in fixes[:10]:  # Limit to 10 suggestions
            try:
                # Format the suggestion as a review comment with suggested change
                body = self._format_review_comment(fix)

                pr.create_review_comment(
                    body=body,
                    commit_sha=pr.head.sha,
                    path=fix.file_path,
                    line=fix.line_number,
                )
                posted += 1

            except Exception as e:
                logger.warning(
                    f"Failed to post suggestion for {fix.file_path}:{fix.line_number}: {e}"
                )

        return posted

    def _format_review_comment(self, fix: SuggestedChange) -> str:
        """Format a fix as a review comment."""
        emoji_map = {
            "syntax": "📝",
            "style": "🎨",
            "logic": "🔧",
            "security": "🔒",
            "performance": "⚡",
        }

        emoji = emoji_map.get(fix.category, "💡")

        comment = f"{emoji} **Suggested Fix** ({fix.category})\n\n"
        comment += f"{fix.description}\n\n"

        if fix.original_code and fix.fixed_code:
            comment += "**Before:**\n"
            comment += f"```python\n{fix.original_code[:200]}\n```\n\n"
            comment += "**After:**\n"
            comment += f"```python\n{fix.fixed_code[:200]}\n```\n"

        return comment


async def generate_and_post_fixes(
    pr: Any,
    findings: list[Any],
    diff_content: str,
    llm_client: Any,
    model: str = "glm-4-flash",
) -> int:
    """Convenience function to generate and post fixes.

    Args:
        pr: PyGithub PR object.
        findings: List of findings.
        diff_content: Original diff.
        llm_client: LLM client.
        model: Model name.

    Returns:
        Number of fixes posted.
    """
    generator = AutoFixGenerator(llm_client, model)
    fixes = await generator.generate_fixes(findings, diff_content)
    return generator.post_suggestions_to_github(pr, fixes)
