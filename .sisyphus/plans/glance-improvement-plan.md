# Glance Improvement Plan

**Generated**: 2026-04-07  
**Status**: Proposed — awaiting approval

---

## Phase 1: Critical Fixes (P0 — Must Fix Before Next Release)

These are bugs that will crash the app or create security holes in production.

### 1.1 Fix Exception Collision in `base.py`
**Problem**: Lines 30-32 unconditionally overwrite imported OpenAI exceptions with bare `Exception`, making all `except RateLimitError` branches catch EVERY exception.

**Fix**:
```python
try:
    from openai import APIError, RateLimitError, Timeout
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    APIError = Exception       # Only define fallback if import failed
    RateLimitError = Exception
    Timeout = Exception
```

**Files**: `src/glance/agents/base.py`  
**Effort**: 5 min  
**Risk**: None — pure fix

---

### 1.2 Replace Deprecated `asyncio.coroutine` in `orchestrator.py`
**Problem**: `asyncio.coroutine` was removed in Python 3.11. Crashes on modern Python.

**Fix**: Replace `asyncio.coroutine(lambda: None)()` with a simple `async def _noop(): return None` helper, or just append `None` directly to the tasks list and handle it in results.

**Files**: `src/glance/orchestrator.py` (lines 453, 464, 475)  
**Effort**: 5 min  
**Risk**: None

---

### 1.3 Re-enable Secret Scanner
**Problem**: The gatekeeper that blocks PRs with hardcoded secrets is commented out. PRs with secrets get sent to third-party LLM APIs.

**Fix**: Uncomment lines 172-177 in `orchestrator.py`.

**Files**: `src/glance/orchestrator.py`  
**Effort**: 2 min  
**Risk**: None — but may start blocking PRs that previously passed

---

## Phase 2: Data Integrity & Functional Fixes (P1)

Features that exist but don't work correctly.

### 2.1 Fix Token Cost Tracking
**Problem**: Always records `input_tokens=0, output_tokens=0`. The cost tracking feature is completely non-functional.

**Fix**: Propagate `tokens_used` from each `AgentReview` into the `TokenUsage` record. Sum up architect + bug_hunter + white_hat tokens.

**Files**: `src/glance/orchestrator.py` (lines 373-392)  
**Effort**: 15 min

---

### 2.2 Pass Full Context to ALL Agents
**Problem**: Only Architect receives review history, memory, test coverage, and team rules. BugHunter and WhiteHat get a bare CI status string.

**Fix**: Build the same rich `architect_ci_context` JSON and pass it to all three agents in both `_run_parallel_agents` and `_run_sequential_agents`.

**Files**: `src/glance/orchestrator.py` (lines 456-475, 536-558)  
**Effort**: 20 min

---

### 2.3 Unify Prompt System — Eliminate Duplicate Prompts
**Problem**: Two sets of prompts exist:
- `prompts/*.md` — rich, detailed, never used
- `agents/*.py` — hardcoded shorter strings, actually used

**Fix**: Load prompts from `prompts/*.md` files at runtime in each agent's `system_prompt` property. Delete hardcoded strings. This makes prompt editing actually work.

**Files**: `src/glance/agents/architect.py`, `bug_hunter.py`, `white_hat.py`, `arbitrator.py`  
**Effort**: 30 min

---

### 2.4 Close HTTP Clients After Use
**Problem**: `OpenAIClient`, `AnthropicClient`, `GoogleClient` have `close()` methods but orchestrator never calls them. Connection leak in TUI mode.

**Fix**: Add `async def close()` to orchestrator that closes `self.raw_client` if it has a `close()` method. Call it at the end of `run()`.

**Files**: `src/glance/orchestrator.py`, `src/glance/llm/client.py`  
**Effort**: 15 min

---

### 2.5 Integrate Conflict Detection into Main Workflow
**Problem**: The `conflict/` module is fully built but never called from anywhere. It's dead code.

**Fix**: Add a conflict detection step in the orchestrator pipeline (after diff fetch, before review). If conflicts found, post a conflict report comment instead of running the review.

**Files**: `src/glance/orchestrator.py`, `src/glance/conflict/`  
**Effort**: 1 hour

---

### 2.6 Fix Conflict Analyzer LLM Client Incompatibility
**Problem**: `ConflictAnalyzer` expects `llm_client.chat()` returning `LLMResponse`. The orchestrator uses `LLMClientAdapter` which has `chat.completions.create()`.

**Fix**: Either (a) make `ConflictAnalyzer` accept `LLMClientAdapter`, or (b) add a `.chat()` shim to `LLMClientAdapter`.

**Files**: `src/glance/conflict/analyzer.py` or `src/glance/llm/client.py`  
**Effort**: 15 min

---

## Phase 3: Quality Improvements (P2)

Things that work but are fragile, inaccurate, or incomplete.

### 3.1 Fix Conflict Reporter `hasattr` Bug
**Problem**: `analysis.conflicts` doesn't exist on `ConflictAnalysis` — always shows `?`.

**Files**: `src/glance/conflict/reporter.py` line 61  
**Effort**: 2 min

---

### 3.2 Add MEDIUM Risk Level to Conflict Analysis
**Problem**: Only `CRITICAL` and `LOW` exist. No nuance.

**Files**: `src/glance/conflict/analyzer.py`  
**Effort**: 2 min

---

### 3.3 Fix `quick_classify()` Naive Classification
**Problem**: Same line count + similar length = "LOW risk". But `if user.is_admin:` → `if user.is_admin and user.is_active:` has same line count but is a logic change.

**Fix**: Add keyword-based diff analysis. Check for control flow keywords (`if`, `for`, `while`, `return`, `raise`, `async`) to detect logic changes vs cosmetic changes.

**Files**: `src/glance/conflict/analyzer.py`  
**Effort**: 20 min

---

### 3.4 Stabilize Issue ID Generation for PR Response Tracker
**Problem**: `issue_id = f"{file_path}:{line_number}:{message[:50]}"` — line numbers shift between commits, LLM rephrases messages. Same bug gets new IDs → false "fixed" detections.

**Fix**: Use a content-based hash: hash the `file_path` + first 3 words of `message` + `category`. Ignore line numbers for identity.

**Files**: `src/glance/integrations/pr_response.py`  
**Effort**: 15 min

---

### 3.5 Auto-Populate `recurring_mistakes` and `strengths` in Memory
**Problem**: These fields exist but are never written to. Always empty.

**Fix**: In `save_memory`, analyze `common_issue_types` to auto-populate `recurring_mistakes` (top 3 categories with 3+ occurrences). Add `strengths` based on categories with 0 occurrences across 5+ PRs.

**Files**: `src/glance/integrations/memory.py`  
**Effort**: 30 min

---

### 3.6 Sanitize TUI `.env` Input
**Problem**: User input written directly to `.env` without newline sanitization. Could inject additional env vars.

**Fix**: Strip newlines and `=` from input values in `save_env()`.

**Files**: `src/glance/tui.py`  
**Effort**: 5 min

---

### 3.7 Fix Arbitrator Prompt Verdict Label Conflict
**Problem**: System prompt says `APPROVE/REQUEST_CHANGES/BLOCK_SECURITY` but output format says `pass/concerns/critical`. LLM gets confused.

**Fix**: Align system prompt verdict labels with output format schema.

**Files**: `src/glance/agents/arbitrator.py`  
**Effort**: 5 min

---

### 3.8 Add Retry Logic for JSON Parse Failures
**Problem**: When LLM returns malformed JSON, review returns empty with `verdict="concerns"`. No retry.

**Fix**: In `BaseAgent._parse_response`, if JSON parse fails, retry once with a "please return valid JSON" wrapper prompt.

**Files**: `src/glance/agents/base.py`  
**Effort**: 20 min

---

## Phase 4: Future Enhancements (Nice-to-Have)

### 4.1 Add Timeout to Agent Execution
Wrap `asyncio.gather` with `asyncio.wait_for` to prevent infinite hangs.

### 4.2 Review History Auto-Mark Fixed
When saving history, check if previous findings' file+pattern still exists in current review. Auto-mark as "fixed" if not found.

### 4.3 Add Config Validation for Empty API Keys
Make `llm_api_key` required or validate non-empty at startup.

### 4.4 Conflict Detection via Git Command (Not File Scanning)
Use `git diff --check` or `git status --porcelain` instead of `rglob("*")` for conflict detection. 100x faster.

---

## Execution Order

```
Phase 1 (P0):  1.1 → 1.2 → 1.3          (~12 min total)
Phase 2 (P1):  2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6  (~2 hours)
Phase 3 (P2):  3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6 → 3.7 → 3.8  (~2 hours)
Phase 4:       Future backlog
```

**Total estimated effort**: ~4.5 hours
