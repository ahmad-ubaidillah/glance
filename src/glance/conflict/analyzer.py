"""Conflict Analyzer - Analyze conflicts using LLM."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger("glance.conflict")


class RiskLevel(Enum):
    CRITICAL = "critical"
    LOW = "low"


@dataclass
class ConflictAnalysis:
    conflict_id: int
    file_path: str
    start_line: int
    our_version: str
    their_version: str
    risk_level: RiskLevel
    suggested_choice: str
    reasoning: str
    hybrid_version: str | None = None


SYSTEM_PROMPT = """You are a code conflict analyzer for git merge conflicts.

Given a merge conflict between two versions of code, analyze which version is better and why.

Consider:
1. Code quality - which is cleaner, more maintainable?
2. Bug risk - which could introduce bugs?
3. Backward compatibility - which preserves existing behavior?
4. Best practices - which follows better patterns?
5. Intent - what was the purpose of each change?

Respond with JSON only, no markdown:
{
    "risk_level": "critical" or "low",
    "suggested_choice": "our" or "their" or "hybrid",
    "reasoning": "brief explanation (1-2 sentences)",
    "hybrid_version": "if hybrid, provide the merged version"
}"""


class ConflictAnalyzer:
    def __init__(self, llm_client: Any, model: str = "glm-4-flash"):
        self.llm_client = llm_client
        self.model = model

    async def analyze_conflict(
        self,
        conflict_id: int,
        file_path: str,
        start_line: int,
        our_version: str,
        their_version: str,
        context_before: str = "",
        context_after: str = "",
    ) -> ConflictAnalysis:
        prompt = self._build_prompt(
            file_path, our_version, their_version, context_before, context_after
        )

        try:
            response = await self._call_llm(prompt)
            result = json.loads(response)

            return ConflictAnalysis(
                conflict_id=conflict_id,
                file_path=file_path,
                start_line=start_line,
                our_version=our_version,
                their_version=their_version,
                risk_level=RiskLevel(result.get("risk_level", "low")),
                suggested_choice=result.get("suggested_choice", "our"),
                reasoning=result.get("reasoning", "No analysis provided"),
                hybrid_version=result.get("hybrid_version"),
            )
        except (json.JSONDecodeError, KeyError, asyncio.TimeoutError) as e:
            logger.warning(f"LLM analysis failed: {e}, using default")
            return self._default_analysis(
                conflict_id, file_path, start_line, our_version, their_version
            )

    def _build_prompt(
        self,
        file_path: str,
        our_version: str,
        their_version: str,
        context_before: str,
        context_after: str,
    ) -> str:
        context = ""
        if context_before:
            context += f"\n\nContext before:\n{context_before}\n"
        if context_after:
            context += f"\nContext after:\n{context_after}\n"

        return f"""Analyze this merge conflict in file: {file_path}

OUR VERSION (current branch):
```code
{our_version}
```

THEIR VERSION (incoming branch):
```code
{their_version}
```
{context}

Return JSON analysis."""

    async def _call_llm(self, prompt: str) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        if hasattr(self.llm_client, "chat"):
            response = await self.llm_client.chat(
                messages=messages,
                temperature=0.3,
                max_tokens=500,
            )
            return response.content

        raise ValueError("LLM client must have chat() method")

    def _default_analysis(
        self,
        conflict_id: int,
        file_path: str,
        start_line: int,
        our_version: str,
        their_version: str,
    ) -> ConflictAnalysis:
        return ConflictAnalysis(
            conflict_id=conflict_id,
            file_path=file_path,
            start_line=start_line,
            our_version=our_version,
            their_version=their_version,
            risk_level=RiskLevel.LOW,
            suggested_choice="our",
            reasoning="Default: kept our version (no LLM analysis available)",
        )

    async def analyze_batch(
        self,
        conflicts: list[dict],
    ) -> list[ConflictAnalysis]:
        tasks = []
        for i, c in enumerate(conflicts):
            task = self.analyze_conflict(
                conflict_id=i + 1,
                file_path=c["file_path"],
                start_line=c["start_line"],
                our_version=c["our_version"],
                their_version=c["their_version"],
                context_before=c.get("context_before", ""),
                context_after=c.get("context_after", ""),
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        analyses = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                analyses.append(
                    self._default_analysis(
                        i + 1,
                        conflicts[i]["file_path"],
                        conflicts[i]["start_line"],
                        conflicts[i]["our_version"],
                        conflicts[i]["their_version"],
                    )
                )
            else:
                analyses.append(result)

        return analyses


def quick_classify(our_version: str, their_version: str) -> tuple[RiskLevel, str, str]:
    our_stripped = our_version.strip()
    their_stripped = their_version.strip()

    if our_stripped == their_stripped:
        return RiskLevel.LOW, "both", "Versions are identical"

    our_len = len(our_stripped)
    their_len = len(their_stripped)
    len_diff = abs(our_len - their_len) / max(our_len, their_len, 1)

    if len_diff < 0.1 and len(our_stripped.splitlines()) == len(their_stripped.splitlines()):
        return RiskLevel.LOW, "either", "Minor changes (whitespace, naming)"

    return RiskLevel.CRITICAL, "unknown", "Significant logic differences"
