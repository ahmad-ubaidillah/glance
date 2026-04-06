"""Custom Team Rules - Allow teams to define custom review rules.

Teams can add rules via .glance/rules.yaml:
- Always check for specific patterns
- Ignore certain patterns (intentional)
- Escalate specific issues to critical
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("glance.rules")


@dataclass
class TeamRule:
    """A custom team rule."""

    rule_id: str
    description: str
    action: str  # "check", "ignore", "escalate"
    pattern: str
    severity: str = "warning"  # default severity if escalated
    files: list[str] = field(default_factory=list)  # apply to specific files


@dataclass
class TeamRules:
    """Collection of team rules."""

    rules: list[TeamRule] = field(default_factory=list)

    def get_checks(self) -> list[TeamRule]:
        """Get rules that require additional checks."""
        return [r for r in self.rules if r.action == "check"]

    def get_ignores(self) -> list[TeamRule]:
        """Get patterns to ignore."""
        return [r for r in self.rules if r.action == "ignore"]

    def get_escalations(self) -> list[TeamRule]:
        """Get patterns to escalate."""
        return [r for r in self.rules if r.action == "escalate"]

    def should_ignore(self, file_path: str, message: str) -> bool:
        """Check if a finding should be ignored."""
        for rule in self.get_ignores():
            if rule.files and file_path not in rule.files:
                continue
            if rule.pattern.lower() in message.lower():
                return True
        return False

    def should_escalate(self, file_path: str, message: str) -> str | None:
        """Check if a finding should be escalated. Returns new severity or None."""
        for rule in self.get_escalations():
            if rule.files and file_path not in rule.files:
                continue
            if rule.pattern.lower() in message.lower():
                return rule.severity
        return None


def load_team_rules(repo_root: Path) -> TeamRules:
    """Load team rules from .glance/rules.yaml or .glance/rules.json."""
    yaml_path = repo_root / ".glance" / "rules.yaml"
    json_path = repo_root / ".glance" / "rules.json"

    if json_path.exists():
        return _load_json_rules(json_path)
    if yaml_path.exists():
        return _load_yaml_rules(yaml_path)
    return TeamRules()


def _load_json_rules(path: Path) -> TeamRules:
    """Load rules from JSON file."""
    import json

    try:
        with open(path) as f:
            data = json.load(f)
        rules = []
        for r in data.get("rules", []):
            rules.append(
                TeamRule(
                    rule_id=r.get("id", ""),
                    description=r.get("description", ""),
                    action=r.get("action", "check"),
                    pattern=r.get("pattern", ""),
                    severity=r.get("severity", "warning"),
                    files=r.get("files", []),
                )
            )
        return TeamRules(rules=rules)
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to load team rules: {e}")
        return TeamRules()


def _load_yaml_rules(path: Path) -> TeamRules:
    """Load rules from YAML file."""
    try:
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f)
        rules = []
        for r in data.get("rules", []):
            rules.append(
                TeamRule(
                    rule_id=r.get("id", ""),
                    description=r.get("description", ""),
                    action=r.get("action", "check"),
                    pattern=r.get("pattern", ""),
                    severity=r.get("severity", "warning"),
                    files=r.get("files", []),
                )
            )
        return TeamRules(rules=rules)
    except ImportError:
        logger.warning("PyYAML not installed, cannot load YAML rules")
        return TeamRules()
    except Exception as e:
        logger.warning(f"Failed to load team rules: {e}")
        return TeamRules()


def format_rules_context(rules: TeamRules) -> str:
    """Format rules context for agent prompts."""
    if not rules.rules:
        return ""

    parts = ["### Team Rules"]
    checks = rules.get_checks()
    ignores = rules.get_ignores()
    escalations = rules.get_escalations()

    if checks:
        parts.append("Always check for:")
        for r in checks:
            parts.append(f"  - {r.description} (pattern: {r.pattern})")

    if ignores:
        parts.append("Ignore these patterns:")
        for r in ignores:
            parts.append(f"  - {r.description} (pattern: {r.pattern})")

    if escalations:
        parts.append("Escalate to critical:")
        for r in escalations:
            parts.append(f"  - {r.description} (pattern: {r.pattern})")

    return "\n".join(parts)
