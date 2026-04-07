"""Glance Conflict Detector - Detect and analyze git merge conflicts."""

from glance.conflict.analyzer import ConflictAnalysis, ConflictAnalyzer, RiskLevel
from glance.conflict.detector import (
    ConflictDetector,
    ConflictFile,
    ConflictRegion,
    detect_conflicts,
)
from glance.conflict.reporter import ConflictReporter
from glance.conflict.resolver import ConflictResolver

__all__ = [
    "ConflictDetector",
    "ConflictFile",
    "ConflictRegion",
    "ConflictAnalyzer",
    "ConflictAnalysis",
    "ConflictReporter",
    "ConflictResolver",
    "RiskLevel",
    "detect_conflicts",
]
