# Glance: AI-Powered Code Review System

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.10+-green" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-orange" alt="License">
</p>

Glance is an automated, AI-driven code review orchestrator designed to act as a virtual "Tech Lead." It utilizes a multi-agent architecture to analyze GitHub Pull Requests from three distinct perspectives: Software Engineering (Clean Code), Quality Assurance (Logic & Bugs), and Cybersecurity.

## Features

- **Multi-Agent Architecture**: 4 specialized AI agents (Architect, Bug Hunter, White Hat, Arbitrator)
- **Flexible LLM Support**: Works with OpenAI, Anthropic, Google Gemini, ZhipuAI, Azure OpenAI, Ollama
- **Multi-CI Support**: GitHub Actions, GitLab CI, Jenkins, TeamCity, CircleCI, Azure DevOps
- **Security First**: Built-in secret scanning to prevent sensitive data exposure
- **Flexible Execution**: Parallel or sequential agent execution modes
- **Customizable Personas**: Edit agent prompts via Markdown files
- **GitHub Integration**: Inline comments and final verdict posting

## Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration](#configuration)
3. [LLM Providers](#llm-providers)
4. [CI Providers](#ci-providers)
5. [Execution Modes](#execution-modes)
6. [Customizing Agents](#customizing-agents)
7. [GitHub Actions Integration](#github-actions-integration)
8. [Security Best Practices](#security-best-practices)
   - [Protecting Your API Keys](#protecting-your-api-keys)
   - [Local Development](#local-development)
   - [GitHub Actions Secrets](#github-actions-secrets)
9. [GitLab CI Integration](#gitlab-ci-integration)
10. [Jenkins Integration](#jenkins-integration)
11. [Azure DevOps Integration](#azure-devops-integration)
12. [TeamCity Integration](#teamcity-integration)
13. [CircleCI Integration](#circleci-integration)
14. [Security Checklist](#security-checklist)
15. [Comparison: Where to Store Secrets](#comparison-where-to-store-secrets)
16. [Development](#development)

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

# Create environment file
cp .env.example .env
```

### Environment Variables

Edit `.env` with your configuration:

```bash
# Required - LLM Configuration
LLM_PROVIDER=zhipuai          # openai, anthropic, google, zhipuai, azure_openai, ollama, custom
LLM_API_KEY=your_api_key
LLM_MODEL=glm-4-flash        # Model name (provider-specific)

# Required - GitHub Configuration
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_REPOSITORY=owner/repo
GITHUB_PR_NUMBER=123

# Optional - Execution Mode
EXECUTION_MODE=parallel       # parallel or sequential

# Optional - CI Configuration
CI_PROVIDER=github           # github, gitlab, jenkins, teamcity, circleci, azure
```

## Configuration

### Full Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `zhipuai` | LLM provider to use |
| `LLM_API_KEY` | - | API key for LLM (or use provider-specific env vars) |
| `LLM_MODEL` | `glm-4-flash` | Model name |
| `LLM_BASE_URL` | - | Custom API base URL (for custom providers) |
| `EXECUTION_MODE` | `parallel` | `parallel` (all agents at once) or `sequential` (one by one) |
| `GITHUB_TOKEN` | - | GitHub personal access token |
| `GITHUB_REPOSITORY` | - | Repository in `owner/repo` format |
| `GITHUB_PR_NUMBER` | - | PR number to review |
| `CI_PROVIDER` | `github` | CI provider for status checks |
| `CI_STATUS_URL` | - | CI status URL (TeamCity, Jenkins, etc.) |
| `SKIP_LINTER` | `false` | Skip linter check |
| `TEMPERATURE` | `0.3` | LLM sampling temperature |
| `MAX_TOKENS` | `4096` | Max tokens in LLM response |
| `LOG_LEVEL` | `INFO` | Logging level |

## LLM Providers

### Supported Providers

| Provider | Environment Variable | Model Example |
|----------|---------------------|---------------|
| OpenAI | `OPENAI_API_KEY` | gpt-4, gpt-3.5-turbo |
| Anthropic | `ANTHROPIC_API_KEY` | claude-3-opus, claude-3-sonnet |
| Google | `GOOGLE_API_KEY` | gemini-pro, gemini-ultra |
| ZhipuAI | `ZHIPUAI_API_KEY` | glm-4-flash, glm-4 |
| Azure OpenAI | `AZURE_OPENAI_API_KEY` | gpt-4 (deployment name) |
| Ollama | (local) | llama2, mistral |
| Custom | `CUSTOM_API_KEY` | Any OpenAI-compatible |

### Using Multiple Providers

```bash
# Using OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4

# Using Anthropic
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-3-sonnet-20240229

# Using Ollama (local)
LLM_PROVIDER=ollama
LLM_MODEL=llama2
LLM_BASE_URL=http://localhost:11434/v1

# Using Custom Provider
LLM_PROVIDER=custom
LLM_API_KEY=your-key
LLM_BASE_URL=https://api.your-provider.com/v1
```

## CI Providers

### Supported CI Systems

| Provider | Required Variables |
|----------|-------------------|
| GitHub | `GITHUB_TOKEN` (already required) |
| GitLab | `GITLAB_URL`, `GITLAB_API_TOKEN`, `PROJECT_ID` |
| Jenkins | `JENKINS_URL`, `JENKINS_USERNAME`, `JENKINS_API_TOKEN`, `JOB_NAME` |
| TeamCity | `TEAMCITY_URL`, `TEAMCITY_USERNAME`, `TEAMCITY_PASSWORD`, `BUILD_CONFIG` |
| CircleCI | `CIRCLECI_API_TOKEN`, `VCS_TYPE` (gh/bb), `USERNAME`, `PROJECT` |
| Azure DevOps | `AZURE_ORGANIZATION`, `AZURE_PROJECT`, `AZURE_TOKEN` |

### CI Provider Configuration

```bash
# GitLab CI
CI_PROVIDER=gitlab
GITLAB_URL=https://gitlab.com
GITLAB_API_TOKEN=glpat-xxxx
PROJECT_ID=12345

# Jenkins CI
CI_PROVIDER=jenkins
JENKINS_URL=https://jenkins.example.com
JENKINS_USERNAME=admin
JENKINS_API_TOKEN=xxxx
JOB_NAME=my-project

# TeamCity CI
CI_PROVIDER=teamcity
TEAMCITY_URL=https://teamcity.example.com
TEAMCITY_USERNAME=admin
TEAMCITY_PASSWORD=xxxx
BUILD_CONFIG=MyBuildConfig
```

## Execution Modes

### Parallel Mode (Default)

All three review agents (Architect, Bug Hunter, White Hat) run simultaneously:

```
┌─────────────┐
│   PR Diff   │
└──────┬──────┘
       │
   ┌───┴───┬───────────┐
   ▼       ▼           ▼
┌──────┐ ┌──────┐ ┌───────┐
│ Arch │ │ Bug  │ │ White │  ← Parallel execution
│ (SWE)│ │Hunter│ │  Hat  │
└──┬───┘ └──┬───┘ └───┬───┘
   └───┬────┴────┬────┘
       ▼        ▼
   ┌───────────────────┐
   │    Arbitrator     │  ← Consolidates results
   └─────────┬─────────┘
             ▼
      Final Verdict
```

### Sequential Mode (Single LLM)

Agents run one by one, using a single LLM call per persona:

```
┌─────────────┐
│   PR Diff   │
└──────┬──────┘
       │
       ▼
┌──────────────┐
│  Architect   │  ← SWE review
│   (SWE)      │
└──────┬───────┘
       ▼
┌──────────────┐
│  Bug Hunter  │  ← QA review
│    (QA)      │
└──────┬───────┘
       ▼
┌──────────────┐
│  White Hat   │  ← Security review
│  (Security)  │
└──────┬───────┘
       ▼
┌──────────────┐
│   Arbitrator │  ← Final verdict
└──────────────┘
```

**Benefits of Sequential Mode:**
- Lower cost (single model instance)
- More deterministic results
- Better for debugging
- Can use smaller/cheaper models

**Benefits of Parallel Mode:**
- Faster execution (all agents at once)
- Better for high-volume PRs
- Allows different models per agent

## Customizing Agents

### Prompt Files

Agent prompts are stored in the `prompts/` directory:

```
prompts/
├── architect.md      # SWE/Architecture agent
├── bug_hunter.md     # QA/Bug detection agent
├── white_hat.md      # Security agent
└── arbitrator.md     # Final verdict agent
```

### Editing Prompts

1. Edit the `.md` file in `prompts/`
2. The system will automatically load your custom prompts
3. Restart the review to see changes

Example of customizing the Architect agent:

```markdown
# Architect Agent - Software Engineering Persona

**Role**: The Architect (SWE) - Clean Code and Architecture Review Agent

## System Prompt

You are The Architect, a senior software engineer...
[Your custom prompt here]
```

### Prompt Structure

Each prompt file should include:
- **Role**: Agent's role definition
- **Focus Areas**: What the agent should prioritize
- **System Prompt**: Detailed instructions for the LLM
- **Output Format**: Expected JSON structure

## GitHub Actions Integration

### Workflow Example

Create `.github/workflows/glance.yml`:

```yaml
name: GR-Review Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  lint:
    name: Run Linter
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -e .
      
      - name: Run linter
        run: |
          # Your linter command here

  analyze:
    name: GR-Review Analysis
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -e .
      
      - name: Run GR-Review
        env:
          ZHIPUAI_API_KEY: ${{ secrets.ZHIPUAI_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          GITHUB_PR_NUMBER: ${{ github.event.pull_request.number }}
          EXECUTION_MODE: ${{ vars.EXECUTION_MODE || 'parallel' }}
        run: python -m glance.orchestrator
```

### Secrets Required

Add these in your GitHub repository settings:
- `ZHIPUAI_API_KEY` - Your LLM API key
- `GITHUB_TOKEN` - GitHub token (auto-provided)

### Optional Variables

Add these in repository settings:
- `EXECUTION_MODE` - parallel or sequential
- `CI_STATUS_URL` - TeamCity/Jenkins URL

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=glance
```

### Project Structure

```
glance/
├── src/glance/
│   ├── agents/           # AI agent implementations
│   │   ├── architect.py
│   │   ├── bug_hunter.py
│   │   ├── white_hat.py
│   │   ├── arbitrator.py
│   │   └── base.py
│   ├── integrations/     # External integrations
│   │   ├── ci_status.py  # CI provider implementations
│   │   ├── github_client.py
│   │   └── signature_mapper.py
│   ├── scanners/         # Pre-review scanners
│   │   ├── secret_scanner.py
│   │   └── linter_check.py
│   ├── prompts/          # Agent prompt loader
│   ├── llm/              # LLM client factory
│   ├── config.py         # Configuration
│   └── orchestrator.py   # Main orchestration
├── prompts/              # Editable agent prompts (.md)
├── tests/                # Test suite
├── .github/workflows/    # GitHub Actions
└── pyproject.toml
```

## Troubleshooting

### Common Issues

**Q: Getting "Missing required configuration" error**
- Make sure all required env vars are set in `.env`
- Check that `GITHUB_REPOSITORY` is in `owner/repo` format

**Q: LLM API errors**
- Verify your API key is correct
- Check the model name is valid for your provider
- For custom providers, ensure `LLM_BASE_URL` is set

**Q: CI status not being fetched**
- Check `CI_PROVIDER` is set correctly
- Verify required CI credentials are configured
- Check logs for specific error messages

**Q: How to switch between parallel and sequential?**
- Set `EXECUTION_MODE=parallel` or `EXECUTION_MODE=sequential` in `.env`
- Or pass as environment variable when running

## Security Best Practices

### Protecting Your API Keys

**NEVER commit API keys to version control!**

```bash
# Verify .env is in .gitignore
cat .gitignore | grep -E "^(\.env|env)"

# If not, add it manually:
echo ".env" >> .gitignore
echo ".env.local" >> .gitignore
```

### Local Development

```bash
# 1. Copy the template
cp .env.example .env

# 2. Edit with your keys (never share this file!)
nano .env

# 3. Verify it's ignored
git status  # Should NOT show .env as untracked
```

### GitHub Actions Secrets

For CI/CD, use GitHub Secrets (recommended):

```yaml
# .github/workflows/glance.yml
name: GR-Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -e .
      
      - name: Run GR-Review
        env:
          # Secrets are encrypted and masked in logs
          LLM_PROVIDER: ${{ vars.LLM_PROVIDER }}
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          LLM_MODEL: ${{ vars.LLM_MODEL }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          GITHUB_PR_NUMBER: ${{ github.event.pull_request.number }}
          EXECUTION_MODE: ${{ vars.EXECUTION_MODE || 'adaptive' }}
        run: python -m glance.orchestrator
```

**Setup Secrets:**
1. Go to Repository → Settings → Secrets and variables → Actions
2. Add new secret:
   - `LLM_API_KEY` - Your LLM provider API key
   - `GITHUB_TOKEN` - GitHub PAT (or use built-in `secrets.GITHUB_TOKEN`)

**Add Variables (public):**
1. Repository → Settings → Secrets and variables → Actions → Variables
2. Add:
   - `LLM_PROVIDER` = zhipuai
   - `LLM_MODEL` = glm-4-flash
   - `EXECUTION_MODE` = adaptive

## GitLab CI Integration

### Option 1: Using GitLab CI Variables

```yaml
# .gitlab-ci.yml
stages:
  - review

glance:
  stage: review
  image: python:3.11-slim
  before_script:
    - pip install -e .
  script:
    - |
      python -m glance.orchestrator
  variables:
    LLM_PROVIDER: $LLM_PROVIDER
    LLM_API_KEY: $LLM_API_KEY
    LLM_MODEL: $LLM_MODEL
    GITHUB_TOKEN: $GITHUB_TOKEN
    GITHUB_REPOSITORY: $CI_PROJECT_PATH
    # Extract PR number from branch or merge request
    GITHUB_PR_NUMBER: $CI_MERGE_REQUEST_IID
  only:
    - merge_requests
```

**Setup in GitLab:**
1. Go to Settings → CI/CD → Variables
2. Add variables (masked):
   - `LLM_API_KEY` - Your API key
   - `GITHUB_TOKEN` - GitHub PAT
3. Add public variables:
   - `LLM_PROVIDER` = zhipuai
   - `LLM_MODEL` = glm-4-flash

### Option 2: Using GitLab as CI Status Provider

To have GR-Review check GitLab CI status:

```bash
# In .env or secrets
CI_PROVIDER=gitlab
GITLAB_URL=https://gitlab.com
GITLAB_API_TOKEN=glpat-xxxx
PROJECT_ID=12345
```

## Jenkins Integration

### Jenkinsfile

```groovy
pipeline {
    agent any
    
    environment {
        LLM_PROVIDER = credentials('llm-provider')
        LLM_API_KEY = credentials('llm-api-key')
        GITHUB_TOKEN = credentials('github-token')
        GITHUB_REPOSITORY = 'owner/repo'
    }
    
    stages {
        stage('GR-Review') {
            steps {
                sh '''
                    pip install -e .
                    python -m glance.orchestrator
                '''
            }
        }
    }
}
```

**Setup Jenkins Credentials:**
1. Manage Jenkins → Manage Credentials
2. Add credentials:
   - Kind: Secret text
   - ID: llm-api-key, github-token, etc.

### Using Jenkins as CI Status Provider

```bash
# In .env or Jenkins environment
CI_PROVIDER=jenkins
JENKINS_URL=https://jenkins.example.com
JENKINS_USERNAME=admin
JENKINS_API_TOKEN=xxxx
JOB_NAME=my-project-pipeline
```

## Azure DevOps Integration

### azure-pipelines.yml

```yaml
trigger: none

pr:
  branches:
    include:
      - '*'

stages:
  - stage: CodeReview
    jobs:
      - job: GRReview
        pool:
          vmImage: ubuntu-latest
        steps:
          - task: UsePythonVersion@0
            inputs:
              versionSpec: '3.11'
          
          - script: |
              pip install -e .
              python -m glance.orchestrator
            env:
              LLM_PROVIDER: $(LLM_PROVIDER)
              LLM_API_KEY: $(LLM_API_KEY)
              LLM_MODEL: $(LLM_MODEL)
              GITHUB_TOKEN: $(GITHUB_TOKEN)
              GITHUB_REPOSITORY: $(Build.Repository.Name)
              GITHUB_PR_NUMBER: $(System.PullRequest.PullRequestNumber)
```

**Setup Azure DevOps Variables:**
1. Project Settings → Pipelines → Variables
2. Add variables (secret for API keys):
   - LLM_API_KEY (secret)
   - GITHUB_TOKEN (secret)
3. Public variables:
   - LLM_PROVIDER = zhipuai
   - LLM_MODEL = glm-4-flash

## TeamCity Integration

### Setup for CI Status

```bash
# In .env or configuration
CI_PROVIDER=teamcity
TEAMCITY_URL=https://teamcity.example.com
TEAMCITY_USERNAME=admin
TEAMCITY_PASSWORD=xxxx
CI_BUILD_CONFIG=MyBuildConfig
```

### Triggering GR-Review from TeamCity

You can trigger GR-Review as a build step:

```bash
# In TeamCity build step
#!/bin/bash
pip install -e .
python -m glance.orchestrator
```

Add parameters as TeamCity configuration parameters.

## CircleCI Integration

### .circleci/config.yml

```yaml
version: 2.1

orbs:
  python: circleci/python@2.1.1

workflows:
  glance:
    jobs:
      - python/run:
          version: '3.11'
          step: >
            run: |
              pip install -e .
              python -m glance.orchestrator
          environment:
            LLM_PROVIDER: <<pipeline.parameters.llm_provider>>
            LLM_API_KEY: <<pipeline.parameters.llm_api_key>>
            LLM_MODEL: <<pipeline.parameters.llm_model>>
            GITHUB_TOKEN: <<pipeline.parameters.github_token>>
            GITHUB_REPOSITORY: <<pipeline.parameters.github_repo>>
            GITHUB_PR_NUMBER: <<pipeline.parameters.pr_number>>
```

## Security Checklist

| ✅ | Item |
|---|------|
| ✅ | `.env` in `.gitignore` |
| ✅ | Never commit secrets to repo |
| ✅ | Use CI/CD secrets (GitHub Secrets, GitLab Variables, Jenkins Credentials) |
| ✅ | Rotate API keys regularly |
| ✅ | Use minimal scope for tokens |
| ✅ | Review audit logs regularly |

## Comparison: Where to Store Secrets

| Environment | Recommended Method | Why |
|-------------|-------------------|-----|
| **GitHub Actions** | GitHub Secrets | Built-in encryption, masked in logs |
| **GitLab CI** | GitLab Variables | Masked, protected variables |
| **Jenkins** | Jenkins Credentials | Encrypted storage |
| **Azure DevOps** | Azure Variables | Secret pipelines variables |
| **CircleCI** | CircleCI Contexts | Shared encrypted environment |
| **Local Dev** | Local `.env` | Never committed, ignored by git |
| **Server/VM** | Environment variables or secrets manager | External secrets management |

## License

MIT License - See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.