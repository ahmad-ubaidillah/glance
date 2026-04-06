"""Configuration management for Glance.

Uses pydantic BaseSettings for automatic environment variable loading
and validation, with optional .env file support via python-dotenv.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings


class ExecutionMode(str, Enum):
    """Execution mode for agent reviews."""

    PARALLEL = "parallel"  # Run all agents simultaneously
    SEQUENTIAL = "sequential"  # Run agents one by one (single LLM)


class RoutingMode(str, Enum):
    """Routing mode for adaptive agent selection."""

    ADAPTIVE = "adaptive"  # Smart routing based on PR characteristics
    PARALLEL = "parallel"  # Always run all agents in parallel
    SEQUENTIAL = "sequential"  # Always run agents sequentially


class LLMProviderConfig(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    ZHIPUAI = "zhipuai"
    AZURE_OPENAI = "azure_openai"
    OLLAMA = "ollama"
    CUSTOM = "custom"


class GlanceConfig(BaseSettings):
    """Configuration for GR-Review, loaded from environment variables and .env files.

    All fields map to environment variables automatically. Required fields
    will raise a ValidationError if not provided.
    """

    # -- LLM Provider Configuration ---------------------------------------------
    llm_provider: LLMProviderConfig = Field(
        "zhipuai",
        alias="LLM_PROVIDER",
        description="LLM provider to use (openai, anthropic, google, zhipuai, azure_openai, ollama, custom).",
    )
    llm_api_key: str = Field(
        "",
        alias="LLM_API_KEY",
        description="API key for the LLM provider. Falls back to provider-specific env vars.",
    )
    llm_model: str = Field(
        "glm-4-flash",
        alias="LLM_MODEL",
        description="Model name to use for LLM calls.",
    )
    llm_base_url: str = Field(
        "",
        alias="LLM_BASE_URL",
        description="Base URL for the LLM API (required for custom providers, optional for others).",
    )

    # -- Execution Mode ----------------------------------------------------------
    execution_mode: ExecutionMode = Field(
        "parallel",
        alias="EXECUTION_MODE",
        description="Execution mode: 'parallel' runs all agents simultaneously, 'sequential' runs one by one.",
    )

    # -- Routing Mode ------------------------------------------------------------
    routing_mode: RoutingMode = Field(
        "adaptive",
        alias="ROUTING_MODE",
        description="Routing mode: 'adaptive' smart routing based on PR complexity, 'parallel' always all agents, 'sequential' always one by one.",
    )

    # -- GitHub/GitLab Configuration ---------------------------------------------
    github_token: str = Field(
        "",
        alias="GITHUB_TOKEN",
        description="Git provider token (GitHub PAT, GitLab token) with repo write scope.",
    )
    github_repository: str = Field(
        "",
        alias="GITHUB_REPOSITORY",
        description='GitHub repository in "owner/repo" format.',
    )
    github_pr_number: int = Field(
        0,
        alias="GITHUB_PR_NUMBER",
        description="Pull request number to review.",
    )
    github_event_path: str = Field(
        "",
        alias="GITHUB_EVENT_PATH",
        description="Path to the GitHub event JSON file (optional).",
    )

    # -- Token Optimization Configuration --------------------------------------
    enable_caching: bool = Field(
        True,
        alias="ENABLE_CACHING",
        description="Enable prompt caching for repeated patterns.",
    )
    max_context_tokens: int = Field(
        8000,
        alias="MAX_CONTEXT_TOKENS",
        description="Max tokens to send in context (input).",
    )
    smart_truncation: bool = Field(
        True,
        alias="SMART_TRUNCATION",
        description="Enable smart truncation for large diffs.",
    )

    # -- Memory & Learning Configuration ---------------------------------------
    enable_memory: bool = Field(
        True,
        alias="ENABLE_MEMORY",
        description="Enable persistent memory - learns developer patterns and recurring issues.",
    )
    enable_review_history: bool = Field(
        True,
        alias="ENABLE_REVIEW_HISTORY",
        description="Enable review history tracking across PRs.",
    )

    # -- Linter Configuration ----------------------------------------------------
    linter_command: str = Field(
        "eslint",
        alias="LINTER_COMMAND",
        description="Command to run for linting changed files.",
    )
    skip_linter: bool = Field(
        False,
        alias="SKIP_LINTER",
        description="Skip linter check (not recommended for production).",
    )

    # -- CI Integration Configuration -------------------------------------------
    ci_provider: str = Field(
        "github",
        alias="CI_PROVIDER",
        description="CI provider: 'github', 'gitlab', 'jenkins', 'teamcity', 'circleci', 'azure', 'none'.",
    )
    ci_status_url: str | None = Field(
        None,
        alias="CI_STATUS_URL",
        description="CI status URL (TeamCity, Jenkins, etc.).",
    )
    ci_api_token: str = Field(
        "",
        alias="CI_API_TOKEN",
        description="API token for CI provider authentication.",
    )
    ci_build_config: str = Field(
        "",
        alias="CI_BUILD_CONFIG",
        description="Build configuration ID (TeamCity, Jenkins).",
    )

    # -- GitLab CI Configuration -------------------------------------------------
    gitlab_url: str = Field(
        "",
        alias="GITLAB_URL",
        description="GitLab instance URL (for GitLab CI integration).",
    )
    gitlab_api_token: str = Field(
        "",
        alias="GITLAB_API_TOKEN",
        description="GitLab API token for CI status.",
    )
    project_id: str = Field(
        "",
        alias="PROJECT_ID",
        description="GitLab project ID or path-encoded name.",
    )

    # -- Jenkins Configuration --------------------------------------------------
    jenkins_url: str = Field(
        "",
        alias="JENKINS_URL",
        description="Jenkins server URL.",
    )
    jenkins_username: str = Field(
        "",
        alias="JENKINS_USERNAME",
        description="Jenkins username for authentication.",
    )
    jenkins_api_token: str = Field(
        "",
        alias="JENKINS_API_TOKEN",
        description="Jenkins API token.",
    )
    job_name: str = Field(
        "",
        alias="JOB_NAME",
        description="Jenkins job name to monitor.",
    )

    # -- Review Limits -----------------------------------------------------------
    max_review_files: int = Field(
        50,
        alias="MAX_REVIEW_FILES",
        description="Maximum number of files to include in a single review.",
    )
    max_diff_chars: int = Field(
        100_000,
        alias="MAX_DIFF_CHARS",
        description="Maximum characters allowed per file diff.",
    )

    # -- Logging ----------------------------------------------------------------
    log_level: str = Field(
        "INFO",
        alias="LOG_LEVEL",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
    )

    # -- LLM Parameters ----------------------------------------------------------
    temperature: float = Field(
        0.3,
        alias="TEMPERATURE",
        description="Sampling temperature for LLM generation.",
    )
    max_tokens: int = Field(
        4096,
        alias="MAX_TOKENS",
        description="Maximum tokens in a single LLM response.",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def get_github_repo_parts(self) -> Tuple[str, str]:
        """Split ``github_repository`` into ``(owner, repo)`` tuple.

        Returns:
            A tuple of (owner, repo).

        Raises:
            ValueError: If ``github_repository`` is not in ``owner/repo`` format.
        """
        parts = self.github_repository.split("/", 1)
        if len(parts) != 2 or not all(parts):
            raise ValueError(
                f'GITHUB_REPOSITORY must be in "owner/repo" format, got: {self.github_repository!r}'
            )
        return parts[0], parts[1]

    def get_llm_config(self) -> dict:
        """Get LLM configuration as a dict for client creation.

        Returns:
            Dict with provider, api_key, model, and base_url.
        """
        import os

        # Map provider to default base URLs
        default_base_urls = {
            "openai": "https://api.openai.com/v1",
            "anthropic": "",  # Uses different API
            "google": "",  # Uses different API
            "zhipuai": "https://open.bigmodel.cn/api/paas/v4",
            "azure_openai": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            "ollama": "http://localhost:11434/v1",
            "custom": "",
        }

        # Get API key from provider-specific env vars if not set
        api_key = self.llm_api_key
        if not api_key:
            env_keys = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "google": "GOOGLE_API_KEY",
                "zhipuai": "ZHIPUAI_API_KEY",
                "azure_openai": "AZURE_OPENAI_API_KEY",
                "custom": "CUSTOM_API_KEY",
            }
            env_key = env_keys.get(self.llm_provider, "")
            if env_key:
                api_key = os.getenv(env_key, "")

        return {
            "provider": self.llm_provider,
            "api_key": api_key,
            "model": self.llm_model,
            "base_url": self.llm_base_url or default_base_urls.get(self.llm_provider, ""),
        }


def load_config() -> GlanceConfig:
    """Load and validate the GR-Review configuration.

    Loads environment variables from a ``.env`` file (if present) and then
    instantiates :class:`GlanceConfig`, which validates all required fields.

    Returns:
        A fully validated ``GlanceConfig`` instance.

    Raises:
        ValueError: If any required configuration field is missing or invalid.
    """
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

    try:
        config = GlanceConfig()
    except ValidationError as exc:
        missing_fields = []
        for error in exc.errors():
            field = error.get("loc", ("unknown",))[0]
            if error.get("type") == "missing":
                missing_fields.append(field)
        if missing_fields:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing_fields)}. "
                f"Set these as environment variables or in a .env file."
            ) from exc
        raise ValueError(f"Configuration validation failed: {exc}") from exc

    return config
