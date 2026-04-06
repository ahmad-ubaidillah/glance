"""Adaptive Agent Router - Smart agent selection based on PR complexity.

Determines which agents to run based on:
- File types changed
- Size of changes
- Type of changes (new features, bug fixes, config, tests)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("glance.routing")


class AgentType(str, Enum):
    """Available agent types."""

    ARCHITECT = "architect"  # SWE/Architecture
    BUG_HUNTER = "bug_hunter"  # QA/Bug detection
    WHITE_HAT = "white_hat"  # Security
    ARBITRATOR = "arbitrator"  # Final consolidation


class PRComplexity(str, Enum):
    """Complexity level of a PR."""

    SIMPLE = "simple"  # Small changes, single file
    MEDIUM = "medium"  # Multiple files, some tests
    COMPLEX = "complex"  # Many files, multiple concerns


@dataclass
class RoutingDecision:
    """Result of agent routing decision."""

    complexity: PRComplexity
    agents_to_run: list[AgentType]
    reason: str
    confidence: float  # 0-1 confidence in decision


class AdaptiveRouter:
    """Smart router that selects appropriate agents based on PR content."""

    def __init__(
        self,
        always_run_architect: bool = True,
        min_files_for_parallel: int = 3,
    ) -> None:
        """Initialize the router.

        Args:
            always_run_architect: Always include architect in reviews.
            min_files_for_parallel: Minimum files to consider parallel execution.
        """
        self.always_run_architect = always_run_architect
        self.min_files_for_parallel = min_files_for_parallel

    def route(
        self,
        file_paths: list[str],
        files_changed: int,
        has_tests: bool,
        has_security_files: bool,
        has_config_changes: bool,
        lines_changed: int,
    ) -> RoutingDecision:
        """Determine which agents to run based on PR characteristics.

        Args:
            file_paths: List of file paths changed.
            files_changed: Number of files changed.
            has_tests: Whether changes include test files.
            has_security_files: Whether changes include security-sensitive files.
            has_config_changes: Whether changes include config files.
            lines_changed: Approximate lines changed.

        Returns:
            RoutingDecision with agents to run and reasoning.
        """
        agents: list[AgentType] = []

        # Determine complexity
        complexity = self._determine_complexity(files_changed, lines_changed, file_paths)

        # Always run architect for architecture review
        if self.always_run_architect or complexity != PRComplexity.SIMPLE:
            agents.append(AgentType.ARCHITECT)

        # Run bug hunter for:
        # - Complex PRs
        # - PRs with test files (likely bug fixes)
        # - Medium+ PRs
        if complexity in (PRComplexity.COMPLEX, PRComplexity.MEDIUM) or has_tests:
            agents.append(AgentType.BUG_HUNTER)

        # Run white hat for:
        # - Security-sensitive files
        # - Config changes (potential security issues)
        # - Complex PRs
        if has_security_files or has_config_changes or complexity == PRComplexity.COMPLEX:
            agents.append(AgentType.WHITE_HAT)

        # Always run arbitrator for final consolidation
        agents.append(AgentType.ARBITRATOR)

        # Remove duplicates while preserving order
        agents = list(dict.fromkeys(agents))

        # Generate reason
        reason = self._generate_reason(
            complexity, agents, has_tests, has_security_files, has_config_changes
        )

        # Calculate confidence
        confidence = self._calculate_confidence(complexity, files_changed, len(file_paths))

        logger.info(
            f"Routing decision: complexity={complexity.value}, "
            f"agents={[a.value for a in agents]}, confidence={confidence:.2f}"
        )

        return RoutingDecision(
            complexity=complexity,
            agents_to_run=agents,
            reason=reason,
            confidence=confidence,
        )

    def _determine_complexity(
        self,
        files_changed: int,
        lines_changed: int,
        file_paths: list[str],
    ) -> PRComplexity:
        """Determine PR complexity."""
        # Simple: 1-2 files, small changes
        if files_changed <= 2 and lines_changed < 100:
            return PRComplexity.SIMPLE

        # Complex: Many files or large changes
        if files_changed >= 5 or lines_changed > 500:
            return PRComplexity.COMPLEX

        # Medium: Everything else
        return PRComplexity.MEDIUM

    def _generate_reason(
        self,
        complexity: PRComplexity,
        agents: list[AgentType],
        has_tests: bool,
        has_security_files: bool,
        has_config_changes: bool,
    ) -> str:
        """Generate human-readable reason for routing decision."""
        reasons = []

        # Complexity reason
        reasons.append(f"Complexity: {complexity.value}")

        # Content reasons
        if has_tests:
            reasons.append("includes test files")
        if has_security_files:
            reasons.append("contains security-sensitive files")
        if has_config_changes:
            reasons.append("has config changes")

        # Agents
        agent_names = {
            AgentType.ARCHITECT: "Architect",
            AgentType.BUG_HUNTER: "BugHunter",
            AgentType.WHITE_HAT: "WhiteHat",
            AgentType.ARBITRATOR: "Arbitrator",
        }
        reasons.append(f"Agents: {', '.join(agent_names[a] for a in agents)}")

        return "; ".join(reasons)

    def _calculate_confidence(
        self,
        complexity: PRComplexity,
        files_changed: int,
        unique_paths: int,
    ) -> float:
        """Calculate confidence in routing decision."""
        # More files = more confident in complexity assessment
        base_confidence = 0.7

        if complexity == PRComplexity.SIMPLE:
            return 0.9  # High confidence for simple PRs
        elif complexity == PRComplexity.COMPLEX:
            return min(0.95, base_confidence + 0.1 * files_changed)
        else:
            # Medium - less confident
            return min(0.85, base_confidence + 0.05 * files_changed)

    def should_run_parallel(self, complexity: PRComplexity) -> bool:
        """Determine if agents should run in parallel or sequential.

        Args:
            complexity: PR complexity level.

        Returns:
            True for parallel execution, False for sequential.
        """
        return complexity != PRComplexity.SIMPLE

    def get_optimized_order(self, agents: list[AgentType]) -> list[AgentType]:
        """Get optimized execution order for agents.

        Args:
            agents: List of agents to run.

        Returns:
            Ordered list for sequential execution.
        """
        # For sequential, run in this order:
        # 1. Architect (foundation - understand code structure)
        # 2. Bug Hunter (find issues based on understanding)
        # 3. White Hat (security last - need full context)
        # 4. Arbitrator (consolidate at end)

        order = [
            AgentType.ARCHITECT,
            AgentType.BUG_HUNTER,
            AgentType.WHITE_HAT,
            AgentType.ARBITRATOR,
        ]

        return [a for a in order if a in agents]


def create_router(
    mode: str = "adaptive",
    always_architect: bool = True,
) -> AdaptiveRouter:
    """Factory function to create router.

    Args:
        mode: Routing mode - "adaptive", "parallel", or "sequential"
        always_architect: Always include architect.

    Returns:
        AdaptiveRouter instance.
    """
    if mode == "parallel":
        # Always run all agents in parallel
        return _ParallelRouter()
    elif mode == "sequential":
        # Always run sequentially
        return _SequentialRouter()
    else:
        # Adaptive
        return AdaptiveRouter(always_run_architect=always_architect)


class _ParallelRouter(AdaptiveRouter):
    """Router that always suggests parallel execution."""

    def route(self, **kwargs) -> RoutingDecision:
        return RoutingDecision(
            complexity=PRComplexity.COMPLEX,
            agents_to_run=[
                AgentType.ARCHITECT,
                AgentType.BUG_HUNTER,
                AgentType.WHITE_HAT,
                AgentType.ARBITRATOR,
            ],
            reason="Parallel mode: running all agents",
            confidence=1.0,
        )

    def should_run_parallel(self, **kwargs) -> bool:
        return True


class _SequentialRouter(AdaptiveRouter):
    """Router that always suggests sequential execution."""

    def route(self, **kwargs) -> RoutingDecision:
        return RoutingDecision(
            complexity=PRComplexity.COMPLEX,
            agents_to_run=[
                AgentType.ARCHITECT,
                AgentType.BUG_HUNTER,
                AgentType.WHITE_HAT,
                AgentType.ARBITRATOR,
            ],
            reason="Sequential mode: running all agents one by one",
            confidence=1.0,
        )

    def should_run_parallel(self, **kwargs) -> bool:
        return False
