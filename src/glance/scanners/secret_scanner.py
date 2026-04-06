"""Secret Scanner - Regex-based detection of high-entropy strings.

Detects hardcoded secrets, API keys, passwords, and tokens before
sending code to the LLM for review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Pattern


@dataclass
class SecretFinding:
    """Represents a detected secret in code."""

    file_path: str
    line_number: int
    secret_type: str
    matched_text: str
    entropy_score: float = 0.0


@dataclass
class SecretScanResult:
    """Result of a secret scan operation."""

    has_secrets: bool = False
    findings: list[SecretFinding] = field(default_factory=list)
    error: str | None = None


class SecretScanner:
    """Regex-based scanner for hardcoded secrets and credentials.

    Detects common patterns:
    - API keys (AWS, GitHub, generic)
    - Passwords in assignments
    - Private keys
    - Tokens (Bearer, JWT patterns)
    - Connection strings
    """

    # Secret patterns with their types
    PATTERNS: dict[str, Pattern] = {
        # AWS Access Key ID
        "aws_access_key": re.compile(
            r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"
        ),
        # AWS Secret Access Key
        "aws_secret_key": re.compile(
            r"(?:aws_secret_access_key|aws_secret_key|secret_access_key)\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}['\"]?",
            re.IGNORECASE,
        ),
        # GitHub Token
        "github_token": re.compile(
            r"(?:ghp_|gho_|ghu_|ghs_|ghr_)[a-zA-Z0-9_]{36,}"
        ),
        # Generic API Key patterns
        "api_key": re.compile(
            r"(?:api[_-]?key|apikey)\s*[=:]\s*['\"]?[a-zA-Z0-9_\-]{20,}['\"]?",
            re.IGNORECASE,
        ),
        # Password in assignment
        "password": re.compile(
            r"(?:password|passwd|pwd)\s*[=:]\s*['\"]?[^'\"\s]{8,}['\"]?",
            re.IGNORECASE,
        ),
        # Bearer Token
        "bearer_token": re.compile(
            r"Bearer\s+[a-zA-Z0-9_\-\.]+",
            re.IGNORECASE,
        ),
        # JWT Token
        "jwt_token": re.compile(
            r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*"
        ),
        # Private Key header
        "private_key": re.compile(
            r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----",
            re.IGNORECASE,
        ),
        # Connection string with credentials
        "connection_string": re.compile(
            r"(?:mysql|postgres|mongodb|redis)://[^\s:]+:[^\s@]+@[^\s]+",
            re.IGNORECASE,
        ),
        # Generic secret assignment
        "generic_secret": re.compile(
            r"(?:secret|token|credential|auth)[_-]?(?:key|token)?\s*[=:]\s*['\"]?[^'\"\s]{16,}['\"]?",
            re.IGNORECASE,
        ),
        # Slack Token
        "slack_token": re.compile(
            r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}"
        ),
        # Google API Key
        "google_api_key": re.compile(
            r"AIza[0-9A-Za-z\-_]{35}"
        ),
    }

    # Patterns that are likely false positives
    FALSE_POSITIVE_PATTERNS: list[Pattern] = [
        re.compile(r"^\$\{"),  # Environment variable placeholders
        re.compile(r"^process\.env\."),  # Node.js env references
        re.compile(r"^os\.environ"),  # Python env references
        re.compile(r"^ENV\[", re.IGNORECASE),  # Docker env references
        re.compile(r"\$\{[A-Z_]+\}"),  # Variable placeholders
        re.compile(r"^\*\*"),  # Wildcards
        re.compile(r"^your[_-]?(?:api[_-]?key|password|secret)", re.IGNORECASE),  # Examples
        re.compile(r"^<[^>]+>$"),  # Placeholder markers
    ]

    def __init__(self, min_entropy: float = 3.5):
        """Initialize the secret scanner.

        Args:
            min_entropy: Minimum Shannon entropy for high-entropy string detection.
        """
        self.min_entropy = min_entropy

    def scan_file(self, file_path: str | Path) -> SecretScanResult:
        """Scan a single file for secrets.

        Args:
            file_path: Path to the file to scan.

        Returns:
            SecretScanResult with any findings.
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return SecretScanResult(error=f"File not found: {file_path}")

            content = path.read_text(encoding="utf-8", errors="ignore")
            return self.scan_content(content, str(file_path))

        except Exception as e:
            return SecretScanResult(error=f"Error scanning file: {e}")

    def scan_content(self, content: str, file_path: str = "<unknown>") -> SecretScanResult:
        """Scan content string for secrets.

        Args:
            content: The content to scan.
            file_path: Optional file path for reporting.

        Returns:
            SecretScanResult with any findings.
        """
        findings: list[SecretFinding] = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            # Skip comments (basic heuristic)
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                # But still scan for private keys in comments
                if "-----BEGIN" in line:
                    findings.append(SecretFinding(
                        file_path=file_path,
                        line_number=line_num,
                        secret_type="private_key",
                        matched_text=line[:50] + "...",
                    ))
                continue

            # Check each pattern
            for secret_type, pattern in self.PATTERNS.items():
                matches = pattern.finditer(line)
                for match in matches:
                    matched_text = match.group()

                    # Check for false positives
                    if self._is_false_positive(matched_text, line):
                        continue

                    # Calculate entropy for validation
                    entropy = self._calculate_entropy(matched_text)

                    findings.append(SecretFinding(
                        file_path=file_path,
                        line_number=line_num,
                        secret_type=secret_type,
                        matched_text=self._mask_secret(matched_text),
                        entropy_score=entropy,
                    ))

        return SecretScanResult(
            has_secrets=len(findings) > 0,
            findings=findings,
        )

    def scan_diff(self, diff_content: str) -> SecretScanResult:
        """Scan a git diff for secrets.

        Only scans added lines (lines starting with +).

        Args:
            diff_content: Git diff content.

        Returns:
            SecretScanResult with any findings.
        """
        findings: list[SecretFinding] = []
        lines = diff_content.split("\n")

        current_file = "<unknown>"

        for line_num, line in enumerate(lines, start=1):
            # Track current file from diff headers
            if line.startswith("+++ b/"):
                current_file = line[6:].strip()
                continue

            # Only scan added lines (not removed or context)
            if not line.startswith("+") or line.startswith("+++"):
                continue

            # Remove the + prefix for scanning
            actual_line = line[1:]

            # Check each pattern
            for secret_type, pattern in self.PATTERNS.items():
                matches = pattern.finditer(actual_line)
                for match in matches:
                    matched_text = match.group()

                    if self._is_false_positive(matched_text, actual_line):
                        continue

                    entropy = self._calculate_entropy(matched_text)

                    findings.append(SecretFinding(
                        file_path=current_file,
                        line_number=line_num,
                        secret_type=secret_type,
                        matched_text=self._mask_secret(matched_text),
                        entropy_score=entropy,
                    ))

        return SecretScanResult(
            has_secrets=len(findings) > 0,
            findings=findings,
        )

    def _is_false_positive(self, matched_text: str, line_context: str) -> bool:
        """Check if a match is likely a false positive."""
        for pattern in self.FALSE_POSITIVE_PATTERNS:
            if pattern.search(matched_text) or pattern.search(line_context):
                return True

        # Check if it's a placeholder pattern
        placeholders = [
            "xxx", "yyy", "zzz",
            "your_", "my_", "example",
            "placeholder", "template",
            "changeme", "insert_here",
        ]
        matched_lower = matched_text.lower()
        for placeholder in placeholders:
            if placeholder in matched_lower:
                return True

        return False

    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of a string."""
        import math
        from collections import Counter

        if not text:
            return 0.0

        counts = Counter(text)
        probs = [count / len(text) for count in counts.values()]
        return -sum(p * math.log2(p) for p in probs)

    def _mask_secret(self, secret: str) -> str:
        """Mask a secret for safe display."""
        if len(secret) <= 8:
            return "*" * len(secret)
        return secret[:4] + "*" * (len(secret) - 8) + secret[-4:]


def scan_for_secrets(content: str) -> SecretScanResult:
    """Convenience function to scan content for secrets.

    Args:
        content: Content to scan.

    Returns:
        SecretScanResult with any findings.
    """
    scanner = SecretScanner()
    return scanner.scan_content(content)
