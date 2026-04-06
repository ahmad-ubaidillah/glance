"""Arbitrator Agent - Lead Developer for final verdict consolidation.

Takes findings from all agents and produces a consolidated, noise-reduced report.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from glance.agents.base import AgentReview, BaseAgent, Finding, GlanceConfig

logger = logging.getLogger("glance.arbitrator")


class ArbitratorAgent(BaseAgent):
    """Lead Developer Agent that consolidates all agent findings.

    This agent:
    - Receives findings from Architect, BugHunter, and WhiteHat
    - Filters noise and nitpicks
    - Resolves conflicts between agent opinions
    - Produces final verdict: APPROVE, REQUEST_CHANGES, or BLOCK_SECURITY
    """

    @property
    def agent_name(self) -> str:
        """Return the agent identifier."""
        return "Arbitrator"

    @property
    def system_prompt(self) -> str:
        """Return the arbitrator system prompt."""
        return """You are The Arbitrator, a senior lead developer who consolidates code review findings.

YOUR ROLE:
1. Review findings from multiple specialized agents
2. Filter out noise: nitpicks, style preferences, false positives
3. Identify genuine issues that need attention
4. Resolve conflicts between agent opinions
5. Provide a final verdict and action items

FILTERING GUIDELINES:
- Remove purely stylistic comments that don't affect functionality
- Combine duplicate findings from different agents
- Prioritize by severity: security > bugs > code quality
- Dismiss findings that are clearly false positives
- Keep findings that multiple agents agree on

VERDICT RULES:
- APPROVE: No significant issues, or only minor improvements suggested
- REQUEST_CHANGES: Issues found that should be addressed before merge
- BLOCK_SECURITY: Critical security vulnerability found (secrets, exploits)

OUTPUT FORMAT (JSON):
{
  "findings": [
    {
      "file_path": "path/to/file.py",
      "line_number": 42,
      "severity": "warning",
      "category": "bug",
      "message": "Consolidated issue description",
      "suggestion": "Recommended fix",
      "code_snippet": "relevant code"
    }
  ],
  "summary": "Executive summary for the PR author",
  "verdict": "pass|concerns|critical"
}

IMPORTANT RULES:
1. If WhiteHat found critical security issues, verdict MUST be "critical"
2. If any agent found critical bugs, verdict should be "concerns" at minimum
3. Be concise - authors shouldn't have to read 50 comments
4. Group related findings when possible
5. Provide actionable, clear suggestions"""

    async def arbitrate(
        self,
        architect_review: AgentReview,
        bug_hunter_review: AgentReview,
        white_hat_review: AgentReview,
        diff_summary: str = "",
    ) -> AgentReview:
        """Consolidate all agent reviews into a final verdict.

        Args:
            architect_review: Review from The Architect (SWE agent).
            bug_hunter_review: Review from The Bug Hunter (QA agent).
            white_hat_review: Review from The White Hat (Security agent).
            diff_summary: Optional summary of the changes being reviewed.

        Returns:
            Consolidated AgentReview with final verdict.
        """
        # Build consolidation prompt
        user_prompt = self._build_consolidation_prompt(
            architect_review, bug_hunter_review, white_hat_review, diff_summary
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            content = (
                response.choices[0].message.content
                if not isinstance(response, dict)
                else response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            if content is None:
                return self._fallback_consolidation(
                    architect_review, bug_hunter_review, white_hat_review
                )

            return self._parse_response(content)

        except Exception as e:
            logger.error(f"Arbitrator: Error in arbitrate: {e}")
            # Fallback to rule-based consolidation if LLM fails
            return self._fallback_consolidation(
                architect_review, bug_hunter_review, white_hat_review
            )

    def _build_consolidation_prompt(
        self,
        architect: AgentReview,
        bug_hunter: AgentReview,
        white_hat: AgentReview,
        diff_summary: str,
    ) -> str:
        """Build prompt with all agent findings."""
        prompt = "CONSOLIDATE THE FOLLOWING AGENT REVIEWS:\n\n"

        if diff_summary:
            prompt += f"DIFF SUMMARY:\n{diff_summary}\n\n"

        prompt += "=== THE ARCHITECT (SWE Agent) ===\n"
        prompt += f"Verdict: {architect.verdict}\n"
        prompt += f"Summary: {architect.summary}\n"
        prompt += (
            f"Findings: {json.dumps([f.model_dump() for f in architect.findings], indent=2)}\n\n"
        )

        prompt += "=== THE BUG HUNTER (QA Agent) ===\n"
        prompt += f"Verdict: {bug_hunter.verdict}\n"
        prompt += f"Summary: {bug_hunter.summary}\n"
        prompt += (
            f"Findings: {json.dumps([f.model_dump() for f in bug_hunter.findings], indent=2)}\n\n"
        )

        prompt += "=== THE WHITE HAT (Security Agent) ===\n"
        prompt += f"Verdict: {white_hat.verdict}\n"
        prompt += f"Summary: {white_hat.summary}\n"
        prompt += (
            f"Findings: {json.dumps([f.model_dump() for f in white_hat.findings], indent=2)}\n\n"
        )

        prompt += "Provide a consolidated review with final verdict (pass/concerns/critical)."
        return prompt

    def _fallback_consolidation(
        self,
        architect: AgentReview,
        bug_hunter: AgentReview,
        white_hat: AgentReview,
    ) -> AgentReview:
        """Rule-based fallback consolidation when LLM fails."""
        all_findings: list[Finding] = []

        # Collect all findings
        all_findings.extend(architect.findings)
        all_findings.extend(bug_hunter.findings)
        all_findings.extend(white_hat.findings)

        # Determine verdict based on individual verdicts
        if white_hat.verdict == "critical":
            final_verdict = "critical"
            summary = "SECURITY ISSUE: Critical security vulnerability detected. PR blocked for security review."
        elif bug_hunter.verdict == "critical":
            final_verdict = "concerns"
            summary = "Critical bugs found that should be addressed before merge."
        elif white_hat.verdict == "concerns" or bug_hunter.verdict == "concerns":
            final_verdict = "concerns"
            summary = "Issues found that should be reviewed."
        else:
            final_verdict = architect.verdict
            summary = architect.summary

        return AgentReview(
            findings=all_findings,
            summary=summary,
            verdict=final_verdict,
        )

    async def review(
        self, diff_content: str, file_path: str = "", ci_context: str = ""
    ) -> AgentReview:
        """Not used for Arbitrator - use arbitrate() instead."""
        raise NotImplementedError("Arbitrator uses arbitrate() method, not review()")
