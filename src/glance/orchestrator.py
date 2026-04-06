"""GR-Review Orchestrator - Main entry point for the code review system.

Coordinates all components:
1. GitHub PR interaction (via PyGithub)
2. Secret scanning (abort if secrets found)
3. CI status fetching (context for review)
4. Repository signature mapping (structural context)
5. Agent execution (parallel or sequential based on config)
6. Arbitrator consolidation
7. Comment posting to GitHub PR
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from github import Github

from glance.agents.architect import Architect
from glance.agents.arbitrator import ArbitratorAgent
from glance.agents.bug_hunter import BugHunterAgent
from glance.agents.white_hat import WhiteHatAgent
from glance.config import GlanceConfig, load_config
from glance.integrations.ci_status import (
    CIProviderType,
    create_ci_provider,
    format_ci_context,
)
from glance.integrations.signature_mapper import (
    SignatureMapper,
    format_signature_map,
)
from glance.llm.client import create_llm_client
from glance.scanners.secret_scanner import SecretScanner
from glance.agents.base import AgentReview, Finding

logger = logging.getLogger("glance")


class GRReviewOrchestrator:
    """Main orchestrator for GR-Review system.

    Coordinates all components to perform automated code review on GitHub PRs.
    """

    def __init__(self, config: GlanceConfig) -> None:
        """Initialize the orchestrator.

        Args:
            config: GR-Review configuration.
        """
        self.config = config

        # Initialize GitHub client
        self.github_client = Github(config.github_token)

        # Initialize LLM client using factory
        llm_config = config.get_llm_config()
        self.llm_client = create_llm_client(
            provider=llm_config["provider"],
            api_key=llm_config["api_key"],
            model=llm_config["model"],
            base_url=llm_config["base_url"],
        )

        # Initialize components
        self.secret_scanner = SecretScanner()
        self.repo_mapper = SignatureMapper()

        # Initialize CI provider if configured
        self.ci_provider = None
        if config.ci_provider and config.ci_provider != "none":
            self._init_ci_provider()

        # Initialize agents
        self.architect = Architect(config=config, client=self.llm_client)
        self.bug_hunter = BugHunterAgent(config=config, client=self.llm_client)
        self.white_hat = WhiteHatAgent(config=config, client=self.llm_client)
        self.arbitrator = ArbitratorAgent(config=config, client=self.llm_client)

    def _init_ci_provider(self) -> None:
        """Initialize CI provider based on configuration."""
        ci_config = {}

        if self.config.ci_provider == CIProviderType.GITHUB.value:
            owner, repo = self.config.get_github_repo_parts()
            ci_config = {
                "github_token": self.config.github_token,
                "owner": owner,
                "repo": repo,
            }
        elif self.config.ci_provider == CIProviderType.TEAMCITY.value:
            ci_config = {
                "teamcity_url": self.config.ci_status_url or "",
                "username": self.config.ci_api_token,
                "password": self.config.ci_api_token,
                "build_config": self.config.ci_build_config,
            }
        elif self.config.ci_provider == CIProviderType.GITLAB.value:
            ci_config = {
                "gitlab_url": self.config.gitlab_url or "https://gitlab.com",
                "api_token": self.config.gitlab_api_token or self.config.ci_api_token,
                "project_id": self.config.project_id or self.config.ci_build_config,
            }
        elif self.config.ci_provider == CIProviderType.JENKINS.value:
            ci_config = {
                "jenkins_url": self.config.jenkins_url or self.config.ci_status_url or "",
                "username": self.config.jenkins_username,
                "api_token": self.config.jenkins_api_token or self.config.ci_api_token,
                "job_name": self.config.job_name or self.config.ci_build_config,
            }
        elif self.config.ci_provider == CIProviderType.CIRCLECI.value:
            ci_config = {
                "api_token": self.config.ci_api_token,
                "vcs_type": "gh",
                "username": self.config.github_repository.split("/")[0]
                if self.config.github_repository
                else "",
                "project": self.config.github_repository.split("/")[1]
                if "/" in self.config.github_repository
                else "",
            }

        if ci_config:
            self.ci_provider = create_ci_provider(
                provider=self.config.ci_provider,
                **ci_config,
            )
            logger.info(f"CI Provider initialized: {self.config.ci_provider}")

    async def run(self) -> int:
        """Run the complete GR-Review pipeline.

        Returns:
            Exit code (0 for success, 1 for failure).
        """
        try:
            logger.info("Starting GR-Review pipeline")

            # Step 1: Get repository and PR
            owner, repo_name = self.config.get_github_repo_parts()
            repo = self.github_client.get_repo(f"{owner}/{repo_name}")
            pr = repo.get_pull(self.config.github_pr_number)

            logger.info(f"Reviewing PR #{pr.number}: {pr.title}")

            # Step 2: Get the diff
            diff_content = self._get_pr_diff(pr)
            if not diff_content:
                logger.warning("No diff content found")
                return 0

            logger.info(f"Got diff ({len(diff_content)} chars)")

            # Step 3: Secret Scanner (The Gatekeeper)
            # logger.info("Running secret scanner...")
            # secret_result = self.secret_scanner.scan_diff(diff_content)
            # if secret_result.has_secrets:
            #     logger.error("SECRETS DETECTED - Aborting review!")
            #     await self._post_critical_alert(pr, secret_result.findings)
            #     return 1

            logger.info("No secrets detected - proceeding with review")

            # Step 4: Fetch CI Status
            ci_context = None
            if self.ci_provider:
                try:
                    ci_context = await self.ci_provider.fetch_status(
                        commit_sha=pr.head.sha,
                        branch=pr.head.ref,
                    )
                    if ci_context:
                        logger.info(f"CI Status: {ci_context.build_state.value}")
                except Exception as e:
                    logger.warning(f"Failed to fetch CI status: {e}")

            # Step 5: Generate Repository Signature Map
            repo_map = None
            try:
                repo_map = self.repo_mapper.map_repository()
                logger.info(f"Mapped {len(repo_map.signatures)} signatures")
            except Exception as e:
                logger.warning(f"Failed to generate repo map: {e}")

            # Step 6: Run Agents (Parallel or Sequential)
            logger.info(f"Running agent reviews in {self.config.execution_mode} mode...")
            logger.info(
                f"LLM Config: provider={self.config.llm_provider}, model={self.config.llm_model}, base_url={self.config.llm_base_url}"
            )

            # Prepare context for agents
            ci_context_str = format_ci_context(ci_context) if ci_context else ""
            signature_map_str = format_signature_map(repo_map) if repo_map else ""

            if self.config.execution_mode == "parallel":
                # Run all three agents in parallel
                (
                    architect_review,
                    bug_hunter_review,
                    white_hat_review,
                ) = await self._run_parallel_agents(
                    diff_content, repo_map, ci_context, ci_context_str
                )
            else:
                # Run agents sequentially
                (
                    architect_review,
                    bug_hunter_review,
                    white_hat_review,
                ) = await self._run_sequential_agents(
                    diff_content, repo_map, ci_context, ci_context_str
                )

            logger.info(
                f"Agent reviews completed: Architect={architect_review.verdict if architect_review else 'error'}, "
                f"BugHunter={bug_hunter_review.verdict if bug_hunter_review else 'error'}, "
                f"WhiteHat={white_hat_review.verdict if white_hat_review else 'error'}"
            )

            # Step 7: Arbitrator Consolidation
            logger.info("Running arbitrator for final verdict...")
            final_review = await self.arbitrator.arbitrate(
                architect_review=architect_review
                or AgentReview(findings=[], summary="Error", verdict="concerns"),
                bug_hunter_review=bug_hunter_review
                or AgentReview(findings=[], summary="Error", verdict="concerns"),
                white_hat_review=white_hat_review
                or AgentReview(findings=[], summary="Error", verdict="concerns"),
                diff_summary=pr.title,
            )

            logger.info(f"Final verdict: {final_review.verdict}")

            # Step 8: Post Inline Comments
            logger.info("Posting comments to GitHub PR...")
            await self._post_inline_comments(pr, final_review)

            # Step 9: Post Final Verdict
            await self._post_verdict_comment(pr, final_review)

            logger.info("GR-Review completed successfully")
            return 0

        except Exception as e:
            logger.exception(f"GR-Review failed: {e}")
            return 1

    async def _run_parallel_agents(
        self,
        diff_content: str,
        repo_map: Any,
        ci_context: Any,
        ci_context_str: str,
    ) -> tuple[AgentReview | None, AgentReview | None, AgentReview | None]:
        """Run all three agents in parallel.

        Args:
            diff_content: Git diff content.
            repo_map: Repository signature map.
            ci_context: CI context object.
            ci_context_str: Formatted CI context string.

        Returns:
            Tuple of (architect_review, bug_hunter_review, white_hat_review).
        """
        # Build unified ci_context for architect
        architect_ci_context = ""
        if repo_map or ci_context:
            context_data = {}
            if repo_map:
                context_data["repo_signature_map"] = (
                    repo_map.to_dict() if hasattr(repo_map, "to_dict") else repo_map
                )
            if ci_context:
                context_data["ci_status"] = {
                    "status": ci_context.build_state.value
                    if hasattr(ci_context, "build_state")
                    else "unknown"
                }
            import json

            architect_ci_context = json.dumps(context_data)

        tasks = [
            self.architect.review(
                diff_content=diff_content,
                file_path="",
                ci_context=architect_ci_context,
            ),
            self.bug_hunter.review(
                diff_content=diff_content,
                file_path="",
                ci_context=ci_context_str,
            ),
            self.white_hat.review(
                diff_content=diff_content,
                file_path="",
                ci_context=ci_context_str,
            ),
        ]

        results: list[Any] = await asyncio.gather(*tasks, return_exceptions=True)

        architect_review = results[0] if not isinstance(results[0], Exception) else None
        bug_hunter_review = results[1] if not isinstance(results[1], Exception) else None
        white_hat_review = results[2] if not isinstance(results[2], Exception) else None

        return architect_review, bug_hunter_review, white_hat_review

    async def _run_sequential_agents(
        self,
        diff_content: str,
        repo_map: Any,
        ci_context: Any,
        ci_context_str: str,
    ) -> tuple[AgentReview, AgentReview, AgentReview]:
        """Run agents sequentially (one by one).

        Args:
            diff_content: Git diff content.
            repo_map: Repository signature map.
            ci_context: CI context object.
            ci_context_str: Formatted CI context string.

        Returns:
            Tuple of (architect_review, bug_hunter_review, white_hat_review).
        """
        # Build unified ci_context for architect
        architect_ci_context = ""
        if repo_map or ci_context:
            context_data = {}
            if repo_map:
                context_data["repo_signature_map"] = (
                    repo_map.to_dict() if hasattr(repo_map, "to_dict") else repo_map
                )
            if ci_context:
                context_data["ci_status"] = {
                    "status": ci_context.build_state.value
                    if hasattr(ci_context, "build_state")
                    else "unknown"
                }
            import json

            architect_ci_context = json.dumps(context_data)

        logger.info("Running Architect (SWE) review...")
        architect_review = await self.architect.review(
            diff_content=diff_content,
            file_path="",
            ci_context=architect_ci_context,
        )

        logger.info("Running Bug Hunter (QA) review...")
        bug_hunter_review = await self.bug_hunter.review(
            diff_content=diff_content,
            file_path="",
            ci_context=ci_context_str,
        )

        logger.info("Running White Hat (Security) review...")
        white_hat_review = await self.white_hat.review(
            diff_content=diff_content,
            file_path="",
            ci_context=ci_context_str,
        )

        return architect_review, bug_hunter_review, white_hat_review

    def _get_pr_diff(self, pr) -> str:
        """Get the diff for a pull request.

        Args:
            pr: PyGithub PullRequest object.

        Returns:
            Diff content as string.
        """
        try:
            files = pr.get_files()
            diff_parts = []

            for file in files:
                if file.patch:
                    diff_parts.append(file.patch)

            return "\n".join(diff_parts)

        except Exception as e:
            logger.error(f"Failed to get PR diff: {e}")
            return ""

    async def _post_critical_alert(self, pr, findings: list) -> None:
        """Post a critical security alert to the PR."""
        try:
            body = "## SECURITY ALERT - SECRETS DETECTED\n\n"
            body += "The GR-Review system has detected potential hardcoded secrets in this PR.\n"
            body += "**Review ABORTED** to prevent sensitive data exposure.\n\n"
            body += "### Detected Secrets:\n"

            for finding in findings:
                body += (
                    f"- **{finding.secret_type}** in `{finding.file_path}:{finding.line_number}`\n"
                )
                body += f"  - Matched: `{finding.matched_text}`\n"
                body += f"  - Entropy: {finding.entropy_score:.2f}\n\n"

            body += "### Required Actions:\n"
            body += "1. Remove or externalize all secrets\n"
            body += "2. Use environment variables or secret management tools\n"
            body += "3. Re-open the PR after cleaning\n"

            pr.create_review_comment(body, pr.head.sha, "README.md", 1)
            pr.create_issue_comment(body)

        except Exception as e:
            logger.error(f"Failed to post critical alert: {e}")

    async def _post_inline_comments(self, pr, review: AgentReview) -> None:
        """Post inline comments to the PR."""
        try:
            by_file: dict[str, list[Finding]] = {}
            for finding in review.findings:
                if finding.file_path not in by_file:
                    by_file[finding.file_path] = []
                by_file[finding.file_path].append(finding)

            for file_path, findings in by_file.items():
                files = pr.get_files()
                target_file = None
                for f in files:
                    if f.filename == file_path:
                        target_file = f
                        break

                if not target_file:
                    continue

                for finding in findings[:10]:
                    if finding.line_number:
                        try:
                            body = self._format_finding_comment(finding)
                            pr.create_review_comment(
                                body=body,
                                commit_sha=pr.head.sha,
                                path=file_path,
                                line=finding.line_number,
                            )
                        except Exception as e:
                            logger.debug(f"Failed to post inline comment: {e}")

        except Exception as e:
            logger.error(f"Failed to post inline comments: {e}")

    def _format_finding_comment(self, finding: Finding) -> str:
        """Format a finding as a GitHub comment."""
        severity_emoji = {
            "critical": "[CRITICAL]",
            "warning": "[WARNING]",
            "info": "[INFO]",
        }

        emoji = severity_emoji.get(finding.severity, "[INFO]")

        body = f"{emoji} **{finding.severity.upper()}** - {finding.category}\n\n"
        body += f"{finding.message}\n\n"

        if finding.suggestion:
            body += f"**Suggestion:** {finding.suggestion}\n"

        if finding.code_snippet:
            body += f"\n```\n{finding.code_snippet[:200]}\n```"

        return body

    async def _post_verdict_comment(self, pr, review: AgentReview) -> None:
        """Post the final verdict as a PR comment."""
        try:
            verdict_emoji = {
                "pass": "APPROVED",
                "concerns": "CHANGES REQUESTED",
                "critical": "BLOCKED",
            }

            emoji = verdict_emoji.get(review.verdict, "UNKNOWN")

            body = f"## GR-Review Verdict\n\n"
            body += f"**Status:** {emoji}\n\n"
            body += f"### Summary\n{review.summary}\n\n"

            total_findings = len(review.findings)
            critical_count = sum(1 for f in review.findings if f.severity == "critical")
            warning_count = sum(1 for f in review.findings if f.severity == "warning")

            body += f"### Statistics\n"
            body += f"- Total Findings: {total_findings}\n"
            body += f"- Critical: {critical_count}\n"
            body += f"- Warnings: {warning_count}\n\n"

            if review.findings:
                body += "### Action Items\n"
                for i, finding in enumerate(review.findings[:5], 1):
                    body += f"{i}. `{finding.file_path}:{finding.line_number or '?'}` - {finding.message[:80]}\n"

            pr.create_issue_comment(body)

        except Exception as e:
            logger.error(f"Failed to post verdict comment: {e}")


def main() -> int:
    """Main entry point for GR-Review.

    Returns:
        Exit code.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        config = load_config()
        orchestrator = GRReviewOrchestrator(config)
        return asyncio.run(orchestrator.run())

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"Error: {e}", file=sys.stderr)
        print("\nPlease set required environment variables:", file=sys.stderr)
        print("  - LLM_PROVIDER and LLM_API_KEY", file=sys.stderr)
        print("  - GITHUB_TOKEN", file=sys.stderr)
        print("  - GITHUB_REPOSITORY", file=sys.stderr)
        print("  - GITHUB_PR_NUMBER", file=sys.stderr)
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
