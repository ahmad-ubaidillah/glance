"""Smart Diff Processor - Intelligent token-efficient diff handling.

Provides:
- Smart truncation that preserves important context
- File prioritization based on change type
- Incremental analysis for large PRs
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("glance.diff")


@dataclass
class DiffChunk:
    """Represents a chunk of diff with metadata."""

    file_path: str
    change_type: str  # added, removed, modified, new, renamed
    hunks: list[str]
    lines_added: int
    lines_removed: int
    is_test: bool
    is_config: bool


@dataclass
class ProcessingResult:
    """Result of diff processing."""

    chunks: list[DiffChunk]
    total_tokens_estimate: int
    should_split: bool  # If too large, needs multiple reviews
    recommended_agents: list[str]  # Which agents to run


class SmartDiffProcessor:
    """Intelligent diff processing for token optimization."""

    # Priority order for files (higher = more important to review thoroughly)
    FILE_PRIORITY = {
        "test": 1.0,  # Tests are high priority
        "config": 0.8,  # Config files matter
        "source": 1.0,  # Main source code
        "docs": 0.3,  # Documentation low priority
        "other": 0.5,
    }

    # Extensions that indicate test files
    TEST_EXTENSIONS = {
        ".test.py",
        ".tests.py",
        "_test.py",
        "_tests.py",
        ".spec.js",
        ".spec.ts",
        ".test.js",
        ".test.ts",
        "test_*.py",
        "*_test.py",
    }

    # Config file patterns
    CONFIG_PATTERNS = {
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".ini",
        ".env",
        ".conf",
        ".config",
    }

    def __init__(
        self,
        max_tokens: int = 8000,
        min_context_lines: int = 3,
        max_files_per_review: int = 10,
    ) -> None:
        """Initialize the processor.

        Args:
            max_tokens: Maximum tokens allowed in a single review.
            min_context_lines: Minimum lines of context to keep around changes.
            max_files_per_review: Maximum files to include in one review.
        """
        self.max_tokens = max_tokens
        self.min_context_lines = min_context_lines
        self.max_files_per_review = max_files_per_review

    def process_diff(self, raw_diff: str) -> ProcessingResult:
        """Process and optimize a diff for token efficiency.

        Args:
            raw_diff: Raw git diff string.

        Returns:
            ProcessingResult with optimized chunks and metadata.
        """
        if not raw_diff:
            return ProcessingResult(
                chunks=[],
                total_tokens_estimate=0,
                should_split=False,
                recommended_agents=[],
            )

        # Parse diff into chunks
        chunks = self._parse_diff(raw_diff)

        # Categorize files
        for chunk in chunks:
            chunk.is_test = self._is_test_file(chunk.file_path)
            chunk.is_config = self._is_config_file(chunk.file_path)

        # Estimate tokens
        total_tokens = self._estimate_tokens(chunks)

        # Determine if we need to split
        should_split = total_tokens > self.max_tokens

        # Determine recommended agents based on content
        agents = self._determine_agents(chunks)

        return ProcessingResult(
            chunks=chunks,
            total_tokens_estimate=total_tokens,
            should_split=should_split,
            recommended_agents=agents,
        )

    def _parse_diff(self, raw_diff: str) -> list[DiffChunk]:
        """Parse raw diff into structured chunks."""
        chunks = []
        current_file = None
        current_hunks = []
        current_type = "modified"

        for line in raw_diff.split("\n"):
            if line.startswith("+++ b/") or line.startswith("diff --git"):
                # New file
                if current_file:
                    chunks.append(
                        DiffChunk(
                            file_path=current_file,
                            change_type=current_type,
                            hunks=current_hunks,
                            lines_added=current_hunks.count("+"),
                            lines_removed=current_hunks.count("-"),
                            is_test=False,
                            is_config=False,
                        )
                    )

                # Extract filename
                if " b/" in line:
                    current_file = line.split(" b/")[-1].strip()
                else:
                    parts = line.split(" a/")[-1].split(" b/")
                    current_file = parts[-1] if len(parts) > 1 else parts[0]

                current_hunks = []
                current_type = "new" if line.startswith("diff") else "modified"

            elif line.startswith("new file"):
                current_type = "new"
            elif line.startswith("deleted file"):
                current_type = "removed"
            elif line.startswith("rename"):
                current_type = "renamed"
            elif line.startswith("@@"):
                current_hunks.append(line)  # Keep hunk headers
            elif line.startswith(("+", "-")) and not line.startswith("+++"):
                current_hunks.append(line[:200])  # Truncate long lines

        # Add last file
        if current_file and current_hunks:
            chunks.append(
                DiffChunk(
                    file_path=current_file,
                    change_type=current_type,
                    hunks=current_hunks,
                    lines_added=sum(1 for h in current_hunks if h.startswith("+")),
                    lines_removed=sum(1 for h in current_hunks if h.startswith("-")),
                    is_test=self._is_test_file(current_file),
                    is_config=self._is_config_file(current_file),
                )
            )

        return chunks

    def _is_test_file(self, file_path: str) -> bool:
        """Check if file is a test file."""
        name = file_path.lower()
        return any(ext in name for ext in self.TEST_EXTENSIONS)

    def _is_config_file(self, file_path: str) -> bool:
        """Check if file is a config file."""
        return any(file_path.endswith(ext) for ext in self.CONFIG_PATTERNS)

    def _estimate_tokens(self, chunks: list[DiffChunk]) -> int:
        """Estimate total tokens for all chunks."""
        total = 0
        for chunk in chunks:
            # Rough estimate: ~3 chars per token for code
            for hunk in chunk.hunks:
                total += len(hunk) // 3
        return total

    def _determine_agents(self, chunks: list[DiffChunk]) -> list[str]:
        """Determine which agents to run based on content."""
        has_tests = any(c.is_test for c in chunks)
        has_security = any(c.file_path.endswith(ext) for ext in [".py", ".js", ".ts", ".go", ".rs"])
        has_config = any(c.is_config for c in chunks)

        agents = ["architect"]  # Always run architect

        if has_tests:
            agents.append("bug_hunter")
        if has_security:
            agents.append("white_hat")
        if has_config:
            agents.append("architect")  # Re-emphasize

        return list(set(agents))  # Remove duplicates

    def get_optimized_diff(
        self,
        chunks: list[DiffChunk],
        focus_files: list[str] | None = None,
    ) -> str:
        """Get optimized diff string for LLM.

        Args:
            chunks: Diff chunks to include.
            focus_files: Optional list of files to prioritize.

        Returns:
            Optimized diff string.
        """
        if not chunks:
            return ""

        # Sort by priority
        sorted_chunks = sorted(
            chunks,
            key=lambda c: (
                0 if focus_files and c.file_path in focus_files else 1,
                0 if c.is_test else 1,
                0 if c.is_config else 1,
            ),
        )

        # Limit files
        limited_chunks = sorted_chunks[: self.max_files_per_review]

        # Build diff
        diff_lines = []
        for chunk in limited_chunks:
            diff_lines.append(f"--- a/{chunk.file_path}")
            diff_lines.append(f"+++ b/{chunk.file_path}")

            # Add hunks with context
            for hunk in chunk.hunks[:50]:  # Limit hunks per file
                diff_lines.append(hunk)

            diff_lines.append("")  # Separator

        return "\n".join(diff_lines)

    def should_use_incremental(self, pr_number: int, repo: str) -> bool:
        """Check if should use incremental review based on PR history.

        Args:
            pr_number: PR number.
            repo: Repository name.

        Returns:
            True if incremental review is recommended.
        """
        # Could integrate with knowledge base to check PR history
        # For now, return False (full review)
        return False


def estimate_diff_tokens(diff: str) -> int:
    """Quick function to estimate token count for a diff.

    Args:
        diff: Raw diff string.

    Returns:
        Estimated token count.
    """
    if not diff:
        return 0

    # Rough estimate: 3 chars per token for code
    return len(diff) // 3
