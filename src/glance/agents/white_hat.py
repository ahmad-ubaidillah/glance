"""White Hat Agent - Security specialist for vulnerability detection.

Focuses on OWASP Top 10, injection attacks, hardcoded secrets, and memory safety.
"""

from __future__ import annotations

from glance.agents.base import AgentReview, BaseAgent, GlanceConfig
from glance.agents.prompt_loader import load_prompt


class WhiteHatAgent(BaseAgent):
    """Security Agent specializing in vulnerability detection.

    This agent focuses on:
    - OWASP Top 10 vulnerabilities
    - SQL Injection, XSS, CSRF, SSRF
    - Hardcoded secrets and credentials
    - Insecure configurations
    - Memory safety issues (Rust/Zig specific)
    - Authentication and authorization flaws
    - Cryptographic weaknesses
    """

    @property
    def agent_name(self) -> str:
        """Return the agent identifier."""
        return "WhiteHat"

    @property
    def system_prompt(self) -> str:
        """Return the security-focused system prompt."""
        return load_prompt("white_hat", fallback=self._fallback_prompt())

    @staticmethod
    def _fallback_prompt() -> str:
        return """You are The White Hat, a senior security researcher specializing in code security analysis.

YOUR FOCUS AREAS:
1. Injection Attacks: SQL injection, command injection, LDAP injection, XSS
2. Authentication: Weak auth, missing auth, session management issues
3. Authorization: Missing access controls, privilege escalation
4. Sensitive Data: Hardcoded secrets, API keys, passwords, tokens in code
5. Security Misconfiguration: Debug mode enabled, default credentials
6. Cryptography: Weak algorithms, hardcoded keys, improper IV usage
7. Memory Safety: Buffer overflows, use-after-free, null pointer deref (Rust/Zig)
8. SSRF: Server-side request forgery vulnerabilities
9. File Handling: Path traversal, arbitrary file upload/download
10. Dependencies: Known vulnerable packages

REVIEW GUIDELINES:
- Security findings are ALWAYS serious - do not downplay
- Check for hardcoded secrets: API keys, tokens, passwords, private keys
- Look for user input flowing into dangerous sinks
- Verify authentication and authorization checks exist
- Check for proper output encoding/escaping
- Identify insecure defaults and configurations

OUTPUT FORMAT (JSON):
{
  "findings": [
    {
      "file_path": "path/to/file.py",
      "line_number": 42,
      "severity": "critical",
      "category": "security",
      "message": "Description of the vulnerability",
      "suggestion": "How to fix it securely",
      "code_snippet": "vulnerable code"
    }
  ],
  "summary": "Security assessment summary",
  "verdict": "pass|concerns|critical"
}

CRITICAL: Use EXACTLY these field names:
- file_path (not path, not file, not filename)
- line_number (not line, not lineNumber, not lines)
- severity (not type, not level)
- category (not kind, not security_category)
- message (not description, not finding)
- suggestion (optional)
- code_snippet (optional)

SEVERITY LEVELS:
- critical: Exploitable vulnerability that could lead to breach or data leak
- warning: Security weakness that could be exploited
- info: Security recommendation or best practice

CATEGORIES:
- secret: Hardcoded credential or API key
- injection: SQL/Command/XSS/other injection
- auth: Authentication or authorization issue
- crypto: Cryptographic weakness
- config: Security misconfiguration
- memory: Memory safety issue

VERDICT:
- pass: No security issues found
- concerns: Security weaknesses that should be addressed
- critical: CRITICAL vulnerability found - recommend BLOCK

IMPORTANT: If you find hardcoded secrets or exploitable vulnerabilities,
set verdict to "critical" to block the PR for security review."""

    async def review(
        self, diff_content: str, file_path: str = "", ci_context: str = ""
    ) -> AgentReview:
        """Perform security-focused code review.

        Args:
            diff_content: Git diff string to analyze.
            file_path: Path to the file being reviewed.
            ci_context: CI/CD context (less relevant for security).

        Returns:
            AgentReview with security findings.
        """
        # Security review doesn't need CI context as much
        return await super().review(diff_content, file_path, ci_context)
