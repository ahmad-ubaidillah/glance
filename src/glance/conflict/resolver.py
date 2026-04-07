"""Conflict Resolver - Apply conflict resolutions."""

from __future__ import annotations

import re
from pathlib import Path


class ConflictResolver:
    CONFLICT_START = "<<<<<<< "
    CONFLICT_SEPARATOR = "======="
    CONFLICT_END = ">>>>>>> "

    def __init__(self, repo_root: Path | str = "."):
        self.repo_root = Path(repo_root)

    def resolve_file(self, file_path: str, choices: dict[int, str]) -> bool:
        path = self.repo_root / file_path
        if not path.exists():
            return False

        try:
            content = path.read_text()
        except (OSError, PermissionError):
            return False

        if self.CONFLICT_START not in content:
            return False

        resolved = self._apply_resolutions(content, choices)
        path.write_text(resolved)
        return True

    def _apply_resolutions(self, content: str, choices: dict[int, str]) -> str:
        lines = content.splitlines()
        result = []
        i = 0
        conflict_count = 0

        while i < len(lines):
            line = lines[i]

            if line.startswith(self.CONFLICT_START):
                conflict_count += 1
                choice = choices.get(conflict_count, "A")

                our_lines = []
                their_lines = []
                i += 1

                while i < len(lines):
                    if lines[i].startswith(self.CONFLICT_SEPARATOR):
                        i += 1
                        break
                    our_lines.append(lines[i])
                    i += 1

                while i < len(lines):
                    if lines[i].startswith(self.CONFLICT_END):
                        i += 1
                        break
                    their_lines.append(lines[i])
                    i += 1

                if choice == "A":
                    result.extend(our_lines)
                elif choice == "B":
                    result.extend(their_lines)
                elif choice == "C":
                    result.extend(our_lines)
                    result.extend(their_lines)
                else:
                    result.append(f"<<<<<<< RESOLVED:{conflict_count}")
                    result.extend(our_lines)
                    result.append("=======")
                    result.extend(their_lines)
                    result.append(">>>>>>> RESOLVED")

            else:
                result.append(line)
                i += 1

        return "\n".join(result)

    def resolve_all(self, file_choices: dict[str, dict[int, str]]) -> int:
        resolved = 0
        for file_path, choices in file_choices.items():
            if self.resolve_file(file_path, choices):
                resolved += 1
        return resolved
