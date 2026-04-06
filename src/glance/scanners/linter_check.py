"""Linter Check - Validates linter status before running review.

Ensures code passes static analysis before AI review begins.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class LinterResult:
    """Result of a linter check."""

    passed: bool
    linter_name: str = "unknown"
    output: str = ""
    error_count: int = 0
    warning_count: int = 0
    error: str | None = None


class LinterChecker:
    """Runs and validates linter status for code review.

    Supports multiple linters:
    - ESLint (JavaScript/TypeScript)
    - Pylint/Flake8 (Python)
    - Cargo Check (Rust)
    - Zig Build Check (Zig)
    """

    LINTER_COMMANDS: dict[str, list[str]] = {
        "eslint": ["eslint", "--format", "compact", "."],
        "pylint": ["pylint", "--output-format=text", "."],
        "flake8": ["flake8", "."],
        "cargo": ["cargo", "check", "--message-format=short"],
        "zig": ["zig", "build", "--summary", "short"],
        "golangci-lint": ["golangci-lint", "run", "--out-format=line-number"],
    }

    # File extensions mapped to default linters
    EXTENSION_LINTER_MAP: dict[str, str] = {
        ".js": "eslint",
        ".jsx": "eslint",
        ".ts": "eslint",
        ".tsx": "eslint",
        ".py": "flake8",
        ".rs": "cargo",
        ".zig": "zig",
        ".go": "golangci-lint",
    }

    def __init__(self, workdir: str | Path = "."):
        """Initialize the linter checker.

        Args:
            workdir: Working directory to run linters in.
        """
        self.workdir = Path(workdir)

    def detect_linter(self) -> str | None:
        """Auto-detect the appropriate linter based on project files.

        Returns:
            Name of detected linter or None.
        """
        # Check for config files
        config_priority = [
            ("eslint", [".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yaml"]),
            ("cargo", ["Cargo.toml"]),
            ("zig", ["build.zig"]),
            ("flake8", [".flake8", "setup.cfg", "tox.ini"]),
            ("pylint", ["pylintrc", ".pylintrc"]),
            ("golangci-lint", [".golangci.yml", ".golangci.yaml"]),
        ]

        for linter, config_files in config_priority:
            for config in config_files:
                if (self.workdir / config).exists():
                    return linter

        # Fall back to extension detection
        for ext, linter in self.EXTENSION_LINTER_MAP.items():
            if list(self.workdir.glob(f"**/*{ext}"))[:5]:
                return linter

        return None

    def run_linter(
        self,
        linter: str | None = None,
        command_override: list[str] | None = None,
    ) -> LinterResult:
        """Run the specified or auto-detected linter.

        Args:
            linter: Name of linter to run, or None to auto-detect.
            command_override: Custom command to run instead of default.

        Returns:
            LinterResult with pass/fail status and output.
        """
        if command_override:
            cmd = command_override
            linter_name = "custom"
        elif linter:
            cmd = self.LINTER_COMMANDS.get(linter)
            linter_name = linter
            if not cmd:
                return LinterResult(
                    passed=False,
                    linter_name=linter,
                    error=f"Unknown linter: {linter}",
                )
        else:
            detected = self.detect_linter()
            if not detected:
                return LinterResult(
                    passed=True,  # No linter detected, skip check
                    linter_name="none",
                    output="No linter detected, skipping check",
                )
            cmd = self.LINTER_COMMANDS[detected]
            linter_name = detected

        try:
            result = subprocess.run(
                cmd,
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            output = result.stdout + result.stderr
            error_count = self._count_errors(output, linter_name)
            warning_count = self._count_warnings(output, linter_name)

            return LinterResult(
                passed=result.returncode == 0,
                linter_name=linter_name,
                output=output[:10000],  # Truncate very long output
                error_count=error_count,
                warning_count=warning_count,
            )

        except subprocess.TimeoutExpired:
            return LinterResult(
                passed=False,
                linter_name=linter_name,
                error="Linter timed out after 5 minutes",
            )
        except FileNotFoundError:
            return LinterResult(
                passed=False,
                linter_name=linter_name,
                error=f"Linter not found: {cmd[0]}",
            )
        except Exception as e:
            return LinterResult(
                passed=False,
                linter_name=linter_name,
                error=f"Error running linter: {e}",
            )

    def check_required(self, linter: str | None = None) -> LinterResult:
        """Run linter and require pass before proceeding.

        This is the main entry point for the pre-execution phase.

        Args:
            linter: Optional specific linter to use.

        Returns:
            LinterResult - should check .passed before proceeding.
        """
        return self.run_linter(linter)

    def _count_errors(self, output: str, linter: str) -> int:
        """Count errors in linter output."""
        import re

        patterns = {
            "eslint": r"\d+ errors?",
            "flake8": r"^.*:\d+:\d+: [EF]\d+",
            "pylint": r"^[EF]:\d+:",
            "cargo": r"error\[E\d+\]",
            "zig": r"error: ",
            "golangci-lint": r"Err\d+",
        }

        pattern = patterns.get(linter, r"error:")
        matches = re.findall(pattern, output, re.MULTILINE)
        return len(matches)

    def _count_warnings(self, output: str, linter: str) -> int:
        """Count warnings in linter output."""
        import re

        patterns = {
            "eslint": r"\d+ warnings?",
            "flake8": r"^.*:\d+:\d+: [W]\d+",
            "pylint": r"^[W]:\d+:",
            "cargo": r"warning: ",
            "zig": r"warning: ",
            "golangci-lint": r"Warn\d+",
        }

        pattern = patterns.get(linter, r"warning:")
        matches = re.findall(pattern, output, re.MULTILINE | re.IGNORECASE)
        return len(matches)


def check_linter(workdir: str = ".") -> LinterResult:
    """Convenience function to run linter check.

    Args:
        workdir: Working directory.

    Returns:
        LinterResult with pass/fail status.
    """
    checker = LinterChecker(workdir)
    return checker.check_required()
