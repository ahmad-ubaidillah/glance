# PRD: GR-Review (Git Request Review)
Version: 1.0
Status: Final Draft
Author: Ahmad Ubaidillah (Senior Test Engineer)
Target Platform: GitHub Actions (Self-hosted Logic)

## 1. Executive Summary
GR-Review is an automated, AI-driven code review orchestrator designed to act as a virtual "Tech Lead." It utilizes a multi-agent architecture to analyze GitHub Pull Requests from three distinct perspectives: Software Engineering (Clean Code), Quality Assurance (Logic & Bugs), and Cybersecurity. It integrates seamlessly with existing CI/CD statuses (like TeamCity) to provide context-aware feedback.

## 2. Goals & Objectives
 * Improve Code Quality: Enforce SOLID, DRY, and Clean Code principles automatically.
 * Reduce Review Latency: Provide instant feedback within minutes of a PR being opened.
 * Security First: Detect hardcoded secrets and OWASP vulnerabilities before human review.
 * Cost Efficiency: Use high-performance, low-cost LLMs (e.g., GLM-4-Flash) with smart filtering to minimize token usage.

## 3. Targeted Personas (The Core Engine)
The system operates using four specialized AI agents:

| Agent | Role | Focus Areas |
|---|---|---|
| The Architect (SWE) | Clean Code Expert | SOLID, DRY, Design Patterns, File Complexity (Anti-File Hell). |
| The Bug Hunter (QA) | Logic Specialist | Edge cases, boundary values, error handling, and business logic. |
| The White Hat (Security) | Security Researcher | OWASP Top 10, SQLi, XSS, Memory Safety (Rust/Zig), Hardcoded secrets. |
| The Arbitrator | Lead Developer | Conflict resolution between agents, noise reduction, and final verdict. |

## 4. Functional Requirements

### 4.1. Pre-Execution Phase (The Gatekeeper)
 * Linter Dependency: GR-Review must only trigger if the static Linter (e.g., ESLint, Cargo Check) passes.
 * Security Pre-Scan: Execute a local Regex-based scan to detect high-entropy strings (API Keys, Passwords). If found, the process aborts and issues a critical alert to prevent sending sensitive data to the LLM.

### 4.2. Context Awareness (The Intelligence)
 * CI Status Integration: The system must read the status of TeamCity/CI checks. If the build failed, the QA Agent must prioritize "Root Cause Analysis" (RCA).
 * Signature Mapping: Use universal-ctags or Regex to extract function/class signatures from the entire repository to provide structural context without sending full files.

### 4.3. Review Execution
 * Incremental Review: Only analyze the git diff of the current Pull Request.
 * Multi-Agent Concensus: Run SWE, QA, and Security agents in parallel (Async).
 * Arbitration: The Arbitrator agent filters out "nitpicks" and summarizes findings into a consolidated report.

### 4.4. Reporting
 * Inline Comments: Comments must be posted directly to the relevant files/lines in the GitHub "Files Changed" tab.
 * Final Verdict: The Arbitrator must provide a summary: APPROVE, REQUEST CHANGES, or BLOCK (SECURITY).

## 5. Technical Stack
 * Runtime: Python 3.10+ (GitHub Actions Runner).
 * Orchestrator: GitHub Actions YAML.
 * AI Engine: ZhipuAI (GLM-4-Flash) via API.
 * Parsing Tools: Universal-ctags (for repository mapping).
 * API Client: PyGithub for GitHub REST API interaction.

## 6. System Flow (Logic Sequence)
 1. Trigger: pull_request event (opened or synchronized).
 2. Step 1: Run Linter. If fail → Exit.
 3. Step 2: Run TeamCity Tests.
 4. Step 3: GR-Review starts → Local Regex Secret Scan.
 5. Step 4: Fetch CI Status (TeamCity) via GitHub Combined Status API.
 6. Step 5: Generate Repo Map (Signatures).
 7. Step 6: Parallel LLM Calls (SWE, QA, Security Agents).
 8. Step 7: Arbitrator Agent consolidates reports.
 9. Step 8: Post Inline Comments to GitHub PR.

## 7. Success Metrics
 * False Positive Rate: < 15% (AI suggests valid improvements).
 * Review Speed: Total execution time < 3 minutes.
 * Cost: Average cost per PR < $0.05 (using GLM-4-Flash).

## 8. Future Enhancements
 * Semantic Search (RAG): Using a Vector DB for cross-file dependency awareness.
 * Auto-Fix Suggestions: Automatically generating "Suggested Changes" buttons in GitHub.
 * Historical Learning: Preventing the AI from repeating the same advice on the same PR.

Approval: Ahmad Ubaidillah
*Senior Test Engineer*
