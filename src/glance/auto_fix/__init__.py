"""Auto-fix generator for Glance.

Generates suggested code changes that can be applied directly
via GitHub's "Suggested Changes" feature.
"""

from __future__ import annotations

import difflib
import json
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
    category: str

    @property
    def severity_label(self) -> str:
        labels = {
            "security": "🔒 Critical",
            "logic": "🔧 Must Fix",
            "syntax": "📝 Should Fix",
            "style": "🎨 Nice to Have",
            "performance": "⚡ Should Fix",
        }
        return labels.get(self.category, "💡 Suggestion")


class AutoFixGenerator:
    """Generates auto-fix suggestions for code issues."""

    FIX_PROMPT = """You are an expert code reviewer. For each issue, provide a minimal, correct fix.

Rules:
1. Keep fixes minimal - only change what's necessary
2. Preserve original code structure and intent
3. Include proper error handling where needed
4. Use language-appropriate patterns
5. Return ONLY valid JSON

Output format:
{
  "fixes": [
    {
      "file_path": "path/to/file.py",
      "line_number": 42,
      "original_code": "exact problematic code",
      "fixed_code": "corrected code",
      "description": "one-line explanation",
      "category": "syntax|style|logic|security|performance"
    }
  ]
}

Return ONLY valid JSON. No markdown, no explanation."""

    def __init__(self, llm_client: Any, model: str = "glm-5") -> None:
        self.client = llm_client
        self.model = model

    async def generate_fixes(
        self,
        findings: list[Any],
        diff_content: str,
    ) -> list[SuggestedChange]:
        """Generate auto-fix suggestions for findings."""
        if not findings:
            return []

        findings_summary = self._build_findings_summary(findings)

        try:
            response = await self._call_llm(findings_summary, diff_content)
            return self._parse_fixes(response)
        except Exception as e:
            logger.error(f"Failed to generate fixes: {e}")
            return []

    def _build_findings_summary(self, findings: list[Any]) -> str:
        """Build a summary of findings for the LLM."""
        lines = ["Issues to fix:"]
        for i, f in enumerate(findings, 1):
            msg = getattr(f, "message", "")
            snippet = getattr(f, "code_snippet", "")
            suggestion = getattr(f, "suggestion", "")
            fp = getattr(f, "file_path", "unknown")
            ln = getattr(f, "line_number", 0)
            cat = getattr(f, "category", "general")
            sev = getattr(f, "severity", "warning")

            lines.append(f"{i}. [{sev}] {fp}:{ln} - {msg}")
            if snippet:
                lines.append(f"   Code: {snippet}")
            if suggestion:
                lines.append(f"   Hint: {suggestion}")
            lines.append(f"   Category: {cat}")

        return "\n".join(lines)

    async def _call_llm(self, findings_summary: str, diff_content: str) -> str:
        """Call LLM to generate fixes."""
        try:
            if hasattr(self.client, "chat"):
                response = await self.client.chat(
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
                return getattr(response, "content", "")
            return "{}"
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return "{}"

    def _parse_fixes(self, response: str) -> list[SuggestedChange]:
        """Parse LLM response into suggested changes."""
        fixes = []
        try:
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned.removeprefix("```json").strip()
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

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
            fixes = self._parse_fixes_from_markdown(response)
            if not fixes:
                logger.warning(f"Failed to parse fixes: {e}")
        return fixes

    def _parse_fixes_from_markdown(self, content: str) -> list[SuggestedChange]:
        """Parse fixes from markdown when JSON fails."""
        fixes = []
        lines = content.split("\n")
        current_file = None
        current_fix = None
        original_lines = []
        fixed_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect file path
            if line.startswith("File:") or line.startswith("**File:"):
                if current_fix and (original_lines or fixed_lines):
                    current_fix.original_code = "\n".join(original_lines)
                    current_fix.fixed_code = "\n".join(fixed_lines)
                    fixes.append(current_fix)
                current_file = line.split(":", 1)[-1].strip().strip("*")
                current_fix = None
                original_lines = []
                fixed_lines = []
                continue

            # Detect original code (before)
            if "before" in line.lower() or "original" in line.lower():
                original_lines = []
                continue

            # Detect fixed code (after)
            if "after" in line.lower() or "fixed" in line.lower():
                fixed_lines = []
                continue

            # Collect code lines
            if line.startswith("+") or line.startswith("-") or line.startswith(" "):
                if "original" in str(current_fix) if current_fix else False:
                    original_lines.append(line)
                else:
                    fixed_lines.append(line)

        # Add last fix
        if current_fix and (original_lines or fixed_lines):
            current_fix.original_code = "\n".join(original_lines)
            current_fix.fixed_code = "\n".join(fixed_lines)
            fixes.append(current_fix)

        return fixes

    def format_github_suggestion(self, fix: SuggestedChange) -> str:
        """Format a fix as GitHub suggested change."""
        diff = difflib.unified_diff(
            fix.original_code.splitlines(keepends=True),
            fix.fixed_code.splitlines(keepends=True),
            fromfile=fix.file_path,
            tofile=fix.file_path,
            lineterm="",
        )

        suggestion = f"💡 **Suggested Fix** ({fix.severity_label})\n\n"
        suggestion += f"{fix.description}\n\n"
        suggestion += "```diff\n"
        for line in diff:
            suggestion += line
        suggestion += "```"
        return suggestion

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
            comment += f"**Before:**\n```python\n{fix.original_code}\n```\n\n"
            comment += f"**After:**\n```python\n{fix.fixed_code}\n```\n"
        return comment


async def generate_and_post_fixes(
    pr: Any,
    findings: list[Any],
    diff_content: str,
    llm_client: Any,
    model: str = "glm-5",
) -> int:
    """Convenience function to generate and post fixes."""
    generator = AutoFixGenerator(llm_client, model)
    fixes = await generator.generate_fixes(findings, diff_content)
    posted = 0
    for fix in fixes[:10]:
        try:
            body = generator._format_review_comment(fix)
            pr.create_review_comment(
                body=body,
                commit=pr.head.sha,
                path=fix.file_path,
                line=fix.line_number,
            )
            posted += 1
        except Exception as e:
            logger.warning(f"Failed to post fix for {fix.file_path}:{fix.line_number}: {e}")
    return posted
