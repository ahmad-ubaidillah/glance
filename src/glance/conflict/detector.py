"""Conflict Detector - Parse git merge conflicts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConflictRegion:
    file_path: str
    start_line: int
    our_content: str
    their_content: str
    context_before: str
    context_after: str


@dataclass
class ConflictFile:
    path: str
    conflicts: list[ConflictRegion]
    is_binary: bool = False


class ConflictDetector:
    CONFLICT_START = "<<<<<<< "
    CONFLICT_SEPARATOR = "======="
    CONFLICT_END = ">>>>>>> "

    def __init__(self, repo_root: Path | str = "."):
        self.repo_root = Path(repo_root)

    def find_conflicted_files(self) -> list[str]:
        files = []
        for path in self.repo_root.rglob("*"):
            if path.is_file() and not self._is_ignored(path):
                if self._has_conflicts(path):
                    files.append(str(path.relative_to(self.repo_root)))
        return sorted(files)

    def _is_ignored(self, path: Path) -> bool:
        gitignore = self.repo_root / ".gitignore"
        if not gitignore.exists():
            return False
        ignored_patterns = gitignore.read_text().splitlines()
        for pattern in ignored_patterns:
            pattern = pattern.strip()
            if not pattern or pattern.startswith("#"):
                continue
            if path.match(pattern):
                return True
        return False

    def _has_conflicts(self, path: Path) -> bool:
        try:
            return self.CONFLICT_START in path.read_text(errors="ignore")
        except (OSError, PermissionError):
            return False

    def parse_file(self, file_path: str) -> ConflictFile | None:
        path = self.repo_root / file_path
        if not path.exists():
            return None

        try:
            content = path.read_text(errors="ignore")
        except (OSError, PermissionError):
            return None

        if self.CONFLICT_START not in content:
            return None

        conflicts = self._parse_conflicts(content, file_path)
        return ConflictFile(path=file_path, conflicts=conflicts)

    def _parse_conflicts(self, content: str, file_path: str) -> list[ConflictRegion]:
        conflicts = []
        lines = content.splitlines()

        i = 0
        conflict_start = -1
        context_before = []

        while i < len(lines):
            line = lines[i]

            if line.startswith(self.CONFLICT_START):
                conflict_start = i
                branch_name = line[len(self.CONFLICT_START) :].strip()

                # Collect context before
                context_before = []
                for j in range(i - 1, -1, -1):
                    prev = lines[j]
                    if prev.startswith(("<<<<<<<", "=======", ">>>>>>")):
                        break
                    context_before.insert(0, prev)
                    if len(context_before) >= 5:
                        break

                our_lines = []
                i += 1

                # Read our content until separator
                while i < len(lines):
                    if lines[i].startswith(self.CONFLICT_SEPARATOR):
                        i += 1
                        break
                    our_lines.append(lines[i])
                    i += 1

                their_lines = []
                while i < len(lines):
                    if lines[i].startswith(self.CONFLICT_END):
                        i += 1
                        break
                    their_lines.append(lines[i])
                    i += 1

                # Collect context after
                context_after = []
                for j in range(i, min(i + 5, len(lines))):
                    nxt = lines[j]
                    if nxt.startswith(("<<<<<<<", "=======", ">>>>>>")):
                        break
                    context_after.append(nxt)

                conflicts.append(
                    ConflictRegion(
                        file_path=file_path,
                        start_line=conflict_start + 1,
                        our_content="\n".join(our_lines),
                        their_content="\n".join(their_lines),
                        context_before="\n".join(context_before),
                        context_after="\n".join(context_after),
                    )
                )
            else:
                i += 1

        return conflicts

    def get_all_conflicts(self) -> list[ConflictFile]:
        files = self.find_conflicted_files()
        result = []
        for f in files:
            parsed = self.parse_file(f)
            if parsed and parsed.conflicts:
                result.append(parsed)
        return result


def detect_conflicts(repo_root: Path | str = ".") -> list[ConflictFile]:
    detector = ConflictDetector(repo_root)
    return detector.get_all_conflicts()
