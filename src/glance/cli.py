"""Glance CLI - Command line interface."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def cmd_dashboard(args):
    import curses
    from glance.tui import main as tui_main

    curses.wrapper(tui_main)


def cmd_cost(args):
    from glance.integrations.cost_tracker import load_cost_tracker

    repo_root = Path(args.repo) if args.repo else Path.cwd()
    tracker = load_cost_tracker(repo_root)
    print(tracker.get_summary())


def cmd_memory(args):
    from glance.integrations.memory import load_memory

    repo_root = Path(args.repo) if args.repo else Path.cwd()
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


def cmd_uninstall(args):
    repo_root = Path.cwd()
    removed = []

    for d in ["venv", ".venv"]:
        if (repo_root / d).exists():
            shutil.rmtree(repo_root / d)
            removed.append(d)

    wrapper = Path.home() / ".local" / "bin" / "glance"
    if wrapper.exists():
        wrapper.unlink()
        removed.append("glance wrapper")

    if (repo_root / ".glance").exists():
        shutil.rmtree(repo_root / ".glance")
        removed.append(".glance data")

    if (repo_root / ".env").exists():
        (repo_root / ".env").unlink()
        removed.append(".env")

    if removed:
        print(f"Removed: {', '.join(removed)}")
    print("Glance uninstalled.")


def cmd_conflict(args):
    import asyncio
    import os

    from glance.conflict import ConflictAnalyzer, ConflictDetector, ConflictReporter
    from glance.llm.client import create_llm_client

    repo_root = Path(args.repo) if args.repo else Path.cwd()
    detector = ConflictDetector(repo_root)

    print("Scanning for merge conflicts...")

    conflicts = detector.get_all_conflicts()

    if not conflicts:
        print("✅ No merge conflicts detected.")
        return

    total = sum(len(c.conflicts) for c in conflicts)
    print(f"⚠️ Found {total} conflicts in {len(conflicts)} files\n")

    if args.analyze and args.llm_key:
        from dotenv import load_dotenv

        load_dotenv(repo_root / ".env")
        base_url = os.getenv("LLM_BASE_URL", "")

        async def analyze_and_report():
            client = create_llm_client(
                provider="zhipuai",
                api_key=args.llm_key,
                model=args.model or os.getenv("LLM_MODEL", "glm-4-flash"),
                base_url=base_url or None,
            )
            analyzer = ConflictAnalyzer(client)
            reporter = ConflictReporter()

            analyses = []
            for cf in conflicts:
                for region in cf.conflicts:
                    analysis = await analyzer.analyze_conflict(
                        conflict_id=len(analyses) + 1,
                        file_path=region.file_path,
                        start_line=region.start_line,
                        our_version=region.our_content,
                        their_version=region.their_content,
                        context_before=region.context_before,
                        context_after=region.context_after,
                    )
                    analyses.append(analysis)

            report = reporter.generate_report(analyses, total)
            print(report)

        asyncio.run(analyze_and_report())
    else:
        print("\nRun with --analyze --llm-key YOUR_KEY to analyze conflicts")
        for cf in conflicts:
            print(f"\n{cf.path}: {len(cf.conflicts)} conflict(s)")


def main():
    parser = argparse.ArgumentParser(prog="glance", description="Glance AI Code Review CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    dash_parser = subparsers.add_parser("dashboard", help="Interactive TUI dashboard")
    dash_parser.add_argument("--repo", help="Repository root path")
    dash_parser.set_defaults(func=cmd_dashboard)

    cost_parser = subparsers.add_parser("cost", help="Token cost summary")
    cost_parser.add_argument("--repo", help="Repository root path")
    cost_parser.set_defaults(func=cmd_cost)

    mem_parser = subparsers.add_parser("memory", help="Memory summary")
    mem_parser.add_argument("--repo", help="Repository root path")
    mem_parser.set_defaults(func=cmd_memory)

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove Glance completely")
    uninstall_parser.set_defaults(func=cmd_uninstall)

    conflict_parser = subparsers.add_parser("conflict", help="Detect and analyze merge conflicts")
    conflict_parser.add_argument("--repo", help="Repository root path")
    conflict_parser.add_argument(
        "--analyze", action="store_true", help="Use LLM to analyze conflicts"
    )
    conflict_parser.add_argument("--llm-key", help="LLM API key for analysis")
    conflict_parser.add_argument("--model", help="LLM model (default: glm-4-flash)")
    conflict_parser.set_defaults(func=cmd_conflict)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
