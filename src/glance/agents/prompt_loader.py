"""Prompt loader - loads agent prompts from markdown files."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("glance.prompts")

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts"

_AGENT_PROMPT_MAP = {
    "architect": "architect.md",
    "bug_hunter": "bug_hunter.md",
    "white_hat": "white_hat.md",
    "arbitrator": "arbitrator.md",
}


def load_prompt(agent_name: str, fallback: str = "") -> str:
    """Load a prompt from the prompts directory.

    Args:
        agent_name: One of 'architect', 'bug_hunter', 'white_hat', 'arbitrator'.
        fallback: Prompt string to return if file not found.

    Returns:
        Prompt content from markdown file, or fallback.
    """
    filename = _AGENT_PROMPT_MAP.get(agent_name)
    if not filename:
        return fallback

    prompt_file = _PROMPTS_DIR / filename
    if not prompt_file.exists():
        logger.warning(f"Prompt file not found: {prompt_file}, using fallback")
        return fallback

    try:
        content = prompt_file.read_text(encoding="utf-8")
        return _extract_system_prompt(content) or fallback
    except Exception as e:
        logger.warning(f"Failed to load prompt {filename}: {e}")
        return fallback


def _extract_system_prompt(markdown_content: str) -> str:
    """Extract the system prompt section from a markdown prompt file.

    Looks for content after '## System Prompt' heading until the next
    top-level heading (##) or end of file.
    """
    lines = markdown_content.splitlines()
    in_system_prompt = False
    prompt_lines = []

    for line in lines:
        if line.strip().startswith("## System Prompt"):
            in_system_prompt = True
            continue
        if in_system_prompt:
            if line.startswith("## ") and not line.startswith("## System Prompt"):
                break
            prompt_lines.append(line)

    if prompt_lines:
        return "\n".join(prompt_lines).strip()

    return markdown_content.strip()
