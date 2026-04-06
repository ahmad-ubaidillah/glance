"""GitHub Client - PyGithub wrapper for PR operations.

Handles PR diff retrieval, inline comments, and status checks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from github import Github, PullRequest, Repository
from github.PullRequestComment import PullRequestComment

logger = logging.getLogger("glance.github")


@dataclass
class PRInfo:
    """Basic PR information."""

    number: int
    title: str
    author: str
    base_branch: str
    head_branch: str
    state: str
    draft: bool


class GitHubClient:
    """Wrapper for GitHub API operations.

    Provides clean interface for:
    - Fetching PR details and diffs
    - Posting inline comments
    - Setting PR status checks
    - Managing review comments
    """

    def __init__(self, token: str, repository: str):
        """Initialize the GitHub client.

        Args:
            token: GitHub personal access token.
            repository: Repository in "owner/repo" format.
        """
        self.client = Github(token)
        self.repo_name = repository
        self._repo: Repository | None = None
        self._pr: PullRequest | None = None

    @property
    def repo(self) -> Repository:
        """Lazy-load repository."""
        if self._repo is None:
            self._repo = self.client.get_repo(self.repo_name)
        return self._repo

    def get_pr(self, pr_number: int) -> PullRequest:
        """Get a pull request by number.

        Args:
            pr_number: Pull request number.

        Returns:
            PullRequest object.
        """
        if self._pr is None or self._pr.number != pr_number:
            self._pr = self.repo.get_pull(pr_number)
        return self._pr

    def get_pr_info(self, pr_number: int) -> PRInfo:
        """Get basic PR information.

        Args:
            pr_number: Pull request number.

        Returns:
            PRInfo with basic details.
        """
        pr = self.get_pr(pr_number)
        return PRInfo(
            number=pr.number,
            title=pr.title,
            author=pr.user.login if pr.user else "unknown",
            base_branch=pr.base.ref if pr.base else "unknown",
            head_branch=pr.head.ref if pr.head else "unknown",
            state=pr.state,
            draft=pr.draft,
        )

    def get_pr_diff(self, pr_number: int) -> str:
        """Get the full diff of a pull request.

        Args:
            pr_number: Pull request number.

        Returns:
            Git diff string.
        """
        pr = self.get_pr(pr_number)
        # Get diff format
        headers = {"Accept": "application/vnd.github.v3.diff"}
        return str(pr.get_files())

    def get_changed_files(self, pr_number: int) -> list[str]:
        """Get list of changed file paths.

        Args:
            pr_number: Pull request number.

        Returns:
            List of file paths changed in the PR.
        """
        pr = self.get_pr(pr_number)
        return [f.filename for f in pr.get_files()]

    def get_file_diff(self, pr_number: int, file_path: str) -> str | None:
        """Get diff for a specific file.

        Args:
            pr_number: Pull request number.
            file_path: Path to the file.

        Returns:
            Diff string for the file, or None if not found.
        """
        pr = self.get_pr(pr_number)
        for file in pr.get_files():
            if file.filename == file_path:
                return file.patch
        return None

    def get_file_content(self, file_path: str, ref: str = "HEAD") -> str | None:
        """Get the content of a file at a specific ref.

        Args:
            file_path: Path to the file.
            ref: Git ref (branch, commit, or HEAD).

        Returns:
            File content or None if not found.
        """
        try:
            content_file = self.repo.get_contents(file_path, ref=ref)
            if isinstance(content_file, list):
                return None
            return content_file.decoded_content.decode("utf-8")
        except Exception as e:
            logger.warning(f"Failed to get file content: {e}")
            return None

    def post_inline_comment(
        self,
        pr_number: int,
        file_path: str,
        line_number: int,
        body: str,
        side: str = "RIGHT",
    ) -> PullRequestComment | None:
        """Post an inline comment on a PR.

        Args:
            pr_number: Pull request number.
            file_path: Path to the file to comment on.
            line_number: Line number for the comment.
            body: Comment text.
            side: Side of the diff (LEFT for old, RIGHT for new).

        Returns:
            The created comment or None on failure.
        """
        try:
            pr = self.get_pr(pr_number)

            # Get the latest commit on the PR
            commit_id = pr.head.sha

            comment = pr.create_review_comment(
                body=body,
                path=file_path,
                line=line_number,
                side=side,
                commit_id=commit_id,
            )

            logger.info(f"Posted comment on {file_path}:{line_number}")
            return comment

        except Exception as e:
            logger.error(f"Failed to post inline comment: {e}")
            return None

    def post_review_comment(
        self,
        pr_number: int,
        body: str,
        event: str = "COMMENT",
        comments: list[dict] | None = None,
    ) -> bool:
        """Post a review comment on a PR.

        Args:
            pr_number: Pull request number.
            body: Review summary text.
            event: Review event type (COMMENT, APPROVE, REQUEST_CHANGES).
            comments: List of inline comments with path, line, body.

        Returns:
            True if successful.
        """
        try:
            pr = self.get_pr(pr_number)
            commit_id = pr.head.sha

            pr.create_review(
                body=body,
                event=event,
                comments=comments or [],
                commit_id=commit_id,
            )

            logger.info(f"Posted review on PR #{pr_number}")
            return True

        except Exception as e:
            logger.error(f"Failed to post review: {e}")
            return False

    def create_issue_comment(self, pr_number: int, body: str) -> bool:
        """Create a general comment on a PR (issue comment).

        Args:
            pr_number: Pull request number.
            body: Comment text.

        Returns:
            True if successful.
        """
        try:
            pr = self.get_pr(pr_number)
            pr.create_issue_comment(body)
            logger.info(f"Posted issue comment on PR #{pr_number}")
            return True
        except Exception as e:
            logger.error(f"Failed to create issue comment: {e}")
            return False

    def get_combined_status(self, pr_number: int) -> dict:
        """Get combined CI status for a PR.

        Args:
            pr_number: Pull request number.

        Returns:
            Dict with status summary.
        """
        pr = self.get_pr(pr_number)
        commit = pr.get_commits().reversed[0]  # Latest commit

        status_list = list(commit.get_statuses())

        statuses = {}
        for status in status_list:
            contexts = status.context or "unknown"
            statuses[contexts] = {
                "state": status.state,
                "description": status.description,
                "target_url": status.target_url,
            }

        # Get check runs as well (GitHub Actions)
        check_runs = list(commit.get_check_runs())

        for run in check_runs:
            statuses[run.name] = {
                "state": run.status,
                "conclusion": run.conclusion,
                "html_url": run.html_url,
            }

        return {
            "sha": commit.sha,
            "statuses": statuses,
            "total": len(statuses),
            "failed": sum(1 for s in statuses.values() if s.get("state") == "failure"),
            "pending": sum(1 for s in statuses.values() if s.get("state") == "pending"),
            "success": sum(1 for s in statuses.values() if s.get("state") == "success"),
        }

    def set_status(
        self,
        pr_number: int,
        state: str,
        description: str,
        context: str = "glance",
        target_url: str | None = None,
    ) -> bool:
        """Set a commit status.

        Args:
            pr_number: Pull request number.
            state: Status state (pending, success, failure, error).
            description: Status description.
            context: Status context name.
            target_url: Optional URL for details.

        Returns:
            True if successful.
        """
        try:
            pr = self.get_pr(pr_number)
            commit = pr.get_commits().reversed[0]

            commit.create_status(
                state=state,
                description=description,
                context=context,
                target_url=target_url,
            )

            logger.info(f"Set status '{state}' for PR #{pr_number}")
            return True

        except Exception as e:
            logger.error(f"Failed to set status: {e}")
            return False


def create_client(token: str, repository: str) -> GitHubClient:
    """Convenience function to create a GitHub client.

    Args:
        token: GitHub token.
        repository: Repository in owner/repo format.

    Returns:
        GitHubClient instance.
    """
    return GitHubClient(token, repository)
