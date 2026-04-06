"""Glance Interactive TUI Dashboard."""

from __future__ import annotations

import json
import os
from pathlib import Path

MENU_MAIN = """
╔══════════════════════════════════════════╗
║         🤖 Glance Dashboard              ║
╠══════════════════════════════════════════╣
║  1. 📊 Review Statistics                 ║
║  2. 💰 Token Cost Summary                ║
║  3. 🧠 Memory & Developer Profiles       ║
║  4. ⚙️  Settings                         ║
║  5. 📖 Tutorial & Setup Guide            ║
║  6. 🚀 Run Review (orchestrator)         ║
║  7. ❌ Exit                              ║
╚══════════════════════════════════════════╝
"""

MENU_SETTINGS = """
╔══════════════════════════════════════════╗
║         ⚙️  Glance Settings              ║
╠══════════════════════════════════════════╣
║  1. 🔑 LLM Provider & Model              ║
║  2. 🔄 Execution Mode                    ║
║  3. 🧭 Routing Mode                      ║
║  4. 📝 Custom Team Rules                 ║
║  5. 🔙 Back to Main Menu                 ║
╚══════════════════════════════════════════╝
"""

TUTORIAL = """
╔══════════════════════════════════════════╗
║     📖 Glance Setup & Usage Guide        ║
╚══════════════════════════════════════════╝

## Quick Start (3 Steps)

### Step 1: Install
```bash
curl -sSL https://raw.githubusercontent.com/ahmad-ubaidillah/glance/main/install.sh | bash
```

### Step 2: Add 2 Secrets
Go to Repository → Settings → Secrets and variables → Actions

| Secret | Value |
|--------|-------|
| LLM_API_KEY | Your LLM API key |
| GIT_TOKEN | Git provider token (repo write) |

### Step 3: Push a PR
Glance automatically reviews new PRs!

## Configuration
After install, edit .github/workflows/glance.yml:

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

## Supported LLM Providers

| Provider | Model Example |
|----------|---------------|
| ZhipuAI | glm-4-flash, glm-5 |
| OpenAI | gpt-4, gpt-3.5-turbo |
| Anthropic | claude-3-opus, claude-3-sonnet |
| Google | gemini-pro, gemini-ultra |
| Azure OpenAI | (deployment name) |
| Ollama | llama2, mistral (local) |

## Features
- Multi-agent review (Architect, BugHunter, WhiteHat)
- Adaptive routing (smart agent selection)
- Inline comments at specific code lines
- Auto-fix suggestions for critical issues
- Memory system (learns from developers)
- Review history tracking
- Test coverage detection
- Custom team rules

## CLI Commands
```bash
glance dashboard          # Show this TUI
glance dashboard --repo . # Stats for current repo
glance cost               # Token cost summary
glance memory             # Memory summary
```

## Custom Team Rules
Create .glance/rules.json:
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
"""


def show_stats(repo_root: Path) -> None:
    from glance.integrations.stats import generate_stats

    stats = generate_stats(repo_root)
    print(stats.to_markdown())


def show_cost(repo_root: Path) -> None:
    from glance.integrations.cost_tracker import load_cost_tracker

    tracker = load_cost_tracker(repo_root)
    print(tracker.get_summary())


def show_memory(repo_root: Path) -> None:
    from glance.integrations.memory import load_memory

    memory = load_memory(repo_root)
    print(f"Developers tracked: {len(memory.developers)}")
    print(f"Issue patterns: {len(memory.issue_patterns)}")
    print(f"Lessons learned: {len(memory.lessons_learned)}")
    print(f"Total reviews: {memory.total_reviews}")
    if memory.developers:
        print("\nDeveloper profiles:")
        for username, dev in memory.developers.items():
            print(
                f"  {username}: {dev.total_prs_reviewed} reviews, "
                f"{sum(dev.common_issue_types.values())} issues"
            )


def configure_llm(repo_root: Path) -> None:
    env_file = repo_root / ".env"
    config = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip().strip('"').strip("'")

    print("\n--- LLM Configuration ---")
    providers = ["zhipuai", "openai", "anthropic", "google", "azure_openai", "ollama", "custom"]
    for i, p in enumerate(providers, 1):
        current = " ✓" if config.get("LLM_PROVIDER") == p else ""
        print(f"  {i}. {p}{current}")

    choice = input("\nSelect provider (number or name): ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        provider = providers[idx] if 0 <= idx < len(providers) else choice
    else:
        provider = choice.lower()

    model = input(f"Model name for {provider} (e.g. glm-5): ").strip() or config.get(
        "LLM_MODEL", ""
    )
    base_url = input(f"Base URL (press Enter for default): ").strip() or config.get(
        "LLM_BASE_URL", ""
    )
    api_key = input(f"API Key (leave empty to keep existing): ").strip()

    config["LLM_PROVIDER"] = provider
    config["LLM_MODEL"] = model
    if base_url:
        config["LLM_BASE_URL"] = base_url
    if api_key:
        config["LLM_API_KEY"] = api_key

    env_file.write_text("\n".join(f"{k}={v}" for k, v in config.items()) + "\n")
    print(f"\n✅ LLM config saved to {env_file}")


def configure_execution(repo_root: Path) -> None:
    env_file = repo_root / ".env"
    config = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip().strip('"').strip("'")

    print("\n--- Execution Mode ---")
    print("  1. parallel  - All agents run simultaneously (faster)")
    print("  2. sequential - Agents run one by one (cheaper)")
    current = config.get("EXECUTION_MODE", "parallel")
    print(f"  Current: {current}")

    choice = input("\nSelect mode (parallel/sequential): ").strip().lower()
    if choice in ("parallel", "sequential"):
        config["EXECUTION_MODE"] = choice
        env_file.write_text("\n".join(f"{k}={v}" for k, v in config.items()) + "\n")
        print(f"✅ Execution mode set to {choice}")


def configure_routing(repo_root: Path) -> None:
    env_file = repo_root / ".env"
    config = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip().strip('"').strip("'")

    print("\n--- Routing Mode ---")
    print("  1. adaptive  - Smart selection based on PR complexity")
    print("  2. parallel  - Always run all agents")
    print("  3. sequential - Always run agents one by one")
    current = config.get("ROUTING_MODE", "adaptive")
    print(f"  Current: {current}")

    choice = input("\nSelect mode (adaptive/parallel/sequential): ").strip().lower()
    if choice in ("adaptive", "parallel", "sequential"):
        config["ROUTING_MODE"] = choice
        env_file.write_text("\n".join(f"{k}={v}" for k, v in config.items()) + "\n")
        print(f"✅ Routing mode set to {choice}")


def configure_team_rules(repo_root: Path) -> None:
    rules_file = repo_root / ".glance" / "rules.json"
    rules_file.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if rules_file.exists():
        try:
            existing = json.loads(rules_file.read_text()).get("rules", [])
        except Exception:
            pass

    print("\n--- Custom Team Rules ---")
    print("Current rules:")
    for i, r in enumerate(existing, 1):
        print(f"  {i}. [{r.get('action')}] {r.get('description')} (pattern: {r.get('pattern')})")
    if not existing:
        print("  (no rules configured)")

    print("\nOptions:")
    print("  1. Add new rule")
    print("  2. Remove rule")
    print("  3. Back")

    choice = input("\nSelect: ").strip()
    if choice == "1":
        rule = {
            "id": input("Rule ID (e.g. no-debug): ").strip(),
            "description": input("Description: ").strip(),
            "action": input("Action (check/ignore/escalate): ").strip(),
            "pattern": input("Pattern to match: ").strip(),
            "severity": input("Severity if escalated (critical/warning/info): ").strip()
            or "warning",
            "files": [
                f.strip()
                for f in input("Files (comma-separated, empty for all): ").strip().split(",")
                if f.strip()
            ],
        }
        existing.append(rule)
        rules_file.write_text(json.dumps({"rules": existing}, indent=2))
        print("✅ Rule added")
    elif choice == "2" and existing:
        idx = input(f"Rule number to remove (1-{len(existing)}): ").strip()
        if idx.isdigit() and 1 <= int(idx) <= len(existing):
            existing.pop(int(idx) - 1)
            rules_file.write_text(json.dumps({"rules": existing}, indent=2))
            print("✅ Rule removed")


def main():
    repo_root = Path(os.getcwd())

    while True:
        print(MENU_MAIN)
        choice = input("Select option (1-7): ").strip()

        if choice == "1":
            show_stats(repo_root)
        elif choice == "2":
            show_cost(repo_root)
        elif choice == "3":
            show_memory(repo_root)
        elif choice == "4":
            while True:
                print(MENU_SETTINGS)
                sub = input("Select option (1-5): ").strip()
                if sub == "1":
                    configure_llm(repo_root)
                elif sub == "2":
                    configure_execution(repo_root)
                elif sub == "3":
                    configure_routing(repo_root)
                elif sub == "4":
                    configure_team_rules(repo_root)
                elif sub == "5":
                    break
                input("\nPress Enter to continue...")
        elif choice == "5":
            print(TUTORIAL)
        elif choice == "6":
            from glance.orchestrator import main as run_review
            import asyncio

            asyncio.run(run_review())
        elif choice == "7":
            print("👋 Goodbye!")
            break
        else:
            print("Invalid option")

        input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()
