"""Signature Mapper - Extract code signatures using ctags.

Provides structural context for code review without sending full files.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("glance.signature")


@dataclass
class Signature:
    """Represents a code signature (function, class, etc.)."""

    name: str
    kind: str  # function, class, method, variable, etc.
    file_path: str
    line_number: int
    signature: str = ""
    scope: str = ""
    language: str = ""


@dataclass
class RepoMap:
    """Map of repository signatures."""

    signatures: list[Signature] = field(default_factory=list)
    files_scanned: int = 0
    total_signatures: int = 0
    error: str | None = None

    def get_functions(self) -> list[Signature]:
        """Get all function signatures."""
        return [s for s in self.signatures if s.kind in ("function", "method")]

    def get_classes(self) -> list[Signature]:
        """Get all class signatures."""
        return [s for s in self.signatures if s.kind == "class"]

    def get_by_file(self, file_path: str) -> list[Signature]:
        """Get signatures for a specific file."""
        return [s for s in self.signatures if s.file_path == file_path]

    def search(self, query: str) -> list[Signature]:
        """Search signatures by name."""
        query_lower = query.lower()
        return [s for s in self.signatures if query_lower in s.name.lower()]

    def to_dict(self) -> dict:
        """Convert to dictionary for LLM context.

        Returns:
            Dict representation suitable for JSON serialization.
        """
        return {
            "files": {},
            "scopes": {},
            "total_signatures": self.total_signatures,
            "files_scanned": self.files_scanned,
            "error": self.error,
        }


def format_signature_map(repo_map: RepoMap | None, max_entries: int = 100) -> str:
    """Format repository map as readable string for LLM context.

    Args:
        repo_map: Repository map to format.
        max_entries: Maximum number of entries to include.

    Returns:
        Formatted string with key signatures.
    """
    if not repo_map:
        return "No repository signature data available."

    lines = [
        "## Repository Structure",
        "",
        f"Total signatures: {repo_map.total_signatures}",
        f"Files scanned: {repo_map.files_scanned}",
        "",
    ]

    # Group by file
    by_file: dict[str, list[Signature]] = {}
    for sig in repo_map.signatures:
        if sig.file_path not in by_file:
            by_file[sig.file_path] = []
        by_file[sig.file_path].append(sig)

    lines.append("### Files and their symbols:")
    lines.append("")

    count = 0
    for file_path, sigs in by_file.items():
        if count >= max_entries:
            lines.append(f"... and {len(by_file) - count} more files")
            break

        lines.append(f"**{file_path}**")
        for sig in sigs[:10]:  # Limit per file
            sig_info = f"  - {sig.kind}: {sig.name}"
            if sig.signature:
                sig_info += f"({sig.signature[:50]})"
            lines.append(sig_info)
        lines.append("")
        count += 1

    if repo_map.error:
        lines.append(f"Note: {repo_map.error}")

    return "\n".join(lines)


class SignatureMapper:
    """Extracts code signatures using universal-ctags.

    Provides lightweight structural context for code review:
    - Function and method signatures
    - Class definitions
    - Variable declarations
    - Interface definitions
    """

    # Supported file extensions and their languages
    EXTENSION_MAP = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".jsx": "JavaScript",
        ".tsx": "TypeScript",
        ".java": "Java",
        ".go": "Go",
        ".rs": "Rust",
        ".zig": "Zig",
        ".c": "C",
        ".cpp": "C++",
        ".h": "C",
        ".hpp": "C++",
        ".rb": "Ruby",
        ".php": "PHP",
        ".kt": "Kotlin",
        ".swift": "Swift",
    }

    # Kind mappings for different languages
    KIND_DISPLAY = {
        "f": "function",
        "m": "method",
        "c": "class",
        "i": "interface",
        "v": "variable",
        "C": "constant",
        "s": "struct",
        "e": "enum",
        "E": "enumerator",
        "g": "enum",
        "n": "namespace",
        "p": "package",
        "P": "property",
        "t": "typedef",
        "T": "type",
    }

    def __init__(self, workdir: str | Path = "."):
        """Initialize the signature mapper.

        Args:
            workdir: Working directory to scan.
        """
        self.workdir = Path(workdir)
        self._ctags_available: bool | None = None

    def check_ctags_available(self) -> bool:
        """Check if universal-ctags is installed."""
        if self._ctags_available is not None:
            return self._ctags_available

        try:
            result = subprocess.run(
                ["ctags", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Universal ctags includes "Universal" in version string
            self._ctags_available = "Universal" in result.stdout or result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            self._ctags_available = False

        return self._ctags_available

    def map_repository(
        self,
        file_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> RepoMap:
        """Alias for scan_repository for backward compatibility."""
        return self.scan_repository(file_patterns, exclude_patterns)

    def scan_repository(
        self,
        file_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> RepoMap:
        """Scan the repository and extract all signatures.

        Args:
            file_patterns: File patterns to include (e.g., ["*.py", "*.js"]).
            exclude_patterns: Patterns to exclude (e.g., ["node_modules", "vendor"]).

        Returns:
            RepoMap with all discovered signatures.
        """
        if not self.check_ctags_available():
            # Fall back to regex-based extraction
            return self._scan_with_regex(file_patterns)

        try:
            return self._scan_with_ctags(file_patterns, exclude_patterns)
        except Exception as e:
            logger.warning(f"ctags scan failed, falling back to regex: {e}")
            return self._scan_with_regex(file_patterns)

    def _scan_with_ctags(
        self,
        file_patterns: list[str] | None,
        exclude_patterns: list[str] | None,
    ) -> RepoMap:
        """Use ctags to extract signatures."""
        cmd = [
            "ctags",
            "--output-format=json",
            "--fields=+n+K+s+S+l",
            "--extras=+q",
            "-R",
        ]

        # Add exclude patterns
        for pattern in exclude_patterns or []:
            cmd.extend(["--exclude", pattern])

        # Add file patterns if specified
        if file_patterns:
            for pattern in file_patterns:
                cmd.append(pattern)
        else:
            # Default: scan all supported file types
            for ext in self.EXTENSION_MAP.keys():
                cmd.extend(["--languages", f"+{self.EXTENSION_MAP[ext]}"])

        try:
            result = subprocess.run(
                cmd,
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return RepoMap(error="ctags scan timed out")

        signatures: list[Signature] = []
        files_seen = set()

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            try:
                import json

                data = json.loads(line)

                sig = Signature(
                    name=data.get("name", ""),
                    kind=self._normalize_kind(data.get("kind", "")),
                    file_path=data.get("path", ""),
                    line_number=data.get("line", 0),
                    signature=data.get("signature", "") or data.get("pattern", ""),
                    scope=data.get("scope", ""),
                    language=data.get("language", ""),
                )

                signatures.append(sig)
                files_seen.add(sig.file_path)

            except (json.JSONDecodeError, KeyError):
                continue

        return RepoMap(
            signatures=signatures,
            files_scanned=len(files_seen),
            total_signatures=len(signatures),
        )

    def _scan_with_regex(
        self,
        file_patterns: list[str] | None,
    ) -> RepoMap:
        """Fall back to regex-based signature extraction."""
        signatures: list[Signature] = []
        files_scanned = 0

        # Get files to scan
        patterns = file_patterns or [f"*{ext}" for ext in self.EXTENSION_MAP.keys()]

        for pattern in patterns:
            for file_path in self.workdir.glob(f"**/{pattern}"):
                # Skip hidden and common exclude dirs
                if any(part.startswith(".") for part in file_path.parts):
                    continue
                if any(
                    skip in file_path.parts
                    for skip in ["node_modules", "vendor", "venv", "__pycache__"]
                ):
                    continue

                file_sigs = self._extract_signatures_regex(file_path)
                signatures.extend(file_sigs)
                files_scanned += 1

        return RepoMap(
            signatures=signatures,
            files_scanned=files_scanned,
            total_signatures=len(signatures),
        )

    def _extract_signatures_regex(self, file_path: Path) -> list[Signature]:
        """Extract signatures from a file using regex."""
        import re

        ext = file_path.suffix
        language = self.EXTENSION_MAP.get(ext, "Unknown")

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return []

        signatures: list[Signature] = []

        if ext == ".py":
            # Python function and class definitions
            func_pattern = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)", re.MULTILINE)
            class_pattern = re.compile(r"^\s*class\s+(\w+)(?:\s*\([^)]*\))?:", re.MULTILINE)

            for match in func_pattern.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                signatures.append(
                    Signature(
                        name=match.group(1),
                        kind="function",
                        file_path=str(file_path.relative_to(self.workdir)),
                        line_number=line_num,
                        signature=f"def {match.group(1)}({match.group(2)})",
                        language=language,
                    )
                )

            for match in class_pattern.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                signatures.append(
                    Signature(
                        name=match.group(1),
                        kind="class",
                        file_path=str(file_path.relative_to(self.workdir)),
                        line_number=line_num,
                        signature=f"class {match.group(1)}",
                        language=language,
                    )
                )

        elif ext in (".js", ".jsx", ".ts", ".tsx"):
            # JavaScript/TypeScript
            func_pattern = re.compile(
                r"(?:export\s+)?(?:async\s+)?(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>)",
                re.MULTILINE,
            )
            class_pattern = re.compile(r"(?:export\s+)?class\s+(\w+)", re.MULTILINE)

            for match in func_pattern.finditer(content):
                name = match.group(1) or match.group(2)
                line_num = content[: match.start()].count("\n") + 1
                signatures.append(
                    Signature(
                        name=name,
                        kind="function",
                        file_path=str(file_path.relative_to(self.workdir)),
                        line_number=line_num,
                        signature=match.group(0)[:100],
                        language=language,
                    )
                )

            for match in class_pattern.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                signatures.append(
                    Signature(
                        name=match.group(1),
                        kind="class",
                        file_path=str(file_path.relative_to(self.workdir)),
                        line_number=line_num,
                        signature=f"class {match.group(1)}",
                        language=language,
                    )
                )

        elif ext == ".go":
            # Go
            func_pattern = re.compile(r"func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(", re.MULTILINE)
            type_pattern = re.compile(r"type\s+(\w+)\s+(?:struct|interface)", re.MULTILINE)

            for match in func_pattern.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                signatures.append(
                    Signature(
                        name=match.group(1),
                        kind="function",
                        file_path=str(file_path.relative_to(self.workdir)),
                        line_number=line_num,
                        signature=match.group(0)[:100],
                        language=language,
                    )
                )

            for match in type_pattern.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                signatures.append(
                    Signature(
                        name=match.group(1),
                        kind="class",
                        file_path=str(file_path.relative_to(self.workdir)),
                        line_number=line_num,
                        signature=match.group(0)[:100],
                        language=language,
                    )
                )

        elif ext in (".rs", ".zig"):
            # Rust/Zig
            func_pattern = re.compile(r"(?:pub\s+)?fn\s+(\w+)\s*[<(]", re.MULTILINE)
            struct_pattern = re.compile(r"(?:pub\s+)?(?:struct|enum)\s+(\w+)", re.MULTILINE)

            for match in func_pattern.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                signatures.append(
                    Signature(
                        name=match.group(1),
                        kind="function",
                        file_path=str(file_path.relative_to(self.workdir)),
                        line_number=line_num,
                        signature=match.group(0)[:100],
                        language=language,
                    )
                )

            for match in struct_pattern.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                signatures.append(
                    Signature(
                        name=match.group(1),
                        kind="class",
                        file_path=str(file_path.relative_to(self.workdir)),
                        line_number=line_num,
                        signature=match.group(0)[:100],
                        language=language,
                    )
                )

        return signatures

    def _normalize_kind(self, kind: str) -> str:
        """Normalize ctags kind to readable form."""
        return self.KIND_DISPLAY.get(kind, kind.lower() if kind else "unknown")

    def get_file_context(self, file_path: str, repo_map: RepoMap | None = None) -> str:
        """Get formatted context for a file's signatures.

        Args:
            file_path: Path to the file.
            repo_map: Optional pre-computed repo map.

        Returns:
            Formatted string with file's signatures.
        """
        if repo_map is None:
            repo_map = self.scan_repository([file_path])

        sigs = repo_map.get_by_file(file_path)
        if not sigs:
            return ""

        lines = [f"Signatures in {file_path}:"]
        for sig in sorted(sigs, key=lambda s: s.line_number):
            lines.append(f"  L{sig.line_number}: {sig.kind} {sig.name}({sig.signature[:50]})")

        return "\n".join(lines)


def map_signatures(workdir: str = ".") -> RepoMap:
    """Convenience function to map repository signatures.

    Args:
        workdir: Working directory.

    Returns:
        RepoMap with all discovered signatures.
    """
    mapper = SignatureMapper(workdir)
    return mapper.scan_repository()
