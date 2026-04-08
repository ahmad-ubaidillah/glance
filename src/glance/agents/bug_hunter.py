"""Bug Hunter Agent - QA specialist for logic and bug detection.

Focuses on edge cases, boundary values, error handling, and business logic bugs.
"""

from __future__ import annotations

from glance.agents.base import AgentReview, BaseAgent, GlanceConfig
from glance.agents.prompt_loader import load_prompt


class BugHunterAgent(BaseAgent):
    """QA Agent specializing in bug detection and logic analysis.

    This agent focuses on:
    - Edge cases and boundary conditions
    - Error handling completeness
    - Business logic correctness
    - Null/undefined handling
    - Race conditions and concurrency issues
    - Off-by-one errors
    - Input validation gaps
    """

    @property
    def agent_name(self) -> str:
        """Return the agent identifier."""
        return "BugHunter"

    @property
    def system_prompt(self) -> str:
        """Return the QA-focused system prompt."""
        return load_prompt("bug_hunter", fallback=self._fallback_prompt())

    @staticmethod
    def _fallback_prompt() -> str:
        return """You are The Bug Hunter, a senior QA engineer specializing in finding bugs, edge cases, and logic errors.

YOUR FOCUS AREAS:
1. Edge Cases: What happens with empty inputs? Null values? Maximum sizes?
2. Boundary Values: Off-by-one errors, integer overflow, array bounds
3. Error Handling: Are all exceptions caught? Are error messages useful?
4. Business Logic: Does the code correctly implement the intended behavior?
5. Concurrency: Race conditions, deadlocks, thread safety issues
6. State Management: Invalid state transitions, missing state checks
7. Input Validation: Missing validation, injection risks in data

REVIEW GUIDELINES:
- Focus on functional correctness, not style
- Identify concrete bugs over theoretical issues
- Consider the "unhappy path" - what could go wrong?
- Check for missing null checks and type validation
- Look for logic errors in conditionals and loops
- Verify error handling is comprehensive

OUTPUT FORMAT (JSON):
{
  "findings": [
    {
      "file_path": "path/to/file.py",
      "line_number": 42,
      "severity": "warning",
      "category": "bug",
      "message": "Description of the bug",
      "suggestion": "How to fix it",
      "code_snippet": "relevant code"
    }
  ],
  "summary": "Overall assessment of code quality",
  "verdict": "pass|concerns|critical"
}

CRITICAL: Use EXACTLY these field names:
- file_path (not path, not filename)
- line_number as a NUMBER (e.g. 42, not "42")
- severity (not type)
- category (not kind)
- message (not description)

SEVERITY LEVELS:
- critical: Definite bug that will cause failures or data corruption
- warning: Likely bug or missing error handling that could cause issues
- info: Potential improvement or minor edge case to consider

VERDICT:
- pass: No significant bugs found
- concerns: Some issues found that should be addressed
- critical: Critical bugs found that must be fixed before merge"""

    async def review(
        self, diff_content: str, file_path: str = "", ci_context: str = ""
    ) -> AgentReview:
        """Perform QA-focused code review.

        If CI context shows build/test failures, prioritize root cause analysis.

        Args:
            diff_content: Git diff string to analyze.
            file_path: Path to the file being reviewed.
            ci_context: CI/CD context including build and test status.

        Returns:
            AgentReview with bug-related findings.
        """
        enhanced_context = ci_context

        # If CI failed, add root cause analysis instruction
        if ci_context and ("failed" in ci_context.lower() or "error" in ci_context.lower()):
            enhanced_context = f"""CI STATUS: FAILURE DETECTED
{ci_context}

IMPORTANT: The CI pipeline has failed. Prioritize ROOT CAUSE ANALYSIS:
1. Look for code that could cause the reported failures
2. Check for syntax errors, import issues, or type mismatches
3. Identify test failures and their likely causes
4. Focus on the changed lines in this diff"""

        return await super().review(diff_content, file_path, enhanced_context)
