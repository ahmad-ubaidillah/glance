"""Tests for GR-Review configuration."""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch


class TestGlanceConfig:
    """Test GlanceConfig loading from environment variables."""

    def test_default_values(self):
        """Test default configuration values."""
        with patch.dict(os.environ, {}, clear=True):
            from glance.config import GlanceConfig

            config = GlanceConfig()
            assert config.llm_provider.value == "zhipuai"
            assert config.llm_model == "glm-4-flash"
            assert config.execution_mode.value == "parallel"

    def test_llm_provider_from_env(self):
        """Test LLM provider loading from environment."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
            from glance.config import GlanceConfig
            import importlib
            import glance.config

            importlib.reload(glance.config)

            from glance.config import GlanceConfig

            config = GlanceConfig()
            assert config.llm_provider.value == "openai"

    def test_github_config(self):
        """Test GitHub configuration."""
        with patch.dict(
            os.environ,
            {
                "GITHUB_TOKEN": "ghp_test123",
                "GITHUB_REPOSITORY": "owner/repo",
                "GITHUB_PR_NUMBER": "42",
            },
        ):
            from glance.config import GlanceConfig
            import importlib
            import glance.config

            importlib.reload(glance.config)

            from glance.config import GlanceConfig

            config = GlanceConfig()
            assert config.github_token == "ghp_test123"
            assert config.github_repository == "owner/repo"
            assert config.github_pr_number == 42

    def test_execution_mode_parallel(self):
        """Test parallel execution mode."""
        with patch.dict(os.environ, {"EXECUTION_MODE": "parallel"}):
            from glance.config import GlanceConfig
            import importlib
            import glance.config

            importlib.reload(glance.config)

            from glance.config import GlanceConfig

            config = GlanceConfig()
            assert config.execution_mode.value == "parallel"

    def test_execution_mode_sequential(self):
        """Test sequential execution mode."""
        with patch.dict(os.environ, {"EXECUTION_MODE": "sequential"}):
            from glance.config import GlanceConfig
            import importlib
            import glance.config

            importlib.reload(glance.config)

            from glance.config import GlanceConfig

            config = GlanceConfig()
            assert config.execution_mode.value == "sequential"

    def test_ci_provider_config(self):
        """Test CI provider configuration."""
        with patch.dict(
            os.environ,
            {
                "CI_PROVIDER": "gitlab",
                "GITLAB_URL": "https://gitlab.com",
                "GITLAB_API_TOKEN": "glpat-test",
                "PROJECT_ID": "12345",
            },
        ):
            from glance.config import GlanceConfig
            import importlib
            import glance.config

            importlib.reload(glance.config)

            from glance.config import GlanceConfig

            config = GlanceConfig()
            assert config.ci_provider == "gitlab"
            assert config.gitlab_url == "https://gitlab.com"
            assert config.gitlab_api_token == "glpat-test"
            assert config.project_id == "12345"

    def test_get_llm_config(self):
        """Test LLM config generation."""
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "openai",
                "LLM_API_KEY": "sk-test",
                "LLM_MODEL": "gpt-4",
            },
            clear=True,
        ):
            from glance.config import GlanceConfig
            import importlib
            import glance.config

            importlib.reload(glance.config)

            from glance.config import GlanceConfig

            config = GlanceConfig()
            llm_config = config.get_llm_config()

            assert llm_config["provider"] == "openai"
            assert llm_config["api_key"] == "sk-test"
            assert llm_config["model"] == "gpt-4"

    def test_get_github_repo_parts(self):
        """Test GitHub repository parsing."""
        with patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "owner/repo",
            },
            clear=True,
        ):
            from glance.config import GlanceConfig
            import importlib
            import glance.config

            importlib.reload(glance.config)

            from glance.config import GlanceConfig

            config = GlanceConfig()
            owner, repo = config.get_github_repo_parts()

            assert owner == "owner"
            assert repo == "repo"
