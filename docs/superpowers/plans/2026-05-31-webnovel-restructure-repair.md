# Webnovel Restructure Repair Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents are explicitly authorized) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the novel project after outline restructuring and plugin migration by rebuilding a single trustworthy canon chain, then hardening `webnovel-writer` so future writing cannot proceed from stale or mixed-generation context.

**Architecture:** Treat the current outline and accepted chapter text as editorial canon, but treat existing `.webnovel/*` and `.story-system/*` as suspect until audited. Add deterministic audit and repair commands first, then add hard prewrite/commit gates, then rebuild projections from a verified chapter ledger. Do not resume automated chapter writing until the runtime is `mainline_ready=true` for the next chapter.

**Tech Stack:** Python 3.13, pytest, Pydantic, SQLite (`.webnovel/index.db`), JSON artifacts under `.story-system/`, existing `webnovel.py` unified CLI.

---

## Non-Negotiable Rules

- Freeze new chapter generation until Task 7 passes.
- Do not delete existing artifacts during audit. Move stale files into an archive only after a dry-run report is reviewed.
- Never treat a backfilled commit as proof that the writing step originally used that context. Backfilled commits must carry explicit provenance.
- The current detailed outline and the current chapter text are editorial canon; `.webnovel/state.json`, summaries, memory, vectors, and index are derived read models.
- `MASTER_SETTING` is book-level. Chapter-level refresh must not overwrite it with a chapter goal.

## Scope Split

This plan has two tracks:

1. **Book repair:** Build a chapter provenance ledger, repair contracts/commits/projections for the existing 1-33 chapters, and archive stale snapshots.
2. **Plugin repair:** Fix command/document drift, volume numbering, prewrite gate, and commit validation so the same failure mode cannot recur.

These tracks are coupled at the rebuild command: code first, then one-time repair of this book.

## File Structure

### Create

- `webnovel-writer/scripts/data_modules/story_repair/__init__.py`
  - Package boundary for audit/rebuild helpers.
- `webnovel-writer/scripts/data_modules/story_repair/outline_catalog.py`
  - Parse detailed outline files into chapter records with volume, chapter, title, goal, time anchor, hook, and source hash.
- `webnovel-writer/scripts/data_modules/story_repair/provenance_auditor.py`
  - Compare outline/body/contracts/commits/projections and classify each chapter as native, backfilled, missing, stale, or inconsistent.
- `webnovel-writer/scripts/data_modules/story_repair/rebuild_service.py`
  - Dry-run/apply service for regenerating story contracts, repair commits, summaries, and projections.
- `webnovel-writer/scripts/data_modules/story_repair/archive_service.py`
  - Move stale snapshots/tmp files to `.webnovel/archive/restructure-YYYYMMDD/` with manifest.
- `webnovel-writer/scripts/data_modules/story_prewrite_gate.py`
  - Strict write-readiness validation used by CLI, context manager, and chapter commit.
- `webnovel-writer/scripts/data_modules/tests/test_story_repair_outline_catalog.py`
- `webnovel-writer/scripts/data_modules/tests/test_story_repair_provenance_auditor.py`
- `webnovel-writer/scripts/data_modules/tests/test_story_repair_rebuild_service.py`
- `webnovel-writer/scripts/data_modules/tests/test_story_prewrite_gate.py`

### Modify

- `webnovel-writer/scripts/data_modules/webnovel.py`
  - Add `story-repair audit`, `story-repair rebuild`, `story-repair archive-stale`, and `prewrite-check`.
- `webnovel-writer/scripts/story_system.py`
  - Support `--volume`; convert `(volume, chapter)` to global chapter; stop overwriting `MASTER_SETTING` on per-chapter refresh unless explicitly requested.
- `webnovel-writer/scripts/chapter_outline_loader.py`
  - Consolidate volume resolution with `chapter_paths`; respect explicit volume for outline reads.
- `webnovel-writer/scripts/chapter_paths.py`
  - Formalize volume-local ranges and global conversion behavior.
- `webnovel-writer/scripts/memory_cli.py`
  - Support optional `--volume` in `load-context`, converting to global chapter.
- `webnovel-writer/scripts/data_modules/story_runtime_sources.py`
  - Report exact contract/commit provenance and stale/missing states.
- `webnovel-writer/scripts/data_modules/prewrite_validator.py`
  - Delegate strict structural checks to `story_prewrite_gate`.
- `webnovel-writer/scripts/data_modules/context_manager.py`
  - Expose strict gate result and avoid silently mixing stale state into write context.
- `webnovel-writer/scripts/data_modules/chapter_commit_service.py`
  - Reject accepted commits when required contracts are missing or stale, unless explicit repair mode is used.
- `webnovel-writer/skills/webnovel-write/SKILL.md`
  - Add mandatory `prewrite-check`; fix command examples after CLI changes.
- `webnovel-writer/agents/context-agent.md`
  - In write mode, contract missing is blocking, not legacy fallback.

### Project Files Affected During Apply Phase

- `从迷因资本到智能狂想/.story-system/**`
- `从迷因资本到智能狂想/.webnovel/state.json`
- `从迷因资本到智能狂想/.webnovel/summaries/**`
- `从迷因资本到智能狂想/.webnovel/index.db`
- `从迷因资本到智能狂想/.webnovel/memory_scratchpad.json`
- `从迷因资本到智能狂想/.webnovel/archive/**`
- `从迷因资本到智能狂想/修复报告/story-provenance-audit.md`
- `从迷因资本到智能狂想/修复报告/chapter-ledger.json`

---

## Chunk 1: Audit First, No Mutation

### Task 1: Outline Catalog

**Files:**
- Create: `webnovel-writer/scripts/data_modules/story_repair/outline_catalog.py`
- Test: `webnovel-writer/scripts/data_modules/tests/test_story_repair_outline_catalog.py`

- [ ] **Step 1: Write failing tests for current outline format**

Test cases:
- Parses `### 第 33 章：盘点第一桶金`.
- Captures `目标`, `时间锚点`, `章末未闭合问题`, `钩子`, `关键实体`.
- Reads `> 卷范围: 第1-48章`.
- Computes a stable `outline_hash` from the chapter section.

Run:

```bash
pytest webnovel-writer/scripts/data_modules/tests/test_story_repair_outline_catalog.py -v
```

Expected: fail because module does not exist.

- [ ] **Step 2: Implement parser**

Public API:

```python
@dataclass(frozen=True)
class OutlineChapterRecord:
    volume: int
    chapter_in_volume: int
    global_chapter: int
    title: str
    goal: str
    time_anchor: str
    chapter_span: str
    hook: str
    end_open_question: str
    key_entities: list[str]
    source_file: str
    outline_hash: str
    raw_section: str

def load_outline_catalog(project_root: Path) -> list[OutlineChapterRecord]:
    ...
```

- [ ] **Step 3: Run parser against this book**

Run:

```bash
python -X utf8 - <<'PY'
from pathlib import Path
from webnovel_writer.scripts.data_modules.story_repair.outline_catalog import load_outline_catalog
root = Path("从迷因资本到智能狂想")
rows = load_outline_catalog(root)
print(len(rows))
print(rows[32])
PY
```

Expected: chapter 33 is `盘点第一桶金`; chapter 34 is `赚钱的都在出金群`; volume 1 range is 48, not 50.

- [ ] **Step 4: Commit**

```bash
git add webnovel-writer/scripts/data_modules/story_repair/outline_catalog.py \
        webnovel-writer/scripts/data_modules/tests/test_story_repair_outline_catalog.py
git commit -m "feat: add story repair outline catalog"
```

### Task 2: Provenance Auditor

**Files:**
- Create: `webnovel-writer/scripts/data_modules/story_repair/provenance_auditor.py`
- Modify: `webnovel-writer/scripts/data_modules/webnovel.py`
- Test: `webnovel-writer/scripts/data_modules/tests/test_story_repair_provenance_auditor.py`

- [ ] **Step 1: Write failing tests**

Fixture should contain:
- Body exists for chapter 33.
- Commit exists but chapter/review contracts are missing.
- `.webnovel/state.json` says current chapter 33, location last chapter 19.
- Context snapshot exists for chapter 19 and references future/mismatched data.

Expected audit row:

```json
{
  "chapter": 33,
  "body": "exists",
  "chapter_contract": "missing",
  "review_contract": "missing",
  "commit": "accepted",
  "projection": "done",
  "classification": "accepted_commit_without_write_contracts",
  "repair_required": true
}
```

- [ ] **Step 2: Implement auditor**

Public API:

```python
def audit_project(project_root: Path, start: int = 1, end: int | None = None) -> dict:
    ...
```

Report sections:
- `chapters[]`
- `state_anomalies[]`
- `stale_files[]`
- `contract_anomalies[]`
- `numbering_anomalies[]`
- `recommended_actions[]`

- [ ] **Step 3: Add CLI**

Command:

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py \
  --project-root "从迷因资本到智能狂想" \
  story-repair audit --chapters 1-33 --format json
```

Expected:
- exit code 0
- no files changed
- reports missing contracts for chapters 30-33
- reports stale `context_snapshots/ch0011.json`, `ch0012.json`, `ch0019.json`
- reports state location lagging at chapter 19

- [ ] **Step 4: Commit**

```bash
git add webnovel-writer/scripts/data_modules/story_repair/provenance_auditor.py \
        webnovel-writer/scripts/data_modules/tests/test_story_repair_provenance_auditor.py \
        webnovel-writer/scripts/data_modules/webnovel.py
git commit -m "feat: add story repair provenance audit"
```

---

## Chunk 2: Fix Plugin Drift Before Rebuild

### Task 3: Volume and Chapter CLI Consistency

**Files:**
- Modify: `webnovel-writer/scripts/story_system.py`
- Modify: `webnovel-writer/scripts/memory_cli.py`
- Modify: `webnovel-writer/scripts/data_modules/webnovel.py`
- Modify: `webnovel-writer/scripts/chapter_outline_loader.py`
- Modify: `webnovel-writer/scripts/chapter_paths.py`
- Test: existing CLI tests plus new targeted tests

- [ ] **Step 1: Write failing tests for documented commands**

Commands from the skills must work:

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py \
  --project-root "$PROJECT_ROOT" \
  story-system "盘点第一桶金" --genre "重生都市" --volume 1 --chapter 33 \
  --persist --emit-runtime-contracts --format json
```

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py \
  --project-root "$PROJECT_ROOT" \
  memory-contract load-context --volume 1 --chapter 33
```

Expected before implementation: fail with unrecognized `--volume`.

- [ ] **Step 2: Implement `(volume, chapter)` normalization**

Rules:
- If `--volume` is present, `--chapter` is volume-local.
- Convert to global chapter through `global_from_volume_chapter(project_root, volume, chapter)`.
- Preserve original pair in output metadata:

```json
{
  "volume": 1,
  "chapter_in_volume": 33,
  "global_chapter": 33
}
```

- [ ] **Step 3: Formalize volume ranges**

Update code so volume-local ranges like `"1-50"` do not break global volume resolution for later volumes.

Acceptance:
- Volume 1 chapter 33 -> global 33.
- Volume 2 chapter 1 -> global 49 when volume 1 has range 1-48.
- Global chapter 49 resolves to volume 2 chapter 1.

- [ ] **Step 4: Run tests**

```bash
pytest webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py \
       webnovel-writer/scripts/data_modules/tests/test_chapter_outline_directive.py \
       webnovel-writer/scripts/data_modules/tests/test_story_runtime_sources.py -v
```

- [ ] **Step 5: Commit**

```bash
git add webnovel-writer/scripts/story_system.py \
        webnovel-writer/scripts/memory_cli.py \
        webnovel-writer/scripts/data_modules/webnovel.py \
        webnovel-writer/scripts/chapter_outline_loader.py \
        webnovel-writer/scripts/chapter_paths.py \
        webnovel-writer/scripts/data_modules/tests
git commit -m "fix: align volume chapter cli contract"
```

### Task 4: Stop Chapter Refresh from Polluting MASTER_SETTING

**Files:**
- Modify: `webnovel-writer/scripts/story_system.py`
- Modify: `webnovel-writer/scripts/data_modules/story_contracts.py`
- Test: `webnovel-writer/scripts/data_modules/tests/test_story_system_cli.py`

- [ ] **Step 1: Write failing test**

Given existing `MASTER_SETTING.json` with book-level query, running per-chapter story-system should not overwrite it unless `--refresh-master` is passed.

- [ ] **Step 2: Add explicit flags**

Behavior:
- `story-system <query> --persist --chapter N`: write chapter brief and anti-pattern merge only.
- `story-system <query> --persist --refresh-master`: may update master.
- Init flow should pass `--refresh-master`.
- Write flow should not.

- [ ] **Step 3: Update skills**

Change write/review/plan docs so chapter refresh does not imply book master overwrite.

- [ ] **Step 4: Commit**

```bash
git add webnovel-writer/scripts/story_system.py \
        webnovel-writer/scripts/data_modules/story_contracts.py \
        webnovel-writer/skills/webnovel-write/SKILL.md \
        webnovel-writer/skills/webnovel-review/SKILL.md \
        webnovel-writer/skills/webnovel-plan/SKILL.md \
        webnovel-writer/scripts/data_modules/tests/test_story_system_cli.py
git commit -m "fix: prevent chapter refresh from overwriting master setting"
```

---

## Chunk 3: Hard Gates

### Task 5: Strict Prewrite Gate

**Files:**
- Create: `webnovel-writer/scripts/data_modules/story_prewrite_gate.py`
- Modify: `webnovel-writer/scripts/data_modules/prewrite_validator.py`
- Modify: `webnovel-writer/scripts/data_modules/context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/webnovel.py`
- Test: `webnovel-writer/scripts/data_modules/tests/test_story_prewrite_gate.py`

- [ ] **Step 1: Write failing tests for current bad states**

Block when:
- Chapter contract missing.
- Review contract missing.
- `chapter_brief.chapter_directive.goal` missing and `chapter_focus` came from CSV/dynamic context.
- Outline section not found or hash mismatch.
- Latest accepted commit is older than `chapter - 1`.
- State location/meta is behind latest accepted commit by more than one chapter.
- Existing accepted commit for target chapter exists and user did not pass `--rewrite`.

- [ ] **Step 2: Implement gate**

Public API:

```python
@dataclass(frozen=True)
class PrewriteGateResult:
    chapter: int
    ready: bool
    blocking_reasons: list[str]
    warnings: list[str]
    provenance: dict[str, Any]

def run_prewrite_gate(project_root: Path, chapter: int, *, rewrite: bool = False) -> PrewriteGateResult:
    ...
```

- [ ] **Step 3: Add CLI**

Command:

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py \
  --project-root "$PROJECT_ROOT" prewrite-check --chapter 34
```

Exit behavior:
- `0` when ready.
- `2` when blocked.

- [ ] **Step 4: Wire context payload**

`context_manager` should include:

```json
"prewrite_gate": {
  "ready": false,
  "blocking_reasons": [...]
}
```

For write mode, the skill must stop on `ready=false`.

- [ ] **Step 5: Commit**

```bash
git add webnovel-writer/scripts/data_modules/story_prewrite_gate.py \
        webnovel-writer/scripts/data_modules/prewrite_validator.py \
        webnovel-writer/scripts/data_modules/context_manager.py \
        webnovel-writer/scripts/data_modules/webnovel.py \
        webnovel-writer/scripts/data_modules/tests/test_story_prewrite_gate.py
git commit -m "feat: add strict prewrite gate"
```

### Task 6: Commit-Time Validation

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/chapter_commit_service.py`
- Modify: `webnovel-writer/scripts/chapter_commit.py`
- Test: `webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py`

- [ ] **Step 1: Write failing test**

`ChapterCommitService.build_commit()` must reject accepted status when required contracts are missing, unless `commit_mode="repair_backfill"`.

- [ ] **Step 2: Add commit provenance**

Commit payload must include:

```json
"provenance": {
  "write_fact_role": "chapter_commit",
  "commit_mode": "native_write|repair_backfill",
  "body_sha256": "...",
  "outline_sha256": "...",
  "contract_sha256": "...",
  "legacy_state_role": "projection_only"
}
```

- [ ] **Step 3: Add CLI mode**

Default:

```bash
chapter-commit --chapter 33 ...
```

Strict native write. Fails if contracts are missing.

Repair:

```bash
chapter-commit --chapter 33 --commit-mode repair_backfill ...
```

Allowed only from `story-repair rebuild`.

- [ ] **Step 4: Commit**

```bash
git add webnovel-writer/scripts/data_modules/chapter_commit_service.py \
        webnovel-writer/scripts/chapter_commit.py \
        webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py
git commit -m "fix: validate chapter commit provenance"
```

---

## Chunk 4: Rebuild This Book

### Task 7: Dry-Run Rebuild Plan for Chapters 1-33

**Files:**
- Create: `webnovel-writer/scripts/data_modules/story_repair/rebuild_service.py`
- Modify: `webnovel-writer/scripts/data_modules/webnovel.py`
- Test: `webnovel-writer/scripts/data_modules/tests/test_story_repair_rebuild_service.py`

- [ ] **Step 1: Write failing dry-run test**

Dry run should produce a plan with no file changes:

```json
{
  "chapters_to_rebuild_contracts": [1, 2, ..., 33],
  "chapters_to_rebuild_commits": [1, 2, ..., 33],
  "stale_files_to_archive": [...],
  "projection_targets": ["state", "index", "summary", "memory"],
  "requires_human_review": true
}
```

- [ ] **Step 2: Implement dry-run**

Command:

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py \
  --project-root "从迷因资本到智能狂想" \
  story-repair rebuild --chapters 1-33 --dry-run \
  --report-file "修复报告/story-repair-dry-run.md"
```

Acceptance:
- no changes to `.story-system` or `.webnovel`
- report explains which commits are native vs backfilled
- report identifies `MASTER_SETTING` pollution risk

- [ ] **Step 3: Commit**

```bash
git add webnovel-writer/scripts/data_modules/story_repair/rebuild_service.py \
        webnovel-writer/scripts/data_modules/tests/test_story_repair_rebuild_service.py \
        webnovel-writer/scripts/data_modules/webnovel.py
git commit -m "feat: add story repair rebuild dry run"
```

### Task 8: Build Canonical Chapter Ledger

**Files:**
- Output: `从迷因资本到智能狂想/修复报告/chapter-ledger.json`
- Output: `从迷因资本到智能狂想/修复报告/chapter-ledger.md`

- [ ] **Step 1: Generate draft ledger**

Use current outline, chapter text, and existing summaries. Each chapter needs:

```json
{
  "chapter": 33,
  "title": "盘点第一桶金",
  "time_anchor": "2024年5月4日",
  "entry_state": "...",
  "exit_state": "...",
  "location": "...",
  "characters": [],
  "must_keep_events": [],
  "open_loops_created": [],
  "open_loops_closed": [],
  "next_chapter_entry": "...",
  "continuity_notes": [],
  "source_body": "正文/第1卷/第0033章-盘点.md",
  "source_outline_hash": "..."
}
```

- [ ] **Step 2: Human/editorial review**

Review specifically:
- Ch18 -> Ch19 duplicate/opening contamination.
- Ch31 -> Ch32 missing physical transition.
- Ch32 -> Ch33 relationship state and location.
- Asset numbers after BOME/SLERF/出金.
- Names: 烧鹅, 阿坤, 杜雨薇, 蒋思瑜, 林建阳.

- [ ] **Step 3: Freeze ledger**

After review, mark:

```json
"ledger_status": "accepted_for_repair"
```

No rebuild apply before this exists.

### Task 9: Apply Rebuild

**Files:**
- Modify: `.story-system/**`
- Modify: `.webnovel/state.json`
- Modify: `.webnovel/summaries/**`
- Modify: `.webnovel/index.db`
- Modify: `.webnovel/memory_scratchpad.json`

- [ ] **Step 1: Run apply from accepted ledger**

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py \
  --project-root "从迷因资本到智能狂想" \
  story-repair rebuild --chapters 1-33 --apply \
  --ledger "修复报告/chapter-ledger.json"
```

- [ ] **Step 2: Validate runtime**

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py \
  --project-root "从迷因资本到智能狂想" preflight --format json
```

Expected for chapter 33:
- `mainline_ready=true`
- no missing chapter/review contracts
- latest commit status accepted
- projection status done/skipped

- [ ] **Step 3: Validate next write**

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py \
  --project-root "从迷因资本到智能狂想" prewrite-check --chapter 34
```

Expected:
- `ready=true`
- previous accepted commit is chapter 33
- chapter 34 outline found
- chapter 34 chapter/review contracts exist
- no stale location from chapter 19

- [ ] **Step 4: Commit book repair**

```bash
git -C "从迷因资本到智能狂想" add .story-system .webnovel 修复报告
git -C "从迷因资本到智能狂想" commit -m "repair: rebuild story system after outline restructure"
git add "从迷因资本到智能狂想"
git commit -m "chore: update submodule pointer after story repair"
```

---

## Chunk 5: Archive Stale Artifacts and Update Prompts

### Task 10: Archive Legacy Snapshots

**Files:**
- Create: `webnovel-writer/scripts/data_modules/story_repair/archive_service.py`
- Modify: `webnovel-writer/scripts/data_modules/webnovel.py`
- Test: archive service tests

- [ ] **Step 1: Dry run**

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py \
  --project-root "从迷因资本到智能狂想" \
  story-repair archive-stale --dry-run
```

Expected includes:
- `.webnovel/context_snapshots/ch0011.json`
- `.webnovel/context_snapshots/ch0012.json`
- `.webnovel/context_snapshots/ch0019.json`
- stale `.webnovel/tmp/*` not matching accepted ledger

- [ ] **Step 2: Apply archive**

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py \
  --project-root "从迷因资本到智能狂想" \
  story-repair archive-stale --apply
```

Expected:
- files moved, not deleted
- manifest written with old path, new path, sha256, reason

- [ ] **Step 3: Commit**

```bash
git add webnovel-writer/scripts/data_modules/story_repair/archive_service.py \
        webnovel-writer/scripts/data_modules/webnovel.py
git -C "从迷因资本到智能狂想" add .webnovel/archive .webnovel/context_snapshots .webnovel/tmp
git commit -m "feat: archive stale story repair artifacts"
```

### Task 11: Update Write/Context Instructions

**Files:**
- Modify: `webnovel-writer/skills/webnovel-write/SKILL.md`
- Modify: `webnovel-writer/agents/context-agent.md`
- Modify: `webnovel-writer/skills/webnovel-review/SKILL.md`

- [ ] **Step 1: Add mandatory command**

Before context-agent:

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" \
  --project-root "${PROJECT_ROOT}" prewrite-check \
  --volume {volume_num} --chapter {chapter_in_volume}
```

- [ ] **Step 2: Change fallback policy**

In write mode:
- Missing contracts: stop.
- Missing outline: stop.
- Stale projection: stop.
- Legacy fallback: query-only, not write.

- [ ] **Step 3: Add “no backfilled proof” rule**

The context agent must treat `commit_mode=repair_backfill` as historical reconstruction, not proof of original writing context.

- [ ] **Step 4: Commit**

```bash
git add webnovel-writer/skills/webnovel-write/SKILL.md \
        webnovel-writer/agents/context-agent.md \
        webnovel-writer/skills/webnovel-review/SKILL.md
git commit -m "docs: require prewrite gate before writing"
```

---

## Chunk 6: Final Verification

### Task 12: Full Test and Book Health Verification

- [ ] **Step 1: Run code tests**

```bash
pytest webnovel-writer/scripts/data_modules/tests/test_story_repair_outline_catalog.py \
       webnovel-writer/scripts/data_modules/tests/test_story_repair_provenance_auditor.py \
       webnovel-writer/scripts/data_modules/tests/test_story_repair_rebuild_service.py \
       webnovel-writer/scripts/data_modules/tests/test_story_prewrite_gate.py \
       webnovel-writer/scripts/data_modules/tests/test_story_runtime_sources.py \
       webnovel-writer/scripts/data_modules/tests/test_context_manager.py \
       webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py -v
```

- [ ] **Step 2: Run book audit**

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py \
  --project-root "从迷因资本到智能狂想" \
  story-repair audit --chapters 1-33 --format text
```

Expected:
- no missing body for 1-33
- no missing chapter/review contract for 1-33
- no accepted commit without contract
- state location/meta aligns with chapter 33

- [ ] **Step 3: Run next chapter gate**

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py \
  --project-root "从迷因资本到智能狂想" prewrite-check --chapter 34
```

Expected:
- ready true

- [ ] **Step 4: Only then resume writing**

Run `webnovel-write` for chapter 34 only after the above succeeds.

---

## Stop Conditions

Stop and ask for review if any of these happen:

- The ledger cannot reconcile a chapter’s outline and body without editorial choice.
- Rebuild would overwrite user-edited chapter text.
- `MASTER_SETTING` still changes during per-chapter refresh after Task 4.
- `prewrite-check --chapter 34` passes while contracts are missing.
- The audit reports a backfilled commit but cannot identify its source body hash.

## Success Criteria

- `story-repair audit --chapters 1-33` returns no blocking anomalies.
- `preflight` reports `mainline_ready=true` for current chapter.
- `prewrite-check --chapter 34` returns exit code 0.
- `.webnovel/state.json` is only a projection and matches latest accepted commit.
- New write flow cannot proceed if Story System contracts are missing.
- Backfilled artifacts are clearly labeled and never confused with native write provenance.
