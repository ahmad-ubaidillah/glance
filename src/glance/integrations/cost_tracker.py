"""Token Cost Tracking and Response Caching.

Tracks:
- Token usage per review (input/output tokens)
- Estimated cost per provider
- Caches LLM responses for identical inputs
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("glance.cost")

# Approximate cost per 1M tokens (USD) - 2025 rates
COST_PER_1M_TOKENS = {
    "zhipuai": {"input": 0.5, "output": 2.0},
    "openai": {"input": 10.0, "output": 30.0},
    "anthropic": {"input": 15.0, "output": 75.0},
    "google": {"input": 1.25, "output": 5.0},
    "openrouter": {"input": 1.0, "output": 3.0},
}


@dataclass
class TokenUsage:
    """Tracks token usage for a single review."""

    review_id: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    timestamp: str = ""
    duration_seconds: float = 0.0

    def calculate_cost(self) -> float:
        """Calculate estimated cost based on provider rates."""
        rates = COST_PER_1M_TOKENS.get(self.provider, {"input": 5.0, "output": 15.0})
        self.estimated_cost = (
            self.input_tokens * rates["input"] / 1_000_000
            + self.output_tokens * rates["output"] / 1_000_000
        )
        return self.estimated_cost


@dataclass
class CacheEntry:
    """A cached LLM response."""

    cache_key: str
    response: str
    model: str
    timestamp: str = ""
    usage: dict = field(default_factory=dict)


@dataclass
class CostTracker:
    """Tracks token costs across reviews."""

    reviews: list[TokenUsage] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0

    def add_review(self, usage: TokenUsage) -> None:
        """Add a review's token usage."""
        self.reviews.append(usage)
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens
        self.total_cost += usage.estimated_cost

    def get_summary(self) -> str:
        """Get cost summary."""
        return (
            f"📊 Token Usage: {self.total_input_tokens:,} in / {self.total_output_tokens:,} out "
            f"= {self.total_input_tokens + self.total_output_tokens:,} total\n"
            f"💰 Estimated Cost: ${self.total_cost:.4f}"
        )


def compute_cache_key(messages: list[dict], model: str) -> str:
    """Compute a cache key for LLM request."""
    content = json.dumps({"messages": messages, "model": model}, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def load_cache(repo_root: Path) -> dict[str, CacheEntry]:
    """Load LLM response cache."""
    cache_file = repo_root / ".glance" / "llm_cache.json"
    if not cache_file.exists():
        return {}
    try:
        with open(cache_file) as f:
            data = json.load(f)
        return {k: CacheEntry(**v) for k, v in data.items()}
    except (json.JSONDecodeError, KeyError):
        return {}


def save_cache(repo_root: Path, cache: dict[str, CacheEntry]) -> None:
    """Save LLM response cache."""
    cache_dir = repo_root / ".glance"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "llm_cache.json"
    data = {
        k: {
            "cache_key": v.cache_key,
            "response": v.response,
            "model": v.model,
            "timestamp": v.timestamp,
        }
        for k, v in cache.items()
    }
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2)


def load_cost_tracker(repo_root: Path) -> CostTracker:
    """Load cost tracker."""
    cost_file = repo_root / ".glance" / "cost.json"
    if not cost_file.exists():
        return CostTracker()
    try:
        with open(cost_file) as f:
            data = json.load(f)
        tracker = CostTracker(
            total_input_tokens=data.get("total_input_tokens", 0),
            total_output_tokens=data.get("total_output_tokens", 0),
            total_cost=data.get("total_cost", 0.0),
        )
        for r in data.get("reviews", []):
            tracker.reviews.append(TokenUsage(**r))
        return tracker
    except (json.JSONDecodeError, KeyError):
        return CostTracker()


def save_cost_tracker(repo_root: Path, tracker: CostTracker) -> None:
    """Save cost tracker."""
    cost_dir = repo_root / ".glance"
    cost_dir.mkdir(parents=True, exist_ok=True)
    cost_file = cost_dir / "cost.json"
    data = {
        "total_input_tokens": tracker.total_input_tokens,
        "total_output_tokens": tracker.total_output_tokens,
        "total_cost": tracker.total_cost,
        "reviews": [
            {
                "review_id": r.review_id,
                "provider": r.provider,
                "model": r.model,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "total_tokens": r.total_tokens,
                "estimated_cost": r.estimated_cost,
                "timestamp": r.timestamp,
                "duration_seconds": r.duration_seconds,
            }
            for r in tracker.reviews[-100:]
        ],
    }
    with open(cost_file, "w") as f:
        json.dump(data, f, indent=2)
