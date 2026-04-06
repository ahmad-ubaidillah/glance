"""Prompt Loader - Loads agent personas from .md files.

Allows customization of agent prompts by editing .md files in the prompts directory.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("glance.prompts")


class PromptLoader:
    """Loads and manages agent prompts from markdown files.

    Supports both file-based prompts and fallback to embedded prompts.
    """

    DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
    PROMPT_FILES = {
        "architect": "architect.md",
        "bug_hunter": "bug_hunter.md",
        "white_hat": "white_hat.md",
        "arbitrator": "arbitrator.md",
    }

    def __init__(self, prompts_dir: Path | str | None = None) -> None:
        """Initialize the prompt loader.

        Args:
            prompts_dir: Directory containing prompt .md files.
                        Defaults to ./prompts directory.
        """
        self.prompts_dir = (
            Path(prompts_dir) if prompts_dir else self.DEFAULT_PROMPTS_DIR
        )
        self._loaded_prompts: dict[str, str] = {}

    def load_prompt(self, agent_name: str) -> str:
        """Load a prompt for the specified agent.

        Args:
            agent_name: Name of the agent (architect, bug_hunter, white_hat, arbitrator).

        Returns:
            The system prompt for the agent.

        Raises:
            ValueError: If agent_name is unknown.
        """
        if agent_name in self._loaded_prompts:
            return self._loaded_prompts[agent_name]

        # Check if prompt file exists
        prompt_file = self.prompts_dir / self.PROMPT_FILES.get(agent_name, "")

        if prompt_file.exists():
            try:
                content = prompt_file.read_text(encoding="utf-8")
                # Extract content after the first markdown header
                prompt = self._extract_prompt_from_markdown(content)
                self._loaded_prompts[agent_name] = prompt
                logger.info(f"Loaded prompt for {agent_name} from {prompt_file}")
                return prompt
            except Exception as e:
                logger.warning(f"Failed to load prompt from {prompt_file}: {e}")

        # Fallback to embedded prompt
        fallback = self._get_fallback_prompt(agent_name)
        logger.info(f"Using fallback prompt for {agent_name}")
        return fallback

    def _extract_prompt_from_markdown(self, content: str) -> str:
        """Extract prompt content from markdown file.

        Skips the header section and returns the system prompt portion.

        Args:
            content: Full markdown content.

        Returns:
            Extracted prompt text.
        """
        lines = content.split("\n")

        # Find the ## System Prompt section
        in_system_prompt = False
        prompt_lines = []

        for line in lines:
            if "## System Prompt" in line:
                in_system_prompt = True
                continue
            if in_system_prompt:
                # Stop at the next ## section
                if line.startswith("## "):
                    break
                prompt_lines.append(line)

        # If no System Prompt section found, return everything after first header
        if not prompt_lines:
            found_first_header = False
            for line in lines:
                if line.startswith("# ") and not found_first_header:
                    found_first_header = True
                    continue
                if found_first_header:
                    prompt_lines.append(line)

        return "\n".join(prompt_lines).strip()

    def _get_fallback_prompt(self, agent_name: str) -> str:
        """Get embedded fallback prompt for an agent.

        These are the original prompts embedded in the agent code.

        Args:
            agent_name: Name of the agent.

        Returns:
            Fallback prompt string.
        """
        # Import here to avoid circular dependencies
        from glance.agents.architect import Architect
        from glance.agents.bug_hunter import BugHunterAgent
        from glance.agents.white_hat import WhiteHatAgent
        from glance.agents.arbitrator import ArbitratorAgent

        fallbacks = {
            "architect": Architect.system_prompt.fget.__self__.system_prompt
            if hasattr(Architect.system_prompt.fget, "__self__")
            else "",
            "bug_hunter": "",
            "white_hat": "",
            "arbitrator": "",
        }

        # For simplicity, return a simple fallback based on agent type
        if agent_name == "architect":
            return """You are The Architect, a senior software engineer specializing in code quality, 
architecture, and design patterns. Your role is to review code changes (git diffs) 
and identify architectural and design-level issues.

Focus on:
- SOLID principles violations
- DRY principle violations
- Design pattern appropriateness
- File complexity and anti-file-hell
- Naming conventions and readability
- Proper abstraction levels

Return findings as JSON with: findings (file_path, line_number, severity, category, message, suggestion, code_snippet), summary, and verdict (pass/concerns/critical)."""
        elif agent_name == "bug_hunter":
            return """You are The Bug Hunter, a senior QA engineer specializing in finding bugs, edge cases, and logic errors.

Focus on:
- Edge cases and boundary conditions
- Error handling completeness
- Business logic correctness
- Null/undefined handling
- Race conditions and concurrency issues
- Off-by-one errors
- Input validation gaps

Return findings as JSON with: findings (file_path, line_number, severity, category, message, suggestion, code_snippet), summary, and verdict."""
        elif agent_name == "white_hat":
            return """You are The White Hat, a senior security researcher specializing in code security analysis.

Focus on:
- OWASP Top 10 vulnerabilities
- SQL Injection, XSS, CSRF, SSRF
- Hardcoded secrets and credentials
- Insecure configurations
- Memory safety issues (Rust/Zig)
- Authentication and authorization flaws

Return findings as JSON with: findings (file_path, line_number, severity, category, message, suggestion, code_snippet), summary, and verdict."""
        elif agent_name == "arbitrator":
            return """You are The Arbitrator, a senior lead developer who consolidates code review findings.

Your role:
1. Review findings from multiple specialized agents
2. Filter noise: nitpicks, style preferences, false positives
3. Identify genuine issues that need attention
4. Resolve conflicts between agent opinions
5. Provide a final verdict and action items

Verdict rules:
- APPROVE: No significant issues
- REQUEST_CHANGES: Issues that should be addressed
- BLOCK_SECURITY: Critical security vulnerability found

Return consolidated findings as JSON."""
        else:
            raise ValueError(f"Unknown agent: {agent_name}")

    def reload_prompts(self) -> None:
        """Clear cached prompts and reload from files."""
        self._loaded_prompts.clear()
        logger.info("Prompt cache cleared")

    def list_available_prompts(self) -> dict[str, Path]:
        """List all available prompt files.

        Returns:
            Dict mapping agent names to their prompt file paths.
        """
        result = {}
        for agent, filename in self.PROMPT_FILES.items():
            path = self.prompts_dir / filename
            result[agent] = path if path.exists() else None
        return result


def load_prompt(agent_name: str, prompts_dir: Path | str | None = None) -> str:
    """Convenience function to load a prompt.

    Args:
        agent_name: Name of the agent.
        prompts_dir: Optional custom prompts directory.

    Returns:
        The system prompt for the agent.
    """
    loader = PromptLoader(prompts_dir)
    return loader.load_prompt(agent_name)
