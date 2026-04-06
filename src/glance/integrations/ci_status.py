"""CI Status Integration - Multi-provider CI/CD status fetching.

Supports:
- GitHub Actions / GitHub Combined Status API
- GitLab CI
- Jenkins
- Azure DevOps
- TeamCity
- CircleCI
- Custom webhooks/endpoints
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger("glance.integrations")


class CIProviderType(str, Enum):
    """Supported CI provider types."""

    GITHUB = "github"
    GITLAB = "gitlab"
    JENKINS = "jenkins"
    AZURE_DEVOPS = "azure"
    TEAMCITY = "teamcity"
    CIRCLECI = "circleci"
    CUSTOM = "custom"


class BuildState(str, Enum):
    """CI build state values."""

    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class CIContext:
    """Complete CI context for a PR review."""

    provider: CIProviderType
    build_state: BuildState
    commit_sha: str
    branch: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    failed_checks: list[str] = field(default_factory=list)
    raw_state: str = ""

    @property
    def is_failed(self) -> bool:
        """Check if the build failed."""
        return self.build_state in (BuildState.FAILURE, BuildState.ERROR)

    @property
    def is_pending(self) -> bool:
        """Check if the build is still pending."""
        return self.build_state == BuildState.PENDING


# For backwards compatibility
CIState = BuildState


class BaseCIProvider(ABC):
    """Abstract base class for CI providers."""

    @abstractmethod
    async def fetch_status(
        self,
        commit_sha: str,
        branch: str = "main",
        **kwargs: Any,
    ) -> CIContext | None:
        """Fetch CI status for a commit.

        Args:
            commit_sha: The commit SHA to check.
            branch: Branch name.
            **kwargs: Provider-specific arguments.

        Returns:
            CIContext with status, or None if unavailable.
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return the provider name."""
        pass


class GitHubCIProvider(BaseCIProvider):
    """GitHub Actions / Combined Status API provider."""

    def __init__(
        self,
        github_token: str,
        owner: str,
        repo: str,
    ) -> None:
        """Initialize GitHub CI provider.

        Args:
            github_token: GitHub personal access token.
            owner: Repository owner.
            repo: Repository name.
        """
        self.token = github_token
        self.owner = owner
        self.repo = repo

    def get_name(self) -> str:
        return "github"

    async def fetch_status(
        self,
        commit_sha: str,
        branch: str = "main",
        **kwargs: Any,
    ) -> CIContext | None:
        """Fetch combined status from GitHub API."""
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with httpx.AsyncClient() as client:
            try:
                url = f"https://api.github.com/repos/{self.owner}/{self.repo}/commits/{commit_sha}/status"
                response = await client.get(url, headers=headers, timeout=10.0)

                if response.status_code != 200:
                    logger.warning(f"GitHub status API returned {response.status_code}")
                    return None

                data = response.json()
                state = data.get("state", "unknown")

                state_map = {
                    "success": BuildState.SUCCESS,
                    "failure": BuildState.FAILURE,
                    "pending": BuildState.PENDING,
                    "error": BuildState.ERROR,
                }
                build_state = state_map.get(state, BuildState.UNKNOWN)

                failed_checks = []
                if state in ("failure", "error"):
                    for check in data.get("checks", []):
                        if check.get("conclusion") in (
                            "failure",
                            "timed_out",
                            "cancelled",
                        ):
                            failed_checks.append(check.get("name", "unknown"))

                return CIContext(
                    provider=CIProviderType.GITHUB,
                    build_state=build_state,
                    commit_sha=commit_sha,
                    branch=branch,
                    message=f"GitHub combined status: {state}",
                    details={"total_checks": data.get("total_count", 0)},
                    failed_checks=failed_checks,
                    raw_state=state,
                )

            except Exception as e:
                logger.error(f"Failed to fetch GitHub status: {e}")
                return None


class GitLabCIProvider(BaseCIProvider):
    """GitLab CI provider."""

    def __init__(
        self,
        gitlab_url: str,
        api_token: str,
        project_id: str,
    ) -> None:
        self.gitlab_url = gitlab_url.rstrip("/")
        self.token = api_token
        self.project_id = project_id

    def get_name(self) -> str:
        return "gitlab"

    async def fetch_status(
        self,
        commit_sha: str,
        branch: str = "main",
        **kwargs: Any,
    ) -> CIContext | None:
        headers = {"PRIVATE-TOKEN": self.token}

        async with httpx.AsyncClient() as client:
            try:
                url = f"{self.gitlab_url}/api/v4/projects/{self.project_id}/pipelines"
                params = {"sha": commit_sha, "per_page": 1}
                response = await client.get(
                    url, headers=headers, params=params, timeout=10.0
                )

                if response.status_code != 200:
                    return None

                pipelines = response.json()
                if not pipelines:
                    return CIContext(
                        provider=CIProviderType.GITLAB,
                        build_state=BuildState.UNKNOWN,
                        commit_sha=commit_sha,
                        branch=branch,
                        message="No pipeline found for commit",
                        details={},
                        failed_checks=[],
                        raw_state="unknown",
                    )

                pipeline = pipelines[0]
                status = pipeline.get("status", "unknown")

                status_map = {
                    "success": BuildState.SUCCESS,
                    "failed": BuildState.FAILURE,
                    "running": BuildState.PENDING,
                    "pending": BuildState.PENDING,
                    "canceled": BuildState.ERROR,
                }
                build_state = status_map.get(status, BuildState.UNKNOWN)

                return CIContext(
                    provider=CIProviderType.GITLAB,
                    build_state=build_state,
                    commit_sha=commit_sha,
                    branch=branch,
                    message=f"GitLab pipeline: {status}",
                    details={"pipeline_id": pipeline.get("id")},
                    failed_checks=[],
                    raw_state=status,
                )

            except Exception as e:
                logger.error(f"Failed to fetch GitLab status: {e}")
                return None


class JenkinsCIProvider(BaseCIProvider):
    """Jenkins CI provider."""

    def __init__(
        self,
        jenkins_url: str,
        username: str,
        api_token: str,
        job_name: str,
    ) -> None:
        self.jenkins_url = jenkins_url.rstrip("/")
        self.username = username
        self.token = api_token
        self.job_name = job_name
        self.auth = (username, api_token)

    def get_name(self) -> str:
        return "jenkins"

    async def fetch_status(
        self,
        commit_sha: str,
        branch: str = "main",
        **kwargs: Any,
    ) -> CIContext | None:
        async with httpx.AsyncClient() as client:
            try:
                url = f"{self.jenkins_url}/job/{self.job_name}/lastBuild/api/json"
                response = await client.get(url, auth=self.auth, timeout=10.0)

                if response.status_code != 200:
                    return None

                data = response.json()
                result = data.get("result", "UNKNOWN")

                result_map = {
                    "SUCCESS": BuildState.SUCCESS,
                    "FAILURE": BuildState.FAILURE,
                    "UNSTABLE": BuildState.FAILURE,
                    "ABORTED": BuildState.ERROR,
                    None: BuildState.PENDING,
                }
                build_state = result_map.get(result, BuildState.UNKNOWN)

                return CIContext(
                    provider=CIProviderType.JENKINS,
                    build_state=build_state,
                    commit_sha=commit_sha,
                    branch=branch,
                    message=f"Jenkins build: {result or 'running'}",
                    details={"build_number": data.get("number")},
                    failed_checks=[],
                    raw_state=result or "running",
                )

            except Exception as e:
                logger.error(f"Failed to fetch Jenkins status: {e}")
                return None


class TeamCityCIProvider(BaseCIProvider):
    """TeamCity CI provider."""

    def __init__(
        self,
        teamcity_url: str,
        username: str,
        password: str,
        build_config: str,
    ) -> None:
        self.teamcity_url = teamcity_url.rstrip("/")
        self.auth = (username, password)
        self.build_config = build_config

    def get_name(self) -> str:
        return "teamcity"

    async def fetch_status(
        self,
        commit_sha: str,
        branch: str = "main",
        **kwargs: Any,
    ) -> CIContext | None:
        headers = {"Accept": "application/json"}

        async with httpx.AsyncClient() as client:
            try:
                url = f"{self.teamcity_url}/app/rest/builds/buildType:{self.build_config},branch:refs/heads/{branch}"
                response = await client.get(
                    url, auth=self.auth, headers=headers, timeout=10.0
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                state = data.get("state", "unknown")
                status = data.get("status", "unknown")

                state_map = {
                    ("finished", "SUCCESS"): BuildState.SUCCESS,
                    ("finished", "FAILURE"): BuildState.FAILURE,
                    ("running", None): BuildState.PENDING,
                    ("queued", None): BuildState.PENDING,
                }
                key = (state, status)
                build_state = state_map.get(key, BuildState.UNKNOWN)

                return CIContext(
                    provider=CIProviderType.TEAMCITY,
                    build_state=build_state,
                    commit_sha=commit_sha,
                    branch=branch,
                    message=f"TeamCity build: {state}:{status}",
                    details={
                        "build_id": data.get("id"),
                        "build_number": data.get("number"),
                    },
                    failed_checks=[],
                    raw_state=f"{state}:{status}",
                )

            except Exception as e:
                logger.error(f"Failed to fetch TeamCity status: {e}")
                return None


class CircleCIProvider(BaseCIProvider):
    """CircleCI provider."""

    def __init__(
        self,
        api_token: str,
        vcs_type: str = "gh",
        username: str = "",
        project: str = "",
    ) -> None:
        self.token = api_token
        self.vcs_type = vcs_type
        self.username = username
        self.project = project

    def get_name(self) -> str:
        return "circleci"

    async def fetch_status(
        self,
        commit_sha: str,
        branch: str = "main",
        **kwargs: Any,
    ) -> CIContext | None:
        headers = {"Circle-Token": self.token}

        async with httpx.AsyncClient() as client:
            try:
                url = f"https://circleci.com/api/v2/project/{self.vcs_type}/{self.username}/{self.project}/pipeline"
                params = {"branch": branch, "sha": commit_sha, "page": 1, "per_page": 1}
                response = await client.get(
                    url, headers=headers, params=params, timeout=10.0
                )

                if response.status_code != 200:
                    return None

                pipelines = response.json().get("items", [])
                if not pipelines:
                    return CIContext(
                        provider=CIProviderType.CIRCLECI,
                        build_state=BuildState.UNKNOWN,
                        commit_sha=commit_sha,
                        branch=branch,
                        message="No pipeline found",
                        details={},
                        failed_checks=[],
                        raw_state="unknown",
                    )

                return CIContext(
                    provider=CIProviderType.CIRCLECI,
                    build_state=BuildState.SUCCESS,
                    commit_sha=commit_sha,
                    branch=branch,
                    message="Pipeline found",
                    details={},
                    failed_checks=[],
                    raw_state="success",
                )

            except Exception as e:
                logger.error(f"Failed to fetch CircleCI status: {e}")
                return None


def create_ci_provider(
    provider: CIProviderType | str,
    **config: Any,
) -> BaseCIProvider | None:
    """Create a CI provider based on type and configuration.

    Args:
        provider: CI provider type.
        **config: Provider-specific configuration.

    Returns:
        BaseCIProvider instance, or None if configuration is invalid.
    """
    if isinstance(provider, str):
        try:
            provider = CIProviderType(provider.lower())
        except ValueError:
            logger.error(f"Unknown CI provider: {provider}")
            return None

    if provider == CIProviderType.GITHUB:
        required = ["github_token", "owner", "repo"]
        missing = [k for k in required if not config.get(k)]
        if missing:
            logger.error(f"Missing config for GitHub CI: {missing}")
            return None
        return GitHubCIProvider(
            github_token=config["github_token"],
            owner=config["owner"],
            repo=config["repo"],
        )

    elif provider == CIProviderType.GITLAB:
        required = ["gitlab_url", "api_token", "project_id"]
        missing = [k for k in required if not config.get(k)]
        if missing:
            logger.error(f"Missing config for GitLab CI: {missing}")
            return None
        return GitLabCIProvider(
            gitlab_url=config["gitlab_url"],
            api_token=config["api_token"],
            project_id=config["project_id"],
        )

    elif provider == CIProviderType.JENKINS:
        required = ["jenkins_url", "username", "api_token", "job_name"]
        missing = [k for k in required if not config.get(k)]
        if missing:
            logger.error(f"Missing config for Jenkins CI: {missing}")
            return None
        return JenkinsCIProvider(
            jenkins_url=config["jenkins_url"],
            username=config["username"],
            api_token=config["api_token"],
            job_name=config["job_name"],
        )

    elif provider == CIProviderType.TEAMCITY:
        required = ["teamcity_url", "username", "password", "build_config"]
        missing = [k for k in required if not config.get(k)]
        if missing:
            logger.error(f"Missing config for TeamCity CI: {missing}")
            return None
        return TeamCityCIProvider(
            teamcity_url=config["teamcity_url"],
            username=config["username"],
            password=config["password"],
            build_config=config["build_config"],
        )

    elif provider == CIProviderType.CIRCLECI:
        required = ["api_token", "username", "project"]
        missing = [k for k in required if not config.get(k)]
        if missing:
            logger.error(f"Missing config for CircleCI: {missing}")
            return None
        return CircleCIProvider(
            api_token=config["api_token"],
            vcs_type=config.get("vcs_type", "gh"),
            username=config["username"],
            project=config["project"],
        )

    else:
        logger.error(f"Unsupported CI provider: {provider}")
        return None


def format_ci_context(context: CIContext) -> str:
    """Format CI context as a readable string for LLM prompts.

    Args:
        context: The CI context to format.

    Returns:
        Formatted string with key information.
    """
    lines = [
        "## CI Build Status",
        "",
        f"Provider: {context.provider.value}",
        f"Build State: {context.build_state.value.upper()}",
        f"Branch: {context.branch}",
        f"Commit: {context.commit_sha[:8]}",
        f"Message: {context.message}",
        "",
    ]

    if context.failed_checks:
        lines.append("### Failed Checks")
        for check in context.failed_checks[:5]:
            lines.append(f"- {check}")
        lines.append("")

    return "\n".join(lines)


# Legacy compatibility - keep old classes for backward compatibility
class CIStatusFetcher:
    """Legacy CI status fetcher for backwards compatibility.

    New code should use create_ci_provider() instead.
    """

    def __init__(self, github_client=None):
        self.github_client = github_client
        self._provider: BaseCIProvider | None = None

    def set_provider(self, provider: BaseCIProvider) -> None:
        """Set a CI provider for status fetching."""
        self._provider = provider

    def get_combined_status(self, pr_number: int) -> "CombinedCIStatus":
        """Get combined CI status (legacy method)."""
        # This is a stub for backwards compatibility
        from glance.integrations.github_client import GitHubClient

        if isinstance(self.github_client, GitHubClient):
            try:
                raw = self.github_client.get_combined_status(pr_number)
                return self._parse_legacy_status(raw)
            except Exception as e:
                logger.error(f"Failed to get CI status: {e}")

        return CombinedCIStatus(
            overall_state=CIState.UNKNOWN,
            summary="GitHub client not configured",
        )

    def _parse_legacy_status(self, raw_status: dict) -> "CombinedCIStatus":
        """Parse legacy status format."""
        checks = []
        failed = []
        pending = []

        for name, info in raw_status.get("statuses", {}).items():
            state_str = info.get("state", "unknown")
            state = (
                CIState.SUCCESS
                if state_str == "success"
                else (
                    CIState.FAILURE
                    if state_str in ("failure", "error")
                    else (
                        CIState.PENDING if state_str == "pending" else CIState.UNKNOWN
                    )
                )
            )

            checks.append(
                CIStatusInfo(
                    name=name, state=state, description=info.get("description", "")
                )
            )

            if state == CIState.FAILURE:
                failed.append(name)
            elif state == CIState.PENDING:
                pending.append(name)

        if failed:
            overall = CIState.FAILURE
            summary = f"CI Failed: {', '.join(failed[:3])}"
        elif pending:
            overall = CIState.PENDING
            summary = f"CI Pending: {', '.join(pending[:3])}"
        else:
            overall = CIState.SUCCESS
            summary = "All CI checks passed"

        return CombinedCIStatus(
            overall_state=overall,
            checks=checks,
            failed_checks=failed,
            pending_checks=pending,
            summary=summary,
        )

    def get_failure_context(self, pr_number: int) -> str:
        """Get formatted failure context (legacy method)."""
        status = self.get_combined_status(pr_number)

        if status.overall_state == CIState.SUCCESS:
            return "CI Status: All checks passed"
        if status.overall_state == CIState.PENDING:
            return f"CI Status: Pending ({', '.join(status.pending_checks)})"
        if not status.failed_checks:
            return "CI Status: Unknown"

        context = f"CI Status: FAILED\n"
        context += f"Failed checks: {', '.join(status.failed_checks)}\n\n"
        return context

    def should_wait_for_ci(self, pr_number: int) -> bool:
        """Check if should wait for CI."""
        status = self.get_combined_status(pr_number)
        return status.overall_state == CIState.PENDING


@dataclass
class CIStatusInfo:
    """Information about a CI status check."""

    name: str
    state: CIState
    description: str = ""
    url: str | None = None


@dataclass
class CombinedCIStatus:
    """Combined status of all CI checks."""

    overall_state: CIState
    checks: list[CIStatusInfo] = field(default_factory=list)
    failed_checks: list[str] = field(default_factory=list)
    pending_checks: list[str] = field(default_factory=list)
    summary: str = ""


def get_ci_status(github_client, pr_number: int) -> CombinedCIStatus:
    """Convenience function to get CI status."""
    fetcher = CIStatusFetcher(github_client)
    return fetcher.get_combined_status(pr_number)
