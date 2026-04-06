"""Review Statistics Dashboard - Generate stats from Glance data.

Generates:
- Issues per developer over time
- Most common issue types
- Fix rate (how many issues actually get fixed)
- Review trends
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("glance.stats")


@dataclass
class ReviewStats:
    """Statistics from all reviews."""

    total_reviews: int = 0
    total_findings: int = 0
    total_fixed: int = 0
    total_ignored: int = 0
    issues_by_category: dict[str, int] = field(default_factory=dict)
    issues_by_severity: dict[str, int] = field(default_factory=dict)
    issues_by_developer: dict[str, int] = field(default_factory=dict)
    fix_rate: float = 0.0
    avg_findings_per_review: float = 0.0

    def to_markdown(self) -> str:
        """Generate markdown dashboard."""
        lines = ["## 📊 Glance Review Dashboard\n"]
        lines.append(f"**Total Reviews:** {self.total_reviews}")
        lines.append(f"**Total Findings:** {self.total_findings}")
        lines.append(f"**Fix Rate:** {self.fix_rate:.1%}")
        lines.append(f"**Avg Findings/Review:** {self.avg_findings_per_review:.1f}")

        if self.issues_by_severity:
            lines.append("\n### By Severity")
            for sev, count in sorted(self.issues_by_severity.items()):
                lines.append(f"- {sev}: {count}")

        if self.issues_by_category:
            lines.append("\n### By Category")
            for cat, count in sorted(
                self.issues_by_category.items(), key=lambda x: x[1], reverse=True
            )[:10]:
                lines.append(f"- {cat}: {count}")

        if self.issues_by_developer:
            lines.append("\n### By Developer")
            for dev, count in sorted(
                self.issues_by_developer.items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"- {dev}: {count} findings")

        return "\n".join(lines)


def generate_stats(repo_root: Path) -> ReviewStats:
    """Generate statistics from all Glance data files."""
    stats = ReviewStats()

    # Load memory
    memory_file = repo_root / ".glance" / "memory.json"
    if memory_file.exists():
        try:
            with open(memory_file) as f:
                data = json.load(f)
            stats.total_reviews = data.get("total_reviews", 0)

            for username, dev_data in data.get("developers", {}).items():
                total = dev_data.get("total_prs_reviewed", 0)
                stats.issues_by_developer[username] = sum(
                    dev_data.get("common_issue_types", {}).values()
                )

                for issue_key, count in dev_data.get("common_issue_types", {}).items():
                    parts = issue_key.split("_", 1)
                    if len(parts) == 2:
                        cat, sev = parts
                        stats.issues_by_category[cat] = stats.issues_by_category.get(cat, 0) + count
                        stats.issues_by_severity[sev] = stats.issues_by_severity.get(sev, 0) + count
        except Exception as e:
            logger.warning(f"Failed to load memory for stats: {e}")

    # Load history
    history_file = repo_root / ".glance" / "history.json"
    if history_file.exists():
        try:
            with open(history_file) as f:
                data = json.load(f)
            findings = data.get("findings", [])
            stats.total_findings = len(findings)
            stats.total_fixed = sum(1 for f in findings if f.get("status") == "fixed")
            stats.total_ignored = sum(1 for f in findings if f.get("status") == "ignored")

            total_tracked = stats.total_fixed + stats.total_ignored
            if total_tracked > 0:
                stats.fix_rate = stats.total_fixed / total_tracked
        except Exception as e:
            logger.warning(f"Failed to load history for stats: {e}")

    if stats.total_reviews > 0:
        stats.avg_findings_per_review = stats.total_findings / stats.total_reviews

    return stats
