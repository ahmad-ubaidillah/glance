"""PR Response Handler - Track if issues are fixed across PR iterations.

When a developer pushes new commits after Glance's review:
1. Compare new diff with previous findings
2. Check if issues were addressed
3. Update memory with fix status
4. Generate follow-up review if needed
"""

from __future__ import annotations

import hashlib

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("glance.response")


def _stable_issue_id(file_path: str, message: str, category: str) -> str:
    """Generate a stable issue ID based on content, not line numbers.

    Line numbers shift between commits, and LLMs may rephrase messages.
    Using a hash of file_path + first 3 words + category gives us stable identity.
    """
    first_words = " ".join(message.split()[:3])
    raw = f"{file_path}:{first_words}:{category}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class TrackedIssue:
    """An issue being tracked across PR iterations."""

    issue_id: str
    file_path: str
    line_number: int | None
    message: str
    severity: str
    category: str
    pr_number: int
    commit_sha: str
    status: str = "open"  # open, fixed, ignored, still_present
    fix_commit: str | None = None
    iterations: int = 0


@dataclass
class PRResponseTracker:
    """Tracks PR responses and issue resolution."""

    tracked_issues: dict[str, TrackedIssue] = field(default_factory=dict)
    total_follow_ups: int = 0

    def record_issues(self, findings: list, pr_number: int, commit_sha: str) -> list[str]:
        """Record new issues to track."""
        new_ids = []
        for f in findings:
            issue_id = _stable_issue_id(f.file_path, f.message, f.category)
            if issue_id not in self.tracked_issues:
                self.tracked_issues[issue_id] = TrackedIssue(
                    issue_id=issue_id,
                    file_path=f.file_path,
                    line_number=getattr(f, "line_number", None),
                    message=f.message,
                    severity=f.severity,
                    category=f.category,
                    pr_number=pr_number,
                    commit_sha=commit_sha,
                )
                new_ids.append(issue_id)
        return new_ids

    def check_resolution(self, findings: list, commit_sha: str) -> dict[str, list[TrackedIssue]]:
        """Check which issues are fixed vs still present."""
        result = {"fixed": [], "still_present": [], "new": []}

        current_issues = set()
        for f in findings:
            issue_id = _stable_issue_id(f.file_path, f.message, f.category)
            current_issues.add(issue_id)

        for issue_id, issue in self.tracked_issues.items():
            if issue.status in ("fixed", "ignored"):
                continue

            if issue_id in current_issues:
                issue.iterations += 1
                if issue.iterations >= 2:
                    result["still_present"].append(issue)
            else:
                issue.status = "fixed"
                issue.fix_commit = commit_sha
                result["fixed"].append(issue)

        # Find new issues
        for f in findings:
            issue_id = _stable_issue_id(f.file_path, f.message, f.category)
            if issue_id not in self.tracked_issues:
                result["new"].append(f)

        return result

    def get_summary(self) -> str:
        """Get summary of tracked issues."""
        open_count = sum(1 for i in self.tracked_issues.values() if i.status == "open")
        fixed_count = sum(1 for i in self.tracked_issues.values() if i.status == "fixed")
        ignored_count = sum(1 for i in self.tracked_issues.values() if i.status == "ignored")
        recurring = [i for i in self.tracked_issues.values() if i.iterations >= 2]

        parts = []
        if fixed_count:
            parts.append(f"✅ {fixed_count} issues fixed")
        if open_count:
            parts.append(f"🔴 {open_count} issues still open")
        if ignored_count:
            parts.append(f"⚪ {ignored_count} issues ignored")
        if recurring:
            parts.append(f"⚠️ {len(recurring)} recurring issues (appeared 2+ times)")

        return "\n".join(parts) if parts else ""
