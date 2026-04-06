"""RAG and Knowledge System for GR-Review.

Provides:
1. Codebase semantic search (RAG-like)
2. Historical learning from past reviews
3. Pattern detection for better suggestions
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("glance.knowledge")


@dataclass
class CodePattern:
    """Represents a code pattern or anti-pattern learned over time."""

    pattern_id: str
    pattern_type: str  # "good", "bad", "fixable"
    description: str
    code_snippet: str
    language: str
    times_seen: int = 1
    last_seen: datetime = field(default_factory=datetime.now)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class ReviewHistory:
    """Historical record of a code review."""

    pr_number: int
    pr_title: str
    repository: str
    timestamp: datetime
    files_changed: list[str]
    findings_count: int
    verdict: str
    key_patterns: list[str]
    agent_feedback: dict[str, str]  # What worked/didn't


@dataclass
class ContextResult:
    """Result from context retrieval."""

    content: str
    source: str  # "knowledge_base", "history", "rag", "repo_map"
    relevance_score: float
    tokens_estimate: int


class LocalKnowledgeBase:
    """Simple file-based knowledge base (no external dependencies).

    Stores patterns and review history in JSON files for:
    - Pattern learning from past reviews
    - Cross-file dependency awareness
    - Similar issue detection
    """

    def __init__(self, storage_path: str | Path | None = None):
        """Initialize knowledge base.

        Args:
            storage_path: Where to store knowledge files.
        """
        self.storage_path = (
            Path(storage_path) if storage_path else Path.home() / ".glance" / "knowledge"
        )
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.patterns_file = self.storage_path / "patterns.json"
        self.history_file = self.storage_path / "history.json"
        self.feedback_file = self.storage_path / "feedback.json"

        self._patterns: dict[str, CodePattern] = {}
        self._history: list[ReviewHistory] = []
        self._feedback: dict[str, Any] = {}

        self._load()

    def _load(self) -> None:
        """Load knowledge base from disk."""
        # Load patterns
        if self.patterns_file.exists():
            try:
                data = json.loads(self.patterns_file.read_text())
                for k, v in data.items():
                    v["last_seen"] = datetime.fromisoformat(v["last_seen"])
                    self._patterns[k] = CodePattern(**v)
            except Exception as e:
                logger.warning(f"Failed to load patterns: {e}")

        # Load history
        if self.history_file.exists():
            try:
                data = json.loads(self.history_file.read_text())
                for item in data:
                    item["timestamp"] = datetime.fromisoformat(item["timestamp"])
                    self._history.append(ReviewHistory(**item))
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")

        # Load feedback
        if self.feedback_file.exists():
            try:
                self._feedback = json.loads(self.feedback_file.read_text())
            except Exception as e:
                logger.warning(f"Failed to load feedback: {e}")

        logger.info(f"Loaded {len(self._patterns)} patterns, {len(self._history)} history entries")

    def _save(self) -> None:
        """Save knowledge base to disk."""
        try:
            # Save patterns
            patterns_data = {
                k: {**v.__dict__, "last_seen": v.last_seen.isoformat()}
                for k, v in self._patterns.items()
            }
            self.patterns_file.write_text(json.dumps(patterns_data, indent=2))

            # Save history (keep last 100)
            history_data = [
                {**h.__dict__, "timestamp": h.timestamp.isoformat()} for h in self._history[-100:]
            ]
            self.history_file.write_text(json.dumps(history_data, indent=2))

            # Save feedback
            self.feedback_file.write_text(json.dumps(self._feedback, indent=2))

        except Exception as e:
            logger.error(f"Failed to save knowledge base: {e}")

    def add_pattern(
        self,
        pattern_type: str,
        description: str,
        code_snippet: str,
        language: str,
    ) -> str:
        """Add a new code pattern to the knowledge base.

        Args:
            pattern_type: Type of pattern (good, bad, fixable).
            description: Description of the pattern.
            code_snippet: Example code.
            language: Programming language.

        Returns:
            Pattern ID.
        """
        # Create hash-based ID from content
        pattern_id = hashlib.md5(f"{description}{language}".encode()).hexdigest()[:12]

        if pattern_id in self._patterns:
            # Update existing pattern
            self._patterns[pattern_id].times_seen += 1
            self._patterns[pattern_id].last_seen = datetime.now()
        else:
            # Create new pattern
            self._patterns[pattern_id] = CodePattern(
                pattern_id=pattern_id,
                pattern_type=pattern_type,
                description=description,
                code_snippet=code_snippet[:500],  # Limit size
                language=language,
            )

        self._save()
        return pattern_id

    def find_similar_patterns(
        self,
        code_snippet: str,
        pattern_type: str | None = None,
        limit: int = 5,
    ) -> list[CodePattern]:
        """Find similar patterns based on code snippet.

        Uses simple string matching for now (can upgrade to embeddings later).

        Args:
            code_snippet: Code to match against.
            pattern_type: Optional filter by type.
            limit: Max results.

        Returns:
            List of similar patterns.
        """
        results = []
        snippet_lower = code_snippet.lower()

        for pattern in self._patterns.values():
            if pattern_type and pattern.pattern_type != pattern_type:
                continue

            # Simple keyword matching
            keywords = pattern.description.lower().split()
            matches = sum(1 for kw in keywords if kw in snippet_lower)

            if matches > 0:
                results.append((pattern, matches))

        # Sort by matches and return top results
        results.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in results[:limit]]

    def add_review_history(
        self,
        pr_number: int,
        pr_title: str,
        repository: str,
        files_changed: list[str],
        findings_count: int,
        verdict: str,
        key_patterns: list[str],
    ) -> None:
        """Add a review to history for learning.

        Args:
            pr_number: PR number.
            pr_title: PR title.
            repository: Repository name.
            files_changed: List of files changed.
            findings_count: Number of findings.
            verdict: Verdict (pass, concerns, critical).
            key_patterns: Key patterns identified in this review.
        """
        history_entry = ReviewHistory(
            pr_number=pr_number,
            pr_title=pr_title,
            repository=repository,
            timestamp=datetime.now(),
            files_changed=files_changed,
            findings_count=findings_count,
            verdict=verdict,
            key_patterns=key_patterns,
            agent_feedback={},
        )

        self._history.append(history_entry)

        # Also learn patterns from this review
        for pattern in key_patterns:
            self.add_pattern(
                pattern_type="review_pattern",
                description=pattern,
                code_snippet="",
                language="mixed",
            )

        self._save()

    def get_similar_reviews(
        self,
        files_changed: list[str],
        limit: int = 5,
    ) -> list[ReviewHistory]:
        """Find similar past reviews based on files changed.

        Args:
            files_changed: List of files in current PR.
            limit: Max results.

        Returns:
            List of similar past reviews.
        """
        results = []

        for review in self._history:
            # Calculate overlap in files
            overlap = len(set(review.files_changed) & set(files_changed))
            if overlap > 0:
                results.append((review, overlap))

        results.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in results[:limit]]

    def add_feedback(
        self,
        pr_number: int,
        agent_name: str,
        feedback_type: str,  # "helpful", "not_helpful", "corrected"
        feedback: str,
    ) -> None:
        """Record user feedback on agent suggestions.

        Args:
            pr_number: PR number.
            agent_name: Which agent.
            feedback_type: Type of feedback.
            feedback: Feedback text.
        """
        key = f"{pr_number}_{agent_name}"
        if key not in self._feedback:
            self._feedback[key] = []

        self._feedback[key].append(
            {
                "type": feedback_type,
                "feedback": feedback,
                "timestamp": datetime.now().isoformat(),
            }
        )

        self._save()

    def get_improved_prompts(self) -> dict[str, str]:
        """Get improved system prompts based on feedback.

        Returns:
            Dict of agent_name -> improved prompt additions.
        """
        improvements = {}

        # Analyze feedback for each agent
        agent_feedback: dict[str, list] = {}
        for key, feedbacks in self._feedback.items():
            _, agent = key.rsplit("_", 1)
            if agent not in agent_feedback:
                agent_feedback[agent] = []
            agent_feedback[agent].extend(feedbacks)

        # Generate improvements
        for agent, feedbacks in agent_feedback.items():
            not_helpful = [f for f in feedbacks if f["type"] == "not_helpful"]
            if not_helpful:
                improvements[agent] = (
                    f"Note: Previous suggestions that were marked not helpful: "
                    f"{[f['feedback'][:100] for f in not_helpful[:3]]}"
                )

        return improvements

    def get_context_for_review(
        self,
        files_changed: list[str],
        diff_content: str,
    ) -> list[ContextResult]:
        """Get relevant context for a new review.

        Combines:
        - Similar past reviews
        - Relevant patterns
        - Learned anti-patterns

        Args:
            files_changed: Files in the PR.
            diff_content: Diff content.

        Returns:
            List of context results.
        """
        context = []

        # 1. Similar past reviews
        similar_reviews = self.get_similar_reviews(files_changed, limit=3)
        if similar_reviews:
            context.append(
                ContextResult(
                    content=f"Similar past reviews: {[(r.pr_title, r.verdict) for r in similar_reviews]}",
                    source="history",
                    relevance_score=0.8,
                    tokens_estimate=100,
                )
            )

        # 2. Relevant patterns for changed files
        relevant_patterns = []
        for pattern in self._patterns.values():
            if pattern.pattern_type in ("bad", "fixable"):
                relevant_patterns.append(pattern)

        if relevant_patterns[:5]:
            patterns_text = "\n".join(
                [f"- {p.description}: {p.code_snippet[:100]}" for p in relevant_patterns[:5]]
            )
            context.append(
                ContextResult(
                    content=f"Known patterns to watch:\n{patterns_text}",
                    source="knowledge_base",
                    relevance_score=0.7,
                    tokens_estimate=300,
                )
            )

        # 3. Check for repeated issues
        for file in files_changed:
            file_patterns = self.find_similar_patterns(file, limit=2)
            if file_patterns:
                context.append(
                    ContextResult(
                        content=f"File {file} has similar patterns in past: {[p.description for p in file_patterns]}",
                        source="pattern_matching",
                        relevance_score=0.6,
                        tokens_estimate=50,
                    )
                )

        return context


class SemanticSearch:
    """Simple semantic search without external vector DB.

    Uses keyword-based scoring for code similarity.
    Can be upgraded to full embeddings later.
    """

    def __init__(self, knowledge_base: LocalKnowledgeBase | None = None):
        """Initialize semantic search.

        Args:
            knowledge_base: Knowledge base to search.
        """
        self.kb = knowledge_base or LocalKnowledgeBase()

    def search_code(
        self,
        query: str,
        codebase_map: dict[str, Any] | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search for relevant code in the codebase.

        Args:
            query: Search query.
            codebase_map: Map of repository signatures.
            limit: Max results.

        Returns:
            List of relevant code items with scores.
        """
        results = []

        query_lower = query.lower()
        query_words = set(query_lower.split())

        # Search in repository map if available
        if codebase_map:
            for file_path, signatures in codebase_map.get("files", {}).items():
                score = 0

                # Check file name
                for word in query_words:
                    if word in file_path.lower():
                        score += 2

                # Check signatures
                for sig in signatures:
                    sig_name = sig.get("name", "").lower()
                    for word in query_words:
                        if word in sig_name:
                            score += 1

                if score > 0:
                    results.append(
                        {
                            "file": file_path,
                            "signatures": signatures,
                            "score": score,
                        }
                    )

        # Also check knowledge base patterns
        patterns = self.kb.find_similar_patterns(query, limit=limit)
        for pattern in patterns:
            results.append(
                {
                    "pattern": pattern.description,
                    "code": pattern.code_snippet[:200],
                    "type": pattern.pattern_type,
                    "score": 3,
                }
            )

        # Sort by score and return top results
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results[:limit]


# Global instances
_knowledge_base: LocalKnowledgeBase | None = None
_semantic_search: SemanticSearch | None = None


def get_knowledge_base() -> LocalKnowledgeBase:
    """Get global knowledge base instance."""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = LocalKnowledgeBase()
    return _knowledge_base


def get_semantic_search() -> SemanticSearch:
    """Get global semantic search instance."""
    global _semantic_search
    if _semantic_search is None:
        _semantic_search = SemanticSearch(get_knowledge_base())
    return _semantic_search
