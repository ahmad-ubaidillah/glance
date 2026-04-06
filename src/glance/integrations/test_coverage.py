"""Test Coverage Detection - Find test files related to changed code.

Detects which changed files have test coverage and which don't,
so agents can flag untested code changes.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger("glance.coverage")


def find_test_files(repo_root: Path) -> list[Path]:
    """Find all test files in the repository."""
    test_patterns = [
        "test_*.py",
        "*_test.py",
        "tests/**/*.py",
        "test/**/*.py",
        "__tests__/**/*.py",
        "*.test.py",
        "*.spec.py",
    ]

    test_files = []
    for pattern in test_patterns:
        test_files.extend(repo_root.glob(pattern))

    return list(set(test_files))


def get_coverage_for_files(repo_root: Path, changed_files: list[str]) -> dict[str, bool]:
    """Determine which changed files have corresponding tests.

    Returns:
        Dict mapping file_path -> has_test (bool)
    """
    test_files = find_test_files(repo_root)
    test_file_names = {f.stem for f in test_files}
    test_file_names_normalized = {
        f.stem.replace("test_", "").replace("_test", "") for f in test_files
    }

    coverage = {}
    for file_path in changed_files:
        file_name = Path(file_path).stem
        has_test = (
            f"test_{file_name}" in test_file_names
            or f"{file_name}_test" in test_file_names
            or file_name in test_file_names_normalized
        )
        coverage[file_path] = has_test

    return coverage


def format_coverage_context(coverage: dict[str, bool]) -> str:
    """Format coverage info for agent prompts."""
    untested = [f for f, covered in coverage.items() if not covered]
    tested = [f for f, covered in coverage.items() if covered]

    parts = []
    if untested:
        parts.append(f"⚠️ Untested files ({len(untested)}): {', '.join(untested)}")
    if tested:
        parts.append(f"✅ Tested files ({len(tested)}): {', '.join(tested)}")

    return "\n".join(parts) if parts else ""
