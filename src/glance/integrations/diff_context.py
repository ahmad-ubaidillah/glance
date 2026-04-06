"""Diff Context Enhancer - Fetch surrounding code for better LLM context.

For each changed file, fetches the actual file content and extracts
relevant context (function/class) around changed lines.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("glance.diff_context")


def get_file_content_at_line(pr, file_path: str, line_number: int, context_lines: int = 10) -> str:
    """Get file content with surrounding context at a specific line.

    Args:
        pr: PyGithub PullRequest object.
        file_path: Path to the file.
        line_number: Line number to get context around.
        context_lines: Number of lines before/after to include.

    Returns:
        File content with context, or empty string on error.
    """
    try:
        repo = pr.base.repository
        file_content = repo.get_contents(file_path, ref=pr.head.sha)
        if file_content.encoding == "base64":
            import base64

            content = base64.b64decode(file_content.content).decode("utf-8")
        else:
            content = file_content.decoded_content.decode("utf-8")

        lines = content.split("\n")
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)

        result = []
        for i in range(start, end):
            marker = ">>>" if i == line_number - 1 else "   "
            result.append(f"{marker} {i + 1}: {lines[i]}")

        return "\n".join(result)
    except Exception as e:
        logger.debug(f"Failed to get file content for {file_path}:{line_number}: {e}")
        return ""


def enhance_diff_with_context(pr, diff_content: str, findings: list) -> str:
    """Enhance diff with file context for important findings.

    For critical findings, fetch surrounding code to give LLM better context.
    """
    if not findings:
        return diff_content

    context_parts = [diff_content]
    critical_findings = [f for f in findings if getattr(f, "severity", "") == "critical"]

    for finding in critical_findings[:5]:
        fp = getattr(finding, "file_path", "")
        ln = getattr(finding, "line_number", 0)
        if fp and ln:
            ctx = get_file_content_at_line(pr, fp, ln, context_lines=8)
            if ctx:
                context_parts.append(f"\n--- Context for {fp}:{ln} ---\n{ctx}")

    return "\n".join(context_parts)
