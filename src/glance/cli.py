"""Glance CLI - Command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def cmd_dashboard(args):
    """Show review statistics dashboard."""
    from glance.tui import main as tui_main

    tui_main()


def cmd_cost(args):
    """Show token cost summary."""
    from glance.integrations.cost_tracker import load_cost_tracker

    repo_root = Path(args.repo) if args.repo else Path.cwd()
    tracker = load_cost_tracker(repo_root)
    print(tracker.get_summary())


def cmd_memory(args):
    """Show memory summary."""
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


def main():
    parser = argparse.ArgumentParser(prog="glance", description="Glance AI Code Review CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Show review statistics")
    dash_parser.add_argument("--repo", help="Repository root path")
    dash_parser.set_defaults(func=cmd_dashboard)

    # cost
    cost_parser = subparsers.add_parser("cost", help="Show token cost summary")
    cost_parser.add_argument("--repo", help="Repository root path")
    cost_parser.set_defaults(func=cmd_cost)

    # memory
    mem_parser = subparsers.add_parser("memory", help="Show memory summary")
    mem_parser.add_argument("--repo", help="Repository root path")
    mem_parser.set_defaults(func=cmd_memory)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
