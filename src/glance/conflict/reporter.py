"""Conflict Reporter - Generate formatted GitHub comments."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glance.conflict.analyzer import ConflictAnalysis


class ConflictReporter:
    def __init__(self, max_code_lines: int = 10):
        self.max_code_lines = max_code_lines

    def generate_report(
        self,
        analyses: list["ConflictAnalysis"],
        total_conflicts: int,
        repo_url: str = "",
    ) -> str:
        if not analyses:
            return self._no_conflicts_report()

        critical = [a for a in analyses if a.risk_level.value == "critical"]
        low_risk = [a for a in analyses if a.risk_level.value == "low"]

        lines = []

        lines.append("# ⚠️ MERGE CONFLICT REPORT")
        lines.append(f"Detected **{total_conflicts} conflicts** in this pull request.\n")

        if critical:
            lines.append("## 🚨 CRITICAL - Requires Decision")
            lines.append("These conflicts have significant differences. Please choose:\n")
            for a in critical:
                lines.extend(self._format_critical_conflict(a))

        if low_risk:
            lines.append("\n## ✅ LOW RISK - Auto-resolvable")
            lines.append(f"**{len(low_risk)} conflicts** can be auto-resolved:\n")
            for a in low_risk:
                lines.extend(self._format_low_risk_conflict(a))

        lines.append("\n---\n")
        lines.append(self._action_section(len(critical)))

        return "\n".join(lines)

    def _format_critical_conflict(self, analysis: "ConflictAnalysis") -> list[str]:
        lines = []

        choice_label = {
            "our": "HEAD (main)",
            "their": "Feature Branch",
            "hybrid": "Hybrid",
        }
        suggested = choice_label.get(analysis.suggested_choice, "our")

        lines.append(f"### [{analysis.conflict_id}] {analysis.file_path}:{analysis.start_line}")
        lines.append("")
        lines.append("| Version | Content |")
        lines.append("|---------|---------|")
        lines.append(
            f"| **HEAD (main)** | ````code\n{self._truncate(analysis.our_version)}\n```` |"
        )
        lines.append(f"| **Feature** | ````code\n{self._truncate(analysis.their_version)}\n```` |")
        lines.append("")
        lines.append(f"**💡 Suggested: {suggested}**")
        lines.append(f"> {analysis.reasoning}")
        lines.append("")
        lines.append(
            f"**Reply:** `{analysis.conflict_id}A` (HEAD) | `{analysis.conflict_id}B` (Feature)"
        )

        if analysis.suggested_choice == "hybrid" and analysis.hybrid_version:
            lines.append(
                f"| `{analysis.conflict_id}C` (Hybrid) | ````code\n{self._truncate(analysis.hybrid_version)}\n```` |"
            )

        lines.append("")
        return lines

    def _format_low_risk_conflict(self, analysis: "ConflictAnalysis") -> list[str]:
        return [
            f"- **{analysis.file_path}** (line {analysis.start_line}): "
            f"{analysis.reasoning} → Auto-keep HEAD\n"
        ]

    def _action_section(self, critical_count: int) -> str:
        lines = [
            "## 📋 HOW TO RESOLVE\n",
            "Reply to this comment with your choices:\n",
            "```",
            "# For individual conflicts:",
            f"{1}A   # Use HEAD for conflict #1",
            f"{1}B   # Use Feature for conflict #1",
            "",
            "# For all critical conflicts:",
            "allA   # Use HEAD for ALL critical conflicts",
            "allB   # Use Feature for ALL critical conflicts",
            "",
            "# Auto-resolve low-risk conflicts:",
            "auto   # Apply auto-resolution",
            "```\n",
            "Glance will apply your choices automatically.",
        ]
        return "\n".join(lines)

    def _no_conflicts_report(self) -> str:
        return "✅ **No merge conflicts detected.** Your branch is ready to merge!"

    def _truncate(self, code: str, max_lines: int | None = None) -> str:
        max_lines = max_lines or self.max_code_lines
        lines = code.splitlines()
        if len(lines) <= max_lines:
            return code
        return "\n".join(lines[:max_lines]) + "\n... (truncated)"

    def generate_summary(self, analyses: list["ConflictAnalysis"]) -> str:
        total = len(analyses)
        critical = sum(1 for a in analyses if a.risk_level.value == "critical")
        low = total - critical

        return (
            f"⚠️ **{total} merge conflicts detected**\n"
            f"- 🚨 {critical} critical (need decision)\n"
            f"- ✅ {low} low-risk (auto-resolvable)"
        )
