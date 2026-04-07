"""Glance Memory System - Persistent learning across PRs.

Stores and retrieves:
- Developer behavior patterns (common mistakes, fix quality)
- Issue patterns across branches (recurring problems)
- Lessons learned from previous fixes
- Issue severity/priority calibration
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("glance.memory")


@dataclass
class DeveloperProfile:
    """Tracks a developer's review patterns."""

    username: str
    total_prs_reviewed: int = 0
    common_issue_types: dict[str, int] = field(default_factory=dict)
    avg_fix_quality: float = 0.0  # 0-1, how well they address findings
    ignored_criticals: int = 0
    recurring_mistakes: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    last_review_date: str = ""

    def record_issue(self, category: str, severity: str) -> None:
        key = f"{category}_{severity}"
        self.common_issue_types[key] = self.common_issue_types.get(key, 0) + 1

    def get_top_issues(self, n: int = 5) -> list[tuple[str, int]]:
        return sorted(self.common_issue_types.items(), key=lambda x: x[1], reverse=True)[:n]


@dataclass
class IssuePattern:
    """A recurring issue pattern across the codebase."""

    pattern_id: str
    description: str
    category: str
    severity: str
    files_affected: list[str] = field(default_factory=list)
    occurrence_count: int = 0
    first_seen: str = ""
    last_seen: str = ""
    branches_seen: list[str] = field(default_factory=list)
    typical_fix: str = ""  # How it's usually fixed
    fix_success_rate: float = 0.0  # How often the suggested fix works

    def record_occurrence(self, file_path: str, branch: str, date: str) -> None:
        if file_path not in self.files_affected:
            self.files_affected.append(file_path)
        if branch not in self.branches_seen:
            self.branches_seen.append(branch)
        self.occurrence_count += 1
        self.last_seen = date


@dataclass
class LessonLearned:
    """A lesson extracted from a fix."""

    lesson_id: str
    original_issue: str
    fix_applied: str
    file_path: str
    category: str
    effectiveness: str = "unknown"  # effective, partial, ineffective
    date_learned: str = ""
    source_pr: int = 0
    applicable_patterns: list[str] = field(default_factory=list)


@dataclass
class GlanceMemory:
    """Complete memory store for Glance."""

    developers: dict[str, DeveloperProfile] = field(default_factory=dict)
    issue_patterns: dict[str, IssuePattern] = field(default_factory=dict)
    lessons_learned: list[LessonLearned] = field(default_factory=list)
    total_reviews: int = 0
    last_updated: str = ""

    def get_developer(self, username: str) -> DeveloperProfile:
        if username not in self.developers:
            self.developers[username] = DeveloperProfile(username=username)
        return self.developers[username]

    def find_matching_pattern(self, file_path: str, message: str) -> list[IssuePattern]:
        """Find issue patterns that match this file and message."""
        matches = []
        msg_lower = message.lower()
        for pattern in self.issue_patterns.values():
            if any(f in pattern.files_affected for f in [file_path]):
                desc_lower = pattern.description.lower()
                if any(word in desc_lower for word in msg_lower.split()[:5]):
                    matches.append(pattern)
        return matches

    def get_relevant_lessons(self, file_path: str, category: str) -> list[LessonLearned]:
        """Get lessons relevant to this file and category."""
        return [
            l for l in self.lessons_learned if l.file_path == file_path or l.category == category
        ]

    def get_developer_insights(self, username: str) -> str:
        """Get insights about a developer's patterns."""
        dev = self.developers.get(username)
        if not dev:
            return ""

        parts = []
        if dev.recurring_mistakes:
            parts.append(f"Recurring issues: {', '.join(dev.recurring_mistakes)}")
        if dev.strengths:
            parts.append(f"Strengths: {', '.join(dev.strengths)}")
        if dev.ignored_criticals > 2:
            parts.append(f"Has ignored {dev.ignored_criticals} critical issues before")

        return "\n".join(parts)

    def get_repo_insights(self) -> str:
        """Get overall repo insights."""
        parts = []
        if self.issue_patterns:
            recurring = [p for p in self.issue_patterns.values() if p.occurrence_count >= 3]
            if recurring:
                parts.append(f"Recurring patterns ({len(recurring)} issues appear 3+ times):")
                for p in recurring:
                    parts.append(
                        f"  - {p.description} (seen {p.occurrence_count} times across {len(p.branches_seen)} branches)"
                    )

        if self.lessons_learned:
            effective = [l for l in self.lessons_learned if l.effectiveness == "effective"]
            if effective:
                parts.append(
                    f"Learned {len(effective)} effective fix patterns from previous reviews"
                )

        return "\n".join(parts)


def load_memory(repo_root: Path) -> GlanceMemory:
    """Load memory from .glance/memory.json."""
    memory_file = repo_root / ".glance" / "memory.json"
    if not memory_file.exists():
        return GlanceMemory()

    try:
        with open(memory_file) as f:
            data = json.load(f)

        memory = GlanceMemory(
            total_reviews=data.get("total_reviews", 0),
            last_updated=data.get("last_updated", ""),
        )

        for username, dev_data in data.get("developers", {}).items():
            memory.developers[username] = DeveloperProfile(**dev_data)

        for pid, pat_data in data.get("issue_patterns", {}).items():
            memory.issue_patterns[pid] = IssuePattern(**pat_data)

        for lesson_data in data.get("lessons_learned", []):
            memory.lessons_learned.append(LessonLearned(**lesson_data))

        return memory

    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to load memory: {e}")
        return GlanceMemory()


def save_memory(repo_root: Path, memory: GlanceMemory) -> None:
    """Save memory to .glance/memory.json."""
    memory_dir = repo_root / ".glance"
    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_file = memory_dir / "memory.json"

    memory.last_updated = datetime.now().isoformat()

    for dev in memory.developers.values():
        if not dev.recurring_mistakes and dev.common_issue_types:
            threshold = 3
            dev.recurring_mistakes = [
                cat for cat, count in dev.common_issue_types.items() if count >= threshold
            ]

        if not dev.strengths and dev.total_prs_reviewed >= 5:
            total_issues = sum(dev.common_issue_types.values())
            if total_issues == 0:
                dev.strengths = ["Consistently clean code across multiple PRs"]
            elif dev.avg_fix_quality >= 0.8:
                dev.strengths = ["Quick to address review feedback effectively"]

    data = {
        "total_reviews": memory.total_reviews,
        "last_updated": memory.last_updated,
        "developers": {
            username: {
                "username": dev.username,
                "total_prs_reviewed": dev.total_prs_reviewed,
                "common_issue_types": dev.common_issue_types,
                "avg_fix_quality": dev.avg_fix_quality,
                "ignored_criticals": dev.ignored_criticals,
                "recurring_mistakes": dev.recurring_mistakes,
                "strengths": dev.strengths,
                "last_review_date": dev.last_review_date,
            }
            for username, dev in memory.developers.items()
        },
        "issue_patterns": {
            pid: {
                "pattern_id": p.pattern_id,
                "description": p.description,
                "category": p.category,
                "severity": p.severity,
                "files_affected": p.files_affected,
                "occurrence_count": p.occurrence_count,
                "first_seen": p.first_seen,
                "last_seen": p.last_seen,
                "branches_seen": p.branches_seen,
                "typical_fix": p.typical_fix,
                "fix_success_rate": p.fix_success_rate,
            }
            for pid, p in memory.issue_patterns.items()
        },
        "lessons_learned": [
            {
                "lesson_id": l.lesson_id,
                "original_issue": l.original_issue,
                "fix_applied": l.fix_applied,
                "file_path": l.file_path,
                "category": l.category,
                "effectiveness": l.effectiveness,
                "date_learned": l.date_learned,
                "source_pr": l.source_pr,
                "applicable_patterns": l.applicable_patterns,
            }
            for l in memory.lessons_learned[-200:]
        ],
    }

    with open(memory_file, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(
        f"Saved memory ({len(memory.developers)} devs, "
        f"{len(memory.issue_patterns)} patterns, "
        f"{len(memory.lessons_learned)} lessons)"
    )


def format_memory_context(memory: GlanceMemory, author: str, file_paths: list[str]) -> str:
    """Format memory context for agent prompts."""
    parts = []

    # Developer insights
    dev_insights = memory.get_developer_insights(author)
    if dev_insights:
        parts.append(f"### Developer Insights ({author})\n{dev_insights}")

    # Repo insights
    repo_insights = memory.get_repo_insights()
    if repo_insights:
        parts.append(f"### Repository Patterns\n{repo_insights}")

    # Relevant lessons
    all_lessons = []
    for fp in file_paths:
        all_lessons.extend(memory.get_relevant_lessons(fp, ""))
    if all_lessons:
        parts.append("### Previous Fixes in These Files")
        for l in all_lessons[:5]:
            parts.append(f"- {l.original_issue} → Fixed with: {l.fix_applied}")

    return "\n\n".join(parts) if parts else ""
