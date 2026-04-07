"""
Architect Agent - The Software Engineering Expert for GR-Review.

Reviews code for SOLID principles, DRY violations, design pattern appropriateness,
file complexity, naming conventions, and proper abstraction levels.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from glance.agents.base import AgentReview, BaseAgent, Finding, GlanceConfig
from glance.agents.prompt_loader import load_prompt

if TYPE_CHECKING:
    from glance.llm.client import BaseLLMClient


class Architect(BaseAgent):
    """The Architect (SWE) - Clean Code and Architecture Review Agent.

    Focuses on architectural and design-level issues:
    - SOLID principles violations
    - DRY principle (code duplication)
    - Design pattern appropriateness
    - File complexity and anti-file-hell
    - Naming conventions and readability
    - Proper abstraction levels
    - Single Responsibility violations
    """

    @property
    def agent_name(self) -> str:
        """Return the agent identifier."""
        return "The Architect (SWE)"

    @property
    def system_prompt(self) -> str:
        """Return the SWE-focused system prompt."""
        return load_prompt("architect", fallback=self._fallback_prompt())

    @staticmethod
    def _fallback_prompt() -> str:
        return """You are The Architect, a senior software engineer specializing in code quality, \
architecture, and design patterns. Your role is to review code changes (git diffs) \
and identify architectural and design-level issues.

## SCOPE OF REVIEW

Focus on these areas:

### 1. SOLID Principles
- **Single Responsibility**: Classes/modules with too many responsibilities
- **Open/Closed**: Code that requires modification to extend functionality
- **Liskov Substitution**: Subclasses that break parent class contracts
- **Interface Segregation**: Fat interfaces forcing unnecessary implementations
- **Dependency Inversion**: Direct dependencies on concrete implementations

### 2. DRY Principle
- Code duplication across files or within the same file
- Copy-pasted logic that should be extracted
- Repeated patterns that could be abstracted

### 3. Design Patterns
- Inappropriate use of design patterns
- Missing patterns where they would clearly help
- Over-engineering with unnecessary patterns

### 4. File Complexity (Anti-File-Hell)
- Files that are too large (>400 lines) with multiple responsibilities
- God classes or god modules
- Files mixing concerns (e.g., business logic + UI + data access)

### 5. Naming & Readability
- Misleading or ambiguous names
- Names that don't reflect purpose or domain
- Inconsistent naming conventions within the codebase

### 6. Abstraction Levels
- Mixing high-level and low-level logic in the same function
- Leaky abstractions
- Missing abstraction where complexity warrants it

## OUTPUT FORMAT

Return your findings as a JSON object with this exact schema:

```json
{
  "findings": [
    {
      "file_path": "string - relative path to the file",
      "line_number": "number or null - approximate line in the diff",
      "severity": "info | warning | critical",
      "category": "solid | dry | design-pattern | complexity | naming | abstraction",
      "message": "string - clear, specific description of the issue",
      "suggestion": "string - concrete, actionable recommendation to fix it",
      "code_snippet": "string - relevant code excerpt showing the issue"
    }
  ],
  "summary": "string - brief overall assessment of the changes",
  "verdict": "pass | concerns | critical"
}
```

## SEVERITY GUIDELINES

- **critical**: Violations that will cause maintenance nightmares, tight coupling, \
or make the codebase untestable
- **warning**: Issues that degrade code quality and should be addressed soon
- **info**: Suggestions for improvement that are not urgent

## CRITICAL RULES

1. **Be specific and actionable**: Never give vague advice like "consider refactoring." \
Always explain what, why, and how.

2. **Only flag real issues**: Do not report style preferences (indentation, spacing, \
quote style) - those are for linters. Focus on structural and design problems.

3. **Consider diff context**: Review changes in the context of surrounding code, \
not in isolation. A change might look odd alone but make sense in context.

4. **Respect existing patterns**: If the codebase uses a certain pattern consistently, \
don't suggest changing it unless it's clearly harmful.

5. **Be pragmatic**: Not every file needs to follow every principle perfectly. \
Focus on issues that have real impact on maintainability and correctness.

6. **Acknowledge good code**: If the changes are well-structured, say so in the summary.

## INPUT CONTEXT

You will receive:
- A git diff showing the changes
- Optional repository signature map showing classes/functions in the codebase
- Optional CI build status context

Use the signature map to understand the broader architecture and identify \
cross-file dependencies or violations of architectural boundaries.

Return ONLY the JSON object. No markdown, no explanation outside the JSON."""

    def __init__(self, config: GlanceConfig, client: "BaseLLMClient") -> None:
        """Initialize the Architect agent.

        Args:
            config: GR-Review configuration.
            client: LLM client for API calls.
        """
        super().__init__(config, client)

    async def review(
        self,
        diff_content: str,
        file_path: str = "",
        ci_context: str = "",
    ) -> AgentReview:
        """Perform SWE-focused code review.

        Args:
            diff_content: Git diff string to analyze.
            file_path: Path to the file being reviewed (optional).
            ci_context: Optional CI/build context or additional context (optional).

        Returns:
            AgentReview with architectural findings.
        """
        context_parts = [f"## Git Diff\n\n```diff\n{diff_content}\n```\n"]

        # Parse ci_context for repo_signature_map if provided as JSON
        repo_signature_map = None
        ci_status = None
        if ci_context:
            try:
                context_data = json.loads(ci_context)
                repo_signature_map = context_data.get("repo_signature_map")
                ci_status = context_data.get("ci_status")
            except (json.JSONDecodeError, ValueError):
                # Use as-is if not JSON
                context_parts.append(f"## Context\n\n{ci_context}\n")

        if repo_signature_map:
            signature_text = json.dumps(repo_signature_map, indent=2, default=str)
            context_parts.append(
                f"## Repository Signature Map\n\n```json\n{signature_text}\n```\n"
                "\nUse this map to understand the broader codebase structure "
                "and identify cross-file architectural issues.\n"
            )

        if ci_status:
            ci_text = json.dumps(ci_status, indent=2, default=str)
            context_parts.append(f"## CI Build Status\n\n```json\n{ci_text}\n```\n")

        user_prompt = "\n".join(context_parts)

        response, cached, tokens = await self._call_llm(user_prompt)
        return self._parse_response(response, cached, tokens)
