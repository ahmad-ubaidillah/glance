"""Review History - Track previous findings across PRs.

Stores and retrieves past review findings to:
- Detect recurring issues (same pattern flagged before)
- Track if critical issues were fixed or ignored
- Provide context: "This was flagged 3 times before"
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("glance.history")


@dataclass
class HistoricalFinding:
    """A finding from a previous review."""

    file_path: str
    line_number: int | None
    message: str
    severity: str
    category: str
    suggestion: str
    pr_number: int
    commit_sha: str
    status: str = "open"  # open, fixed, ignored


@dataclass
class ReviewHistory:
    """Collection of historical findings."""

    findings: list[HistoricalFinding] = field(default_factory=list)
    total_reviews: int = 0

    def get_recurring(self, file_path: str, message_keywords: list[str]) -> list[HistoricalFinding]:
        """Find recurring issues matching file and keywords."""
        matches = []
        for f in self.findings:
            if f.file_path != file_path:
                continue
            msg_lower = f.message.lower()
            if any(kw.lower() in msg_lower for kw in message_keywords):
                matches.append(f)
        return matches

    def get_unfixed_criticals(self, file_path: str) -> list[HistoricalFinding]:
        """Get critical issues that were never fixed."""
        return [
            f
            for f in self.findings
            if f.file_path == file_path
            and f.severity == "critical"
            and f.status in ("open", "ignored")
        ]

    def count_occurrences(self, file_path: str, message_keywords: list[str]) -> int:
        """Count how many times a similar issue was flagged."""
        return len(self.get_recurring(file_path, message_keywords))


def load_history(repo_root: Path) -> ReviewHistory:
    """Load review history from .glance/history.json."""
    history_file = repo_root / ".glance" / "history.json"
    if not history_file.exists():
        return ReviewHistory()

    try:
        with open(history_file) as f:
            data = json.load(f)
        findings = [HistoricalFinding(**f) for f in data.get("findings", [])]
        return ReviewHistory(findings=findings, total_reviews=data.get("total_reviews", 0))
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to load review history: {e}")
        return ReviewHistory()


def save_history(
    repo_root: Path, history: ReviewHistory, new_findings: list, pr_number: int, commit_sha: str
) -> None:
    """Save review history to .glance/history.json."""
    history_dir = repo_root / ".glance"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_file = history_dir / "history.json"

    # Add new findings to history
    for finding in new_findings:
        history.findings.append(
            HistoricalFinding(
                file_path=getattr(finding, "file_path", "unknown"),
                line_number=getattr(finding, "line_number", None),
                message=getattr(finding, "message", ""),
                severity=getattr(finding, "severity", "info"),
                category=getattr(finding, "category", "unknown"),
                suggestion=getattr(finding, "suggestion", ""),
                pr_number=pr_number,
                commit_sha=commit_sha,
                status="open",
            )
        )

    history.total_reviews += 1

    data = {
        "total_reviews": history.total_reviews,
        "findings": [
            {
                "file_path": f.file_path,
                "line_number": f.line_number,
                "message": f.message,
                "severity": f.severity,
                "category": f.category,
                "suggestion": f.suggestion,
                "pr_number": f.pr_number,
                "commit_sha": f.commit_sha,
                "status": f.status,
            }
            for f in history.findings[-500:]  # Keep last 500 findings
        ],
    }

    with open(history_file, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(
        f"Saved review history ({len(history.findings)} findings, {history.total_reviews} reviews)"
    )


def format_history_context(history: ReviewHistory, file_path: str, message: str) -> str:
    """Format history context for agent prompts."""
    keywords = message.split()[:5]  # Use first 5 words as keywords
    count = history.count_occurrences(file_path, keywords)
    unfixed = history.get_unfixed_criticals(file_path)

    context_parts = []
    if count > 1:
        context_parts.append(f"⚠️ This issue has been flagged {count} times before in {file_path}")
    if unfixed:
        context_parts.append(
            f"🔴 {len(unfixed)} critical issue(s) in this file were never addressed"
        )

    return "\n".join(context_parts) if context_parts else ""
