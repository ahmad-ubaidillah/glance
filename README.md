# Glance: AI-Powered Code Review System

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.10+-green" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-orange" alt="License">
</p>

Glance is an automated AI code review system that acts as a virtual Tech Lead. It analyzes GitHub/GitLab Pull Requests using multi-agent architecture with persistent memory and self-learning capabilities.

## Why Glance?

| Feature | Benefit |
|---------|---------|
| **1-Line Install** | No server, no setup - just install and run |
| **Self-Hosted on CI** | Runs on your existing GitHub Actions / GitLab CI |
| **Adaptive** | Smart agent selection - runs more agents for complex PRs |
| **Self-Learning** | Remembers developer patterns, recurring issues, proven fixes |
| **Auto-Fix** | Generates actual code patches for critical issues |
| **Interactive TUI** | Configure everything from a beautiful dashboard |
| **Multi-Provider** | Works with ZhipuAI, OpenAI, Anthropic, Google, Azure |

## Quick Start (3 Steps)

### Step 1: Install

```bash
curl -sSL https://raw.githubusercontent.com/ahmad-ubaidillah/glance/main/install.sh | bash
```

### Step 2: Add 2 Secrets

Go to **Repository → Settings → Secrets and variables → Actions**

| Secret | Value |
|--------|-------|
| `LLM_API_KEY` | Your LLM API key (ZhipuAI, OpenAI, etc) |
| `GIT_TOKEN` | Git provider token with repo write access |

### Step 3: Run

Push a PR - Glance automatically reviews it!

---

## Configuration

### Via Workflow File

Edit `.github/workflows/glance.yml` (or `ci.yml`):

```yaml
- name: Run Glance
  env:
    # === CHANGE THESE ===
    LLM_PROVIDER: zhipuai
    LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
    LLM_MODEL: glm-5
    LLM_BASE_URL: https://api.z.ai/api/coding/paas/v4
    # ======================
    GIT_TOKEN: ${{ secrets.GIT_TOKEN }}
    GITHUB_REPOSITORY: ${{ github.repository }}
    GITHUB_PR_NUMBER: ${{ github.event.pull_request.number }}
  run: python -c "from glance.orchestrator import main; main()"
```

### Via Interactive TUI Dashboard

```bash
glance dashboard
```

The TUI lets you:
- View review statistics
- Check token costs
- Inspect memory & developer profiles
- Configure LLM provider, model, execution mode, routing
- Manage custom team rules
- Read the setup guide
- Run reviews directly

---

## Supported LLM Providers

| Provider | Model Example | API Key Secret |
|----------|---------------|----------------|
| **ZhipuAI** (recommended) | glm-4-flash, glm-5 | `ZHIPUAI_API_KEY` |
| OpenAI | gpt-4, gpt-3.5-turbo | `OPENAI_API_KEY` |
| Anthropic | claude-3-opus, claude-3-sonnet | `ANTHROPIC_API_KEY` |
| Google | gemini-pro, gemini-ultra | `GOOGLE_API_KEY` |
| Azure OpenAI | (deployment name) | `AZURE_OPENAI_API_KEY` |
| Ollama | llama2, mistral (local) | None |

---

## Example Output

### Inline Comments (on code lines)
```
🔴 CRITICAL at line 42
Authentication is broken - only checks header exists...
💡 Fix: Implement proper token validation
```

### Summary Comment (on PR)
```markdown
## 🤖 Glance Code Review

### Verdict: 🛑 BLOCKED

**Summary:** @author This PR has 2 critical security issues...

### 📊 Statistics
| Severity | Count |
|----------|-------|
| 🔴 Critical | 2 |
| 🟡 Warning | 1 |

_See inline comments on the code for detailed findings._
```

---

## Architecture

```
PR Diff → Adaptive Router → Selected Agents (Architect, BugHunter, WhiteHat)
                                      ↓
                              Arbitrator (consolidate)
                                      ↓
                         Auto-Fix Generator (critical issues)
                                      ↓
                    Inline Comments + Summary + Memory Update
```

### Agent Specialization

| Agent | Focus |
|-------|-------|
| **Architect** | SOLID, DRY, design patterns, file complexity |
| **BugHunter** | Null refs, type errors, race conditions, resource leaks |
| **WhiteHat** | Auth bypass, injection, data exposure, misconfigurations |
| **Arbitrator** | Consolidates findings, determines verdict |

### Adaptive Routing

| PR Type | Complexity | Agents Selected |
|---------|------------|-----------------|
| <20 lines | Simple | Architect |
| 2-5 files | Medium | Architect + BugHunter |
| 10+ files | Complex | All 4 agents |

---

## Self-Learning Features

### Memory System
- **Developer Profiles** - Tracks common mistakes, strengths, fix quality
- **Issue Patterns** - Recurring problems across branches
- **Lessons Learned** - What fixes worked, what didn't
- Agents read memory BEFORE reviewing

### Review History
- Tracks all findings across PRs
- Detects recurring issues
- Escalates severity for ignored problems

### Test Coverage Detection
- Identifies which files have tests
- Flags untested complex code as higher risk

---

## Auto-Fix Suggestions

For critical issues, Glance generates actual code patches that can be applied directly.

---

## Custom Team Rules

Create `.glance/rules.json`:

```json
{
  "rules": [
    {
      "id": "no-debug",
      "description": "Never allow debug endpoints",
      "action": "escalate",
      "pattern": "debug endpoint",
      "severity": "critical"
    },
    {
      "id": "ignore-generated",
      "description": "Ignore generated files",
      "action": "ignore",
      "pattern": "generated",
      "files": ["*.gen.py", "migrations/*"]
    }
  ]
}
```

---

## CLI Commands

```bash
glance dashboard          # Interactive TUI
glance cost               # Token cost summary
glance memory             # Memory summary
```

---

## Security Best Practices

- **NEVER commit API keys** to version control
- Use GitHub/GitLab Secrets for sensitive values
- Use `GIT_TOKEN` with minimal scope (repo access)
- Rotate API keys regularly

---

## License

MIT License
