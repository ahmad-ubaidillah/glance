# Glance: AI-Powered Code Review System

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.10+-green" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-orange" alt="License">
</p>

Glance is an automated, AI-driven code review system that acts as a virtual Tech Lead. It analyzes GitHub Pull Requests using multi-agent architecture from three perspectives: Software Engineering (Clean Code), Quality Assurance (Logic & Bugs), and Cybersecurity.

## Features

- **Multi-Agent Architecture**: 4 specialized AI agents (Architect, Bug Hunter, White Hat, Arbitrator)
- **Adaptive Routing**: Smart agent selection based on PR complexity - only runs necessary agents
- **Delta-Based Repo Mapping**: Only scans changed files for better performance
- **GitHub Integration**: Inline comments at specific lines + final verdict with author tagging
- **Smart Output**: Grouped findings by file, severity-sorted, numbered lists
- **Flexible LLM Support**: Works with OpenAI, Anthropic, Google Gemini, ZhipuAI, Azure OpenAI, Ollama
- **Multi-CI Support**: GitHub Actions, GitLab CI, Jenkins, TeamCity, CircleCI, Azure DevOps
- **Security First**: Built-in secret scanning to prevent sensitive data exposure

## Quick Start

### One-Line Installation (Recommended)

```bash
# Via curl
curl -sSL https://raw.githubusercontent.com/ahmad-ubaidillah/glance/main/install.sh | bash

# OR via wget
wget -qO- https://raw.githubusercontent.com/ahmad-ubaidillah/glance/main/install.sh | bash
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/ahmad-ubaidillah/glance.git
cd glance

# Create virtual environment
python3 -m venv venv

# Activate
source venv/bin/activate

# Install
pip install -e .
```

## GitHub Actions Integration

### Step 1: Add GitHub Secrets

Go to **Repository → Settings → Secrets and variables → Actions**, add:

| Secret | Description | Example |
|--------|-------------|---------|
| `LLM_API_KEY` | Your LLM provider API key | Get from ZhipuAI/OpenAI/Anthropic |
| `PAT_TOKEN` | GitHub token with repo write access | Generate with repo scope |

### Step 2: Create Workflow

Create `.github/workflows/glance.yml`:

```yaml
name: Glance AI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install Glance
        run: pip install -e git+https://github.com/ahmad-ubaidillah/glance.git#egg=glance

      - name: Run Glance
        env:
          # === CONFIGURABLE SECTION ===
          # Change these to use different LLM provider/model
          LLM_PROVIDER: zhipuai
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          LLM_MODEL: glm-5
          LLM_BASE_URL: https://api.z.ai/api/coding/paas/v4
          # ============================
          GITHUB_TOKEN: ${{ secrets.PAT_TOKEN || github.token }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          GITHUB_PR_NUMBER: ${{ github.event.pull_request.number }}
        run: |
          python -c "from glance.orchestrator import main; main()" || true
```

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | zhipuai | Provider: openai, anthropic, google, zhipuai, azure_openai, ollama, custom |
| `LLM_MODEL` | glm-5 | Model name (provider-specific) |
| `LLM_BASE_URL` | (provider default) | Custom API endpoint |

## Example Review Output

Glance posts a comprehensive review comment:

```markdown
## 🤖 Glance Code Review

### Verdict: 🛑 BLOCKED

**Summary:** @author This PR introduces 3 critical security issues...

### 📊 Statistics
| Severity | Count |
|----------|-------|
| 🔴 Critical | 3 |
| 🟡 Warning | 2 |

### 📝 Findings by File

**`app.py`**
1. 🔴 `app.py:42` - Security issue description
   └─ 💡 Fix: Suggested fix here
2. 🟡 `app.py:15` - Warning description
   └─ 💡 Fix: Suggested fix here
```

## Supported LLM Providers

| Provider | API Key Variable | Model Example |
|----------|-----------------|---------------|
| ZhipuAI | `ZHIPUAI_API_KEY` | glm-4-flash, glm-5 |
| OpenAI | `OPENAI_API_KEY` | gpt-4, gpt-3.5-turbo |
| Anthropic | `ANTHROPIC_API_KEY` | claude-3-opus, claude-3-sonnet |
| Google | `GOOGLE_API_KEY` | gemini-pro, gemini-ultra |
| Azure OpenAI | `AZURE_OPENAI_API_KEY` | (deployment name) |
| Ollama | (local) | llama2, mistral |

## Adaptive Routing

Glance automatically selects which agents to run based on PR complexity:

| PR Type | Complexity | Agents Selected |
|---------|------------|-----------------|
| 1 file, <20 lines | SIMPLE | Architect + Arbitrator |
| 2-5 files, <100 lines | MEDIUM | Architect + BugHunter + Arbitrator |
| 10+ files, 200+ lines | COMPLEX | All 4 agents |

## Customizing Agents

Edit agent prompts in `prompts/` directory:

```
prompts/
├── architect.md      # SWE/Architecture agent
├── bug_hunter.md     # QA/Bug detection agent
├── white_hat.md      # Security agent
└── arbitrator.md     # Final verdict agent
```

## Security Best Practices

- **NEVER commit API keys** to version control
- Use GitHub Secrets for sensitive values
- Use `PAT_TOKEN` with minimal scope (repo access)
- Rotate API keys regularly

## License

MIT License - See [LICENSE](LICENSE) for details.