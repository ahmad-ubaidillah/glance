"""Glance Interactive TUI Dashboard."""

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
    sanitized = {}
    for k, v in config.items():
        safe_v = v.replace("\n", "").replace("\r", "").replace("=", "")
        sanitized[k] = safe_v
    existing.update(sanitized)
    env_file.write_text("\n".join(f"{k}={v}" for k, v in existing.items()) + "\n")


def safe_addstr(stdscr, y, x, text):
    h, w = stdscr.getmaxyx()
    y = max(0, min(y, h - 1))
    x = max(0, min(x, w - 1))
    text = text[: w - x - 1] if x < w else ""
    try:
        stdscr.addstr(y, x, text)
    except curses.error:
        pass


def clear_line(stdscr, y, x1, x2):
    h, w = stdscr.getmaxyx()
    y = max(0, min(y, h - 1))
    x1 = max(0, min(x1, w - 1))
    x2 = max(x1, min(x2, w - 1))
    try:
        for x in range(x1, x2):
            stdscr.addch(y, x, " ")
    except curses.error:
        pass


def draw_box(stdscr, y1, x1, y2, x2, color=0):
    h, w = stdscr.getmaxyx()
    y1 = max(0, min(y1, h - 1))
    x1 = max(0, min(x1, w - 1))
    y2 = max(y1 + 1, min(y2, h - 1))
    x2 = max(x1 + 1, min(x2, w - 1))

    width = x2 - x1 - 1
    if width < 1:
        return

    try:
        stdscr.attron(curses.color_pair(color) | curses.A_BOLD)
        safe_addstr(stdscr, y1, x1, "┌" + "─" * width + "┐")
        for y in range(y1 + 1, y2):
            safe_addstr(stdscr, y, x1, "│")
            safe_addstr(stdscr, y, x2 - 1, "│")
        safe_addstr(stdscr, y2, x1, "└" + "─" * width + "┘")
        stdscr.attroff(curses.color_pair(color) | curses.A_BOLD)
    except curses.error:
        pass


def draw_text(stdscr, y, x, text, color=0, bold=False):
    h, w = stdscr.getmaxyx()
    y = max(0, min(y, h - 1))
    x = max(0, min(x, w - 1))
    try:
        attr = curses.color_pair(color)
        if bold:
            attr |= curses.A_BOLD
        text = text[: w - x - 1] if x < w else ""
        stdscr.addstr(y, x, text, attr)
    except curses.error:
        pass


def menu(stdscr, title, items, selected=0):
    h, w = stdscr.getmaxyx()

    box_w = min(58, w - 6)
    max_visible = min(len(items), h - 8)
    box_h = max_visible + 5

    y1 = max(1, (h - box_h) // 2)
    x1 = max(1, (w - box_w) // 2)
    y2 = y1 + box_h - 1
    x2 = x1 + box_w

    scroll_offset = 0
    if selected >= max_visible:
        scroll_offset = selected - max_visible + 1

    while True:
        stdscr.erase()
        draw_box(stdscr, y1, x1, y2, x2, 1)
        draw_text(stdscr, y1, x1 + 2, f" {title} ", 2, True)

        for i in range(max_visible):
            item_idx = i + scroll_offset
            if item_idx >= len(items):
                break

            cy = y1 + 2 + i
            cx = x1 + 3
            clear_line(stdscr, cy, cx, x2 - 2)

            item = items[item_idx]
            max_item_len = box_w - 6
            display_item = item[:max_item_len] if len(item) > max_item_len else item

            if item_idx == selected:
                draw_text(stdscr, cy, cx, f"► {display_item}", 3, True)
            else:
                draw_text(stdscr, cy, cx, f"  {display_item}")

        footer_y = y2
        clear_line(stdscr, footer_y, x1 + 2, x2 - 2)

        if len(items) > max_visible:
            scroll_info = (
                f"↑↓ scroll ({scroll_offset + 1}-{scroll_offset + max_visible}/{len(items)})"
            )
            draw_text(stdscr, footer_y, x1 + 2, scroll_info, 4)
        else:
            draw_text(stdscr, footer_y, x1 + 2, "↑↓ navigate  Enter select  Esc back", 4)

        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_UP, ord("k")):
            if selected > 0:
                selected -= 1
                if selected < scroll_offset:
                    scroll_offset = max(0, scroll_offset - 1)
        elif key in (curses.KEY_DOWN, ord("j")):
            if selected < len(items) - 1:
                selected += 1
                if selected >= scroll_offset + max_visible:
                    scroll_offset = min(len(items) - max_visible, scroll_offset + 1)
        elif key in (curses.KEY_ENTER, 10, 13):
            return selected
        elif key == 27:
            return -1


def input_box(stdscr, prompt, default="", password=False):
    h, w = stdscr.getmaxyx()

    dialog_h = 6
    dialog_w = min(56, w - 6)
    y1 = max(1, (h - dialog_h) // 2)
    x1 = max(1, (w - dialog_w) // 2)
    y2 = y1 + dialog_h - 1
    x2 = x1 + dialog_w

    draw_box(stdscr, y1, x1, y2, x2, 1)
    draw_text(stdscr, y1, x1 + 2, " Input ", 2, True)

    display_prompt = prompt[: dialog_w - 6] if len(prompt) > dialog_w - 6 else prompt
    draw_text(stdscr, y1 + 2, x1 + 3, display_prompt, 0)

    input_y = y1 + 3
    input_x = x1 + 3
    max_input_len = dialog_w - 6

    current = default if default else ""
    display_current = "*" * len(current) if password else current
    display_current = display_current[:max_input_len]

    draw_text(stdscr, input_y, input_x, display_current, 3)

    curses.echo()
    curses.curs_set(2)
    stdscr.refresh()

    try:
        cursor_x = input_x + len(display_current)
        stdscr.move(input_y, cursor_x)
        user_input = stdscr.getstr(input_y, input_x, max_input_len).decode()
    except Exception:
        user_input = ""

    curses.noecho()
    curses.curs_set(0)

    return user_input if user_input else default


def confirm(stdscr, msg):
    h, w = stdscr.getmaxyx()

    dialog_h = 5
    dialog_w = min(48, w - 6)
    y1 = max(1, (h - dialog_h) // 2)
    x1 = max(1, (w - dialog_w) // 2)

    stdscr.erase()
    draw_box(stdscr, y1, x1, y1 + dialog_h - 1, x1 + dialog_w, 1)

    display_msg = msg[: dialog_w - 10] if len(msg) > dialog_w - 10 else msg
    draw_text(stdscr, y1 + 1, x1 + 3, display_msg, 0)
    draw_text(stdscr, y1 + 3, x1 + 3, "Press [Y] Yes  [N] No", 4)

    stdscr.refresh()

    while True:
        key = stdscr.getch()
        if key in (ord("y"), ord("Y"), curses.KEY_ENTER, 10, 13):
            return True
        elif key in (ord("n"), ord("N"), 27):
            return False


def show_page(stdscr, title, lines, scrollable=True):
    h, w = stdscr.getmaxyx()

    page_w = min(68, w - 4)
    page_h = min(len(lines) + 4, h - 2)

    y1 = max(0, (h - page_h) // 2)
    x1 = max(0, (w - page_w) // 2)
    y2 = min(h - 1, y1 + page_h - 1)
    x2 = min(w - 1, x1 + page_w)

    scroll_offset = 0
    max_content_lines = page_h - 5
    total_lines = len(lines)

    while True:
        stdscr.erase()
        draw_box(stdscr, y1, x1, y2, x2, 1)
        draw_text(stdscr, y1, x1 + 2, f" {title} ", 2, True)

        content_x = x1 + 2
        content_max_w = page_w - 4

        for i in range(max_content_lines):
            line_idx = i + scroll_offset
            if line_idx >= total_lines:
                break

            cy = y1 + 2 + i
            line = lines[line_idx]

            if len(line) > content_max_w:
                line = line[: content_max_w - 3] + "..."

            clear_line(stdscr, cy, content_x, x2 - 2)
            draw_text(stdscr, cy, content_x, line, 0)

        footer_y = y2
        clear_line(stdscr, footer_y, x1 + 2, x2 - 2)

        footer_parts = []
        if scrollable and total_lines > max_content_lines:
            footer_parts.append(
                f"↑↓ scroll ({scroll_offset + 1}-{scroll_offset + max_content_lines}/{total_lines})"
            )
        footer_parts.append("Any key to return")
        footer_text = "  ".join(footer_parts)
        draw_text(stdscr, footer_y, x1 + 2, footer_text[: page_w - 4], 4)

        stdscr.refresh()

        key = stdscr.getch()

        if scrollable and total_lines > max_content_lines:
            if key in (curses.KEY_UP, ord("k")):
                scroll_offset = max(0, scroll_offset - 1)
            elif key in (curses.KEY_DOWN, ord("j")):
                scroll_offset = min(total_lines - max_content_lines, scroll_offset + 1)
            elif key == curses.KEY_PPAGE:
                scroll_offset = max(0, scroll_offset - max_content_lines)
            elif key == curses.KEY_NPAGE:
                scroll_offset = min(
                    total_lines - max_content_lines, scroll_offset + max_content_lines
                )
            else:
                break
        else:
            break


def stats_screen(stdscr):
    try:
        from glance.integrations.stats import generate_stats

        stats = generate_stats(repo_root)

        lines = [
            "=" * 40,
            "         REVIEW STATISTICS",
            "=" * 40,
            "",
            f"  Total Reviews:      {stats.total_reviews}",
            f"  Total Findings:     {stats.total_findings}",
            f"  Fix Rate:           {stats.fix_rate:.1%}",
            f"  Avg/Review:         {stats.avg_findings_per_review:.1f}",
            "",
        ]

        if stats.issues_by_severity:
            lines.append("  By Severity:")
            for sev, count in sorted(stats.issues_by_severity.items()):
                lines.append(f"    - {sev}: {count}")
            lines.append("")

        if stats.issues_by_category:
            lines.append("  By Category (Top 10):")
            for cat, count in sorted(
                stats.issues_by_category.items(), key=lambda x: x[1], reverse=True
            )[:10]:
                lines.append(f"    - {cat}: {count}")

        if len(lines) == 5:
            lines.append("  No review data yet.")
            lines.append("  Run a review first!")

        show_page(stdscr, "Statistics", lines)
    except Exception as e:
        show_page(stdscr, "Statistics", [f"Error: {e}"])


def cost_screen(stdscr):
    try:
        from glance.integrations.cost_tracker import load_cost_tracker

        tracker = load_cost_tracker(repo_root)
        lines = tracker.get_summary().split("\n")
        if not lines or all(l.strip() == "" for l in lines):
            lines = ["No cost data yet.", "Run reviews to track token usage."]
        show_page(stdscr, "Token Cost", lines)
    except Exception as e:
        show_page(stdscr, "Token Cost", [f"Error: {e}"])


def memory_screen(stdscr):
    try:
        from glance.integrations.memory import load_memory

        memory = load_memory(repo_root)

        lines = [
            "=" * 40,
            "         MEMORY & LEARNING",
            "=" * 40,
            "",
            f"  Developers tracked:  {len(memory.developers)}",
            f"  Issue patterns:     {len(memory.issue_patterns)}",
            f"  Lessons learned:    {len(memory.lessons_learned)}",
            f"  Total reviews:      {memory.total_reviews}",
            "",
        ]

        if memory.developers:
            lines.append("  Developer Profiles:")
            for username, dev in memory.developers.items():
                issues = sum(dev.common_issue_types.values())
                lines.append(f"    @{username}")
                lines.append(f"      Reviews: {dev.total_prs_reviewed}, Issues: {issues}")

        show_page(stdscr, "Memory", lines)
    except Exception as e:
        show_page(stdscr, "Memory", [f"Error: {e}"])


def llm_config_screen(stdscr):
    config = load_env()
    providers = ["zhipuai", "openai", "anthropic", "google", "azure_openai", "ollama", "custom"]
    current = config.get("LLM_PROVIDER", "zhipuai")
    sel = providers.index(current) if current in providers else 0

    sel = menu(stdscr, "LLM Provider", providers, sel)
    if sel < 0:
        return

    provider = providers[sel]
    model = input_box(stdscr, "Model (e.g. glm-5):", config.get("LLM_MODEL", ""))
    base_url = input_box(stdscr, "Base URL (Enter=default):", config.get("LLM_BASE_URL", ""))

    save_env(
        {
            "LLM_PROVIDER": provider,
            "LLM_MODEL": model,
            "LLM_BASE_URL": base_url,
        }
    )
    show_page(stdscr, "Saved", [f"Provider: {provider}", f"Model: {model}"])


def execution_screen(stdscr):
    config = load_env()
    current = config.get("EXECUTION_MODE", "sequential")
    modes = ["sequential (1 LLM, 4 personas in order)", "parallel (3 LLMs at once)"]
    sel = 0 if current == "sequential" else 1

    sel = menu(stdscr, "Execution Mode", modes, sel)
    if sel >= 0:
        mode = "sequential" if sel == 0 else "parallel"
        save_env({"EXECUTION_MODE": mode})
        desc = "1 LLM, 4 personas sequentially" if sel == 0 else "3 LLMs in parallel"
        show_page(stdscr, "Saved", [f"Mode: {desc}"])


def routing_screen(stdscr):
    config = load_env()
    current = config.get("ROUTING_MODE", "adaptive")
    modes = ["adaptive", "parallel", "sequential"]
    descriptions = [
        "Smart - auto-select agents based on PR",
        "Always run all agents in parallel",
        "Always run all agents sequentially",
    ]

    sel = modes.index(current) if current in modes else 0
    items = [f"{m} - {d}" for m, d in zip(modes, descriptions)]

    sel = menu(stdscr, "Routing Mode", items, sel)
    if sel >= 0:
        mode = modes[sel]
        save_env({"ROUTING_MODE": mode})
        show_page(stdscr, "Saved", [f"Routing: {mode}"])


def memory_config_screen(stdscr):
    config = load_env()
    mem = config.get("ENABLE_MEMORY", "true")
    hist = config.get("ENABLE_REVIEW_HISTORY", "true")

    items = [
        f"Persistent Memory:    {'ON' if mem == 'true' else 'OFF'}",
        f"Review History:      {'ON' if hist == 'true' else 'OFF'}",
        "Toggle Memory",
        "Toggle History",
        "Back to Settings",
    ]

    sel = menu(stdscr, "Memory & Learning", items)
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
        action = r.get("action", "?").upper()
        desc = r.get("description", "")[:30]
        items.append(f"[{action}] {desc}")
    items.extend(["+ Add New Rule", "Back"])

    sel = menu(stdscr, "Team Rules", items)

    if sel == len(existing):
        rid = input_box(stdscr, "Rule ID:")
        desc = input_box(stdscr, "Description:")
        action = input_box(stdscr, "Action (check/ignore/escalate):")
        pattern = input_box(stdscr, "Pattern:")
        severity = input_box(stdscr, "Severity (critical/warning/info):") or "warning"

        existing.append(
            {
                "id": rid,
                "description": desc,
                "action": action,
                "pattern": pattern,
                "severity": severity,
                "files": [],
            }
        )
        rules_file.write_text(json.dumps({"rules": existing}, indent=2))
        show_page(stdscr, "Rule Added", [f"{rid}: {desc}"])
    elif 0 <= sel < len(existing):
        if confirm(stdscr, f"Remove rule?"):
            existing.pop(sel)
            rules_file.write_text(json.dumps({"rules": existing}, indent=2))


def tutorial_screen(stdscr):
    lines = [
        "=" * 44,
        "         GLANCE SETUP GUIDE",
        "=" * 44,
        "",
        "  QUICK START (3 Steps)",
        "",
        "  Step 1: Install",
        "    curl -sSL bit.ly/glance-install | bash",
        "",
        "  Step 2: Add Secrets",
        "    Go to: Repo -> Settings -> Secrets",
        "    - LLM_API_KEY  : Your LLM API key",
        "    - GIT_TOKEN    : GitHub token (repo write)",
        "",
        "  Step 3: Push a PR",
        "    Glance auto-reviews new PRs!",
        "",
        "=" * 44,
        "  SUPPORTED PROVIDERS",
        "=" * 44,
        "  - ZhipuAI   -> glm-4-flash, glm-5",
        "  - OpenAI    -> gpt-4, gpt-3.5-turbo",
        "  - Anthropic -> claude-3-opus, claude-3-sonnet",
        "  - Google    -> gemini-pro, gemini-ultra",
        "",
        "=" * 44,
        "  FEATURES",
        "=" * 44,
        "  + Multi-agent review (4 personas)",
        "  + Adaptive agent selection",
        "  + Secret scanner (auto-abort)",
        "  + Inline comments + auto-fix",
        "  + Memory & learning system",
        "  + Custom team rules",
        "  + Sequential/Parallel modes",
    ]
    show_page(stdscr, "Tutorial", lines)


def run_review_screen(stdscr):
    show_page(
        stdscr,
        "Running Review",
        [
            "Starting review...",
            "",
            "This may take a few minutes.",
            "Check CI logs for progress.",
            "",
            "Results will be posted as",
            "inline comments on the PR.",
        ],
        scrollable=False,
    )

    try:
        from glance.orchestrator import main as run_review
        import asyncio

        asyncio.run(run_review())
    except Exception as e:
        show_page(stdscr, "Review Error", [str(e)])


def settings_menu(stdscr):
    items = [
        "LLM Provider & Model",
        "Execution Mode (Seq/Parallel)",
        "Routing Mode",
        "Custom Team Rules",
        "Memory & Learning",
        "Back to Main Menu",
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
        sel = menu(stdscr, "Settings", items, sel)
        if sel < 0 or sel == len(items) - 1:
            return
        screens[sel](stdscr)


def uninstall_screen(stdscr):
    h, w = stdscr.getmaxyx()

    dialog_h = 12
    dialog_w = min(52, w - 6)
    y1 = max(1, (h - dialog_h) // 2)
    x1 = max(1, (w - dialog_w) // 2)

    stdscr.erase()
    draw_box(stdscr, y1, x1, y1 + dialog_h - 1, x1 + dialog_w, 1)
    draw_text(stdscr, y1, x1 + 2, " Uninstall Glance ", 2, True)

    items = [
        "- Virtual environment (venv)",
        "- Global glance wrapper",
        "- .glance data",
        "- .env file",
    ]

    for i, item in enumerate(items):
        draw_text(stdscr, y1 + 2 + i, x1 + 4, item, 0)

    draw_text(stdscr, y1 + 7, x1 + 4, "This cannot be undone!", 1)
    draw_text(stdscr, y1 + 9, x1 + 4, "Press [Y] to uninstall  [N] to cancel", 4)

    stdscr.refresh()

    while True:
        key = stdscr.getch()
        if key in (ord("y"), ord("Y")):
            import shutil

            removed = []
            for d in ["venv", ".venv"]:
                if (repo_root / d).exists():
                    shutil.rmtree(repo_root / d)
                    removed.append(d)

            wrapper = Path.home() / ".local" / "bin" / "glance"
            if wrapper.exists():
                wrapper.unlink()
                removed.append("wrapper")

            if (repo_root / ".glance").exists():
                shutil.rmtree(repo_root / ".glance")
                removed.append(".glance")

            if (repo_root / ".env").exists():
                (repo_root / ".env").unlink()
                removed.append(".env")

            if removed:
                msg = f"Removed: {', '.join(removed)}"
            else:
                msg = "Nothing to remove"

            show_page(stdscr, "Uninstalled", [msg, "", "Glance has been removed."])
            break
        elif key in (ord("n"), ord("N"), 27):
            return


def main(stdscr):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.noecho()

    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_GREEN)
    curses.init_pair(4, curses.COLOR_WHITE, -1)
    curses.init_pair(5, curses.COLOR_RED, -1)

    items = [
        "Review Statistics",
        "Token Cost Summary",
        "Memory & Developer Profiles",
        "Settings",
        "Tutorial & Setup Guide",
        "Run Review",
        "Uninstall Glance",
        "Exit",
    ]

    screens = [
        stats_screen,
        cost_screen,
        memory_screen,
        settings_menu,
        tutorial_screen,
        run_review_screen,
        uninstall_screen,
        None,
    ]

    sel = 0
    while True:
        sel = menu(stdscr, "Glance Dashboard", items, sel)

        if sel < 0:
            break

        if sel == len(items) - 1:
            break

        if screens[sel]:
            screens[sel](stdscr)


if __name__ == "__main__":
    curses.wrapper(main)
