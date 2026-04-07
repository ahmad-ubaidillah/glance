"""Glance Interactive TUI Dashboard - curses-based."""

from __future__ import annotations

import curses
import json
import os
from pathlib import Path

repo_root = Path(os.getcwd())


def load_env():
    config = {}
    env_file = repo_root / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip().strip('"').strip("'")
    return config


def save_env(config):
    env_file = repo_root / ".env"
    existing = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()
    existing.update(config)
    env_file.write_text("\n".join(f"{k}={v}" for k, v in existing.items()) + "\n")


def draw_box(stdscr, y1, x1, y2, x2, color=0):
    try:
        stdscr.attron(curses.color_pair(color) | curses.A_BOLD)
        stdscr.addstr(y1, x1, "┌" + "─" * (x2 - x1 - 1) + "┐")
        for y in range(y1 + 1, y2):
            stdscr.addstr(y, x1, "│")
            stdscr.addstr(y, x2 - 1, "│")
        stdscr.addstr(y2, x1, "└" + "─" * (x2 - x1 - 1) + "┘")
        stdscr.attroff(curses.color_pair(color) | curses.A_BOLD)
    except curses.error:
        pass


def draw_text(stdscr, y, x, text, color=0, bold=False):
    try:
        attr = curses.color_pair(color)
        if bold:
            attr |= curses.A_BOLD
        stdscr.addstr(y, x, text, attr)
    except curses.error:
        pass


def menu(stdscr, title, items, selected=0):
    h, w = stdscr.getmaxyx()
    box_w = min(60, w - 4)
    box_h = len(items) + 4
    y1 = max(1, (h - box_h) // 2)
    x1 = max(1, (w - box_w) // 2)
    y2 = y1 + box_h - 1
    x2 = x1 + box_w

    while True:
        stdscr.erase()
        draw_box(stdscr, y1, x1, y2, x2, 1)
        draw_text(stdscr, y1, x1 + 2, f" {title} ", 2, True)

        for i, item in enumerate(items):
            cy = y1 + 2 + i
            cx = x1 + 2
            if i == selected:
                draw_text(stdscr, cy, cx, f" ► {item} ", 3, True)
            else:
                draw_text(stdscr, cy, cx, f"   {item} ")

        draw_text(stdscr, y2, x1 + 2, " ↑↓ navigate  Enter select  Esc back ", 4)
        stdscr.refresh()

        key = stdscr.getch()
        if key == curses.KEY_UP:
            selected = (selected - 1) % len(items)
        elif key == curses.KEY_DOWN:
            selected = (selected + 1) % len(items)
        elif key in (curses.KEY_ENTER, 10, 13):
            return selected
        elif key == 27:
            return -1


def input_box(stdscr, prompt, default="", mask=False):
    h, w = stdscr.getmaxyx()
    y = h // 2
    x = max(1, (w - 50) // 2)
    draw_text(stdscr, y, x, prompt, 2, True)
    curses.echo()
    curses.curs_set(1)
    stdscr.refresh()
    try:
        val = stdscr.getstr(y, x + len(prompt) + 1, 60).decode()
    except Exception:
        val = ""
    curses.noecho()
    curses.curs_set(0)
    return val or default


def confirm(stdscr, msg):
    h, w = stdscr.getmaxyx()
    y = h // 2
    x = max(1, (w - len(msg) - 10) // 2)
    draw_text(stdscr, y, x, msg + " (y/n) ", 3, True)
    stdscr.refresh()
    key = stdscr.getch()
    return key in (ord("y"), ord("Y"))


def show_page(stdscr, title, lines):
    h, w = stdscr.getmaxyx()
    box_w = min(70, w - 4)
    box_h = min(len(lines) + 5, h - 2)
    y1 = max(1, (h - box_h) // 2)
    x1 = max(1, (w - box_w) // 2)
    y2 = y1 + box_h - 1
    x2 = x1 + box_w

    while True:
        stdscr.erase()
        draw_box(stdscr, y1, x1, y2, x2, 1)
        draw_text(stdscr, y1, x1 + 2, f" {title} ", 2, True)
        for i, line in enumerate(lines[: box_h - 4]):
            draw_text(stdscr, y1 + 2 + i, x1 + 2, line[: box_w - 4], 0)
        draw_text(stdscr, y2, x1 + 2, " Press any key to return ", 4)
        stdscr.refresh()
        stdscr.getch()
        return


def stats_screen(stdscr):
    try:
        from glance.integrations.stats import generate_stats

        stats = generate_stats(repo_root)
        lines = [
            f"Total Reviews: {stats.total_reviews}",
            f"Total Findings: {stats.total_findings}",
            f"Fix Rate: {stats.fix_rate:.1%}",
            f"Avg Findings/Review: {stats.avg_findings_per_review:.1f}",
            "",
        ]
        if stats.issues_by_severity:
            lines.append("By Severity:")
            for sev, count in sorted(stats.issues_by_severity.items()):
                lines.append(f"  {sev}: {count}")
        if stats.issues_by_category:
            lines.append("")
            lines.append("By Category:")
            for cat, count in sorted(
                stats.issues_by_category.items(), key=lambda x: x[1], reverse=True
            )[:10]:
                lines.append(f"  {cat}: {count}")
        if not lines[0]:
            lines = ["No review data yet. Run a review first."]
        show_page(stdscr, "📊 Review Statistics", lines)
    except Exception as e:
        show_page(stdscr, "📊 Review Statistics", [f"Error: {e}"])


def cost_screen(stdscr):
    try:
        from glance.integrations.cost_tracker import load_cost_tracker

        tracker = load_cost_tracker(repo_root)
        lines = tracker.get_summary().split("\n")
        if not lines:
            lines = ["No cost data yet."]
        show_page(stdscr, "💰 Token Cost", lines)
    except Exception as e:
        show_page(stdscr, "💰 Token Cost", [f"Error: {e}"])


def memory_screen(stdscr):
    try:
        from glance.integrations.memory import load_memory

        memory = load_memory(repo_root)
        lines = [
            f"Developers tracked: {len(memory.developers)}",
            f"Issue patterns: {len(memory.issue_patterns)}",
            f"Lessons learned: {len(memory.lessons_learned)}",
            f"Total reviews: {memory.total_reviews}",
        ]
        if memory.developers:
            lines.append("")
            lines.append("Developer profiles:")
            for username, dev in memory.developers.items():
                lines.append(
                    f"  {username}: {dev.total_prs_reviewed} reviews, "
                    f"{sum(dev.common_issue_types.values())} issues"
                )
        show_page(stdscr, "🧠 Memory", lines)
    except Exception as e:
        show_page(stdscr, "🧠 Memory", [f"Error: {e}"])


def llm_config_screen(stdscr):
    config = load_env()
    providers = ["zhipuai", "openai", "anthropic", "google", "azure_openai", "ollama", "custom"]
    current = config.get("LLM_PROVIDER", "zhipuai")
    sel = providers.index(current) if current in providers else 0

    sel = menu(stdscr, "🔑 LLM Provider", providers, sel)
    if sel < 0:
        return
    provider = providers[sel]

    model = input_box(stdscr, "Model (e.g. glm-5): ", config.get("LLM_MODEL", ""))
    base_url = input_box(stdscr, "Base URL (Enter for default): ", config.get("LLM_BASE_URL", ""))
    api_key = input_box(stdscr, "API Key (Enter to keep existing): ", "", mask=True)

    save_env(
        {
            "LLM_PROVIDER": provider,
            "LLM_MODEL": model,
            "LLM_BASE_URL": base_url,
            **({"LLM_API_KEY": api_key} if api_key else {}),
        }
    )
    show_page(stdscr, "✅ Saved", [f"Provider: {provider}", f"Model: {model}"])


def execution_screen(stdscr):
    config = load_env()
    current = config.get("EXECUTION_MODE", "parallel")
    sel = menu(
        stdscr, "🔄 Execution Mode", ["parallel", "sequential"], 0 if current == "parallel" else 1
    )
    if sel >= 0:
        save_env({"EXECUTION_MODE": ["parallel", "sequential"][sel]})
        show_page(stdscr, "✅ Saved", [f"Execution mode: {['parallel', 'sequential'][sel]}"])


def routing_screen(stdscr):
    config = load_env()
    current = config.get("ROUTING_MODE", "adaptive")
    modes = ["adaptive", "parallel", "sequential"]
    sel = modes.index(current) if current in modes else 0
    sel = menu(stdscr, "🧭 Routing Mode", modes, sel)
    if sel >= 0:
        save_env({"ROUTING_MODE": modes[sel]})
        show_page(stdscr, "✅ Saved", [f"Routing mode: {modes[sel]}"])


def memory_config_screen(stdscr):
    config = load_env()
    mem = config.get("ENABLE_MEMORY", "true")
    hist = config.get("ENABLE_REVIEW_HISTORY", "true")
    sel = menu(
        stdscr,
        "🧠 Memory & Learning",
        [
            f"Persistent Memory: {'ON' if mem == 'true' else 'OFF'}",
            f"Review History: {'ON' if hist == 'true' else 'OFF'}",
            "Toggle Memory",
            "Toggle History",
            "Back",
        ],
    )
    if sel == 2:
        save_env({"ENABLE_MEMORY": "false" if mem == "true" else "true"})
    elif sel == 3:
        save_env({"ENABLE_REVIEW_HISTORY": "false" if hist == "true" else "true"})


def team_rules_screen(stdscr):
    rules_file = repo_root / ".glance" / "rules.json"
    rules_file.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if rules_file.exists():
        try:
            existing = json.loads(rules_file.read_text()).get("rules", [])
        except Exception:
            pass

    items = []
    for r in existing:
        items.append(f"[{r.get('action')}] {r.get('description')}")
    items.extend(["+ Add rule", "Back"])

    sel = menu(stdscr, "📝 Team Rules", items)
    if sel < 0 or sel >= len(existing):
        return
    if sel == len(existing):
        rid = input_box(stdscr, "Rule ID: ")
        desc = input_box(stdscr, "Description: ")
        action = input_box(stdscr, "Action (check/ignore/escalate): ")
        pattern = input_box(stdscr, "Pattern: ")
        severity = input_box(stdscr, "Severity (critical/warning/info): ") or "warning"
        files_str = input_box(stdscr, "Files (comma-sep, empty=all): ")
        files = [f.strip() for f in files_str.split(",") if f.strip()]
        existing.append(
            {
                "id": rid,
                "description": desc,
                "action": action,
                "pattern": pattern,
                "severity": severity,
                "files": files,
            }
        )
        rules_file.write_text(json.dumps({"rules": existing}, indent=2))
        show_page(stdscr, "✅ Rule added", [f"{rid}: {desc}"])
    elif sel < len(existing):
        if confirm(stdscr, f"Remove '{existing[sel].get('description')}'?"):
            existing.pop(sel)
            rules_file.write_text(json.dumps({"rules": existing}, indent=2))


def tutorial_screen(stdscr):
    lines = [
        "╔══════════════════════════════════════════╗",
        "║     📖 Glance Setup & Usage Guide        ║",
        "╚══════════════════════════════════════════╝",
        "",
        "Quick Start (3 Steps)",
        "",
        "Step 1: Install",
        "  curl -sSL https://raw.githubusercontent.com/",
        "  ahmad-ubaidillah/glance/main/install.sh | bash",
        "",
        "Step 2: Add 2 Secrets",
        "  Repository → Settings → Secrets → Actions",
        "  LLM_API_KEY : Your LLM API key",
        "  GIT_TOKEN   : Git provider token (repo write)",
        "",
        "Step 3: Push a PR",
        "  Glance automatically reviews new PRs!",
        "",
        "Configuration",
        "  Edit .github/workflows/glance.yml:",
        "  LLM_PROVIDER: zhipuai",
        "  LLM_MODEL: glm-5",
        "  LLM_BASE_URL: https://api.z.ai/api/coding/paas/v4",
        "",
        "Supported LLM Providers",
        "  ZhipuAI  | glm-4-flash, glm-5",
        "  OpenAI   | gpt-4, gpt-3.5-turbo",
        "  Anthropic| claude-3-opus, claude-3-sonnet",
        "  Google   | gemini-pro, gemini-ultra",
        "",
        "Features",
        "  ✅ Multi-agent review",
        "  ✅ Adaptive routing",
        "  ✅ Inline comments + auto-fix",
        "  ✅ Memory & learning system",
        "  ✅ Custom team rules",
    ]
    show_page(stdscr, "📖 Tutorial", lines)


def run_review_screen(stdscr):
    show_page(stdscr, "🚀 Running Review", ["Starting review... (check CI for results)"])
    try:
        from glance.orchestrator import main as run_review
        import asyncio

        asyncio.run(run_review())
    except Exception as e:
        show_page(stdscr, "🚀 Review Error", [str(e)])


def settings_menu(stdscr):
    items = [
        "🔑 LLM Provider & Model",
        "🔄 Execution Mode",
        "🧭 Routing Mode",
        "📝 Custom Team Rules",
        "🧠 Memory & Learning",
        "🔙 Back",
    ]
    screens = [
        llm_config_screen,
        execution_screen,
        routing_screen,
        team_rules_screen,
        memory_config_screen,
        None,
    ]
    sel = 0
    while True:
        sel = menu(stdscr, "⚙️  Settings", items, sel)
        if sel < 0 or sel == len(items) - 1:
            return
        screens[sel](stdscr)


def main(stdscr):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_GREEN)
    curses.init_pair(4, curses.COLOR_WHITE, -1)

    items = [
        "📊 Review Statistics",
        "💰 Token Cost Summary",
        "🧠 Memory & Developer Profiles",
        "⚙️  Settings",
        "📖 Tutorial & Setup Guide",
        "🚀 Run Review",
        "❌ Exit",
    ]
    screens = [
        stats_screen,
        cost_screen,
        memory_screen,
        settings_menu,
        tutorial_screen,
        run_review_screen,
        None,
    ]
    sel = 0
    while True:
        sel = menu(stdscr, "🤖 Glance Dashboard", items, sel)
        if sel < 0 or sel == len(items) - 1:
            break
        screens[sel](stdscr)


if __name__ == "__main__":
    curses.wrapper(main)
