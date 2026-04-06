# Glance: AI-Powered Code Review System

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.10+-green" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-orange" alt="License">
</p>

Glance is an automated AI code review system that acts as a virtual Tech Lead. It analyzes GitHub/GitLab Pull Requests using multi-agent architecture.

## Why Glance?

| Feature | Benefit |
|---------|---------|
| **1-Line Install** | No server, no setup - just install and run |
| **Self-Hosted on CI** | Runs on your existing GitHub Actions / GitLab CI |
| **Adaptive** | Smart agent selection - runs more agents for complex PRs |
| **Token Efficient** | Only critical issues get inline comments |
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

After installation, edit your workflow file (usually `.github/workflows/glance.yml` or `.github/workflows/ci.yml`):

```yaml
- name: Run Glance
  env:
    # === CHANGE THESE ===
    LLM_PROVIDER: zhipuai      # openai, anthropic, google, zhipuai, ollama
    LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
    LLM_MODEL: glm-5           # model name for your provider
    LLM_BASE_URL: https://api.z.ai/api/coding/paas/v4
    # ======================
    GIT_TOKEN: ${{ secrets.GIT_TOKEN }}
    GITHUB_REPOSITORY: ${{ github.repository }}
    GITHUB_PR_NUMBER: ${{ github.event.pull_request.number }}
  run: python -c "from glance.orchestrator import main; main()"
```

---

## Supported LLM Providers

| Provider | Model Example | API Key Secret |
|----------|---------------|----------------|
| **ZhipuAI** (recommended) | glm-4-flash, glm-5 | `ZHIPUAI_API_KEY` |
| OpenAI | gpt-4, gpt-3.5-turbo | `OPENAI_API_KEY` |
| Anthropic | claude-3-opus, claude-3-sonnet | `ANTHROPIC_API_KEY` |
| Google | gemini-pro, gemini-ultra | `GOOGLE_API_KEY` |

---

## Example Output

Glance posts to your PR:

### Verdict Comment (on PR)
```markdown
## 🤖 Glance Code Review

### Verdict: 🛑 BLOCKED

**Summary:** @author This PR has 2 critical security issues...

### 📊 Statistics
| Severity | Count |
|----------|-------|
| 🔴 Critical | 2 |
| 🟡 Warning | 1 |

### ⚠️ Warnings (Should Fix)
1. `app.py:50` - Missing null check
   └─ 💡 Fix: Add validation
```

### Inline Comments (on code)
```
🔴 CRITICAL at line 42
Authentication is broken - only checks header exists...
💡 Fix: Implement proper token validation
```

**Smart Commenting:**
- **Inline comments**: Only for Critical + Medium issues (at specific lines)
- **PR comment**: Summary + Warnings only (no duplicates)

---

## Architecture

```
PR Diff → Adaptive Router → Selected Agents (Architect, BugHunter, WhiteHat)
                                      ↓
                              Arbitrator (consolidate)
                                      ↓
                              Final Verdict → GitHub Comment + Inline
```

**Adaptive Routing:**
| PR Type | Complexity | Agents |
|---------|------------|--------|
| <20 lines | Simple | Architect |
| 2-5 files | Medium | Architect + BugHunter |
| 10+ files | Complex | All 4 agents |

---

## Customization

### Edit Agent Prompts
Edit files in `prompts/` directory:
- `architect.md` - Software Engineering
- `bug_hunter.md` - QA & Bug Detection  
- `white_hat.md` - Security
- `arbitrator.md` - Final Verdict

---

## License

MIT License