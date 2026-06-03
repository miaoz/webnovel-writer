# Codex Plugin Adaptation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `webnovel-writer` installable and usable as a Codex plugin while preserving Claude Code compatibility.

**Architecture:** Keep the Python CLI, data chain, dashboard, templates, references, and most skill content as the shared core. Add a Codex manifest and a portable plugin-root/workspace convention, then replace Claude-only skill orchestration (`Agent`, `AskUserQuestion`, Claude env vars) with Codex-compatible inline protocols or helper references. Treat this as a dual-runtime plugin, not a fork.

**Tech Stack:** Codex plugin manifest (`.codex-plugin/plugin.json`), existing Markdown skills, Python 3.10+ CLI, pytest, existing FastAPI/Vite dashboard, Codex plugin validator.

---

## Scope And Non-Goals

- Keep `.claude-plugin/plugin.json` and Claude Code installation paths working.
- Add `.codex-plugin/plugin.json`; do not move the existing plugin root.
- Do not rewrite core story runtime or dashboard backend unless a test exposes a real compatibility bug.
- Do not depend on Codex subagents for normal use. If subagents are available, they can be an optimization, not a requirement.
- Do not manually edit the Chinese story submodule as part of this work.

## File Map

- Create: `webnovel-writer/.codex-plugin/plugin.json` — Codex plugin manifest.
- Modify: `README.md` — add Codex install/use section and update badge language.
- Modify: `docs/guides/commands.md`, `docs/operations/operations.md` — document dual env vars and Codex use.
- Modify: `webnovel-writer/skills/*/SKILL.md` — replace Claude-only env/tool assumptions with dual-runtime instructions.
- Create: `webnovel-writer/references/codex/agent-protocols.md` — index for Codex inline replacements.
- Create if needed: `webnovel-writer/references/codex/protocols/*.md` — split long `context-agent`, `reviewer`, `data-agent`, and `deconstruction-agent` protocols if the index would exceed about 250 lines.
- Modify: `webnovel-writer/agents/*.md` — keep for Claude, but mark as Claude Code subagent specs and point Codex users to `references/codex/agent-protocols.md`.
- Modify: `webnovel-writer/scripts/project_locator.py` and `webnovel-writer/scripts/data_modules/config.py` — support Codex home/workspace env vars without removing Claude vars.
- Add or modify tests under `webnovel-writer/scripts/data_modules/tests/` — manifest validation, prompt integrity, env compatibility.

## Chunk 1: Baseline And Manifest

### Task 1: Record current compatibility baseline

**Files:**
- Read only: repository state and existing tests.

- [ ] Run `git status --short` in the outer repo.
  Expected: only known unrelated submodule dirt or clean state. If ` m 从迷因资本到智能狂想` is present, record it in the implementation notes as user-owned story work.
- [ ] Run:
  ```bash
  git -C 从迷因资本到智能狂想 status --short
  git -C 从迷因资本到智能狂想 status -sb
  ```
  Expected: confirms whether the story submodule has user edits. Do not stage, commit, clean, or update the submodule from this adaptation plan.
- [ ] Run `python -X utf8 webnovel-writer/scripts/webnovel.py preflight --format json`.
  Expected: CLI starts and prints JSON or a clear no-project diagnostic.
- [ ] Run `pytest webnovel-writer/scripts/data_modules/tests/test_project_locator.py -q`.
  Expected: pass before changes.

### Task 2: Add Codex plugin manifest

**Files:**
- Create: `webnovel-writer/.codex-plugin/plugin.json`
- Test: `webnovel-writer/scripts/data_modules/tests/test_codex_manifest.py`

- [ ] Write a failing test that asserts:
  - `.codex-plugin/plugin.json` exists.
  - `name == "webnovel-writer"`.
  - `version` is strict semver.
  - `author.name` exists.
  - `skills == "./skills/"`.
  - required `interface` fields exist: `displayName`, `shortDescription`, `longDescription`, `developerName`, `category`, `capabilities`, `defaultPrompt`.
  - optional URL fields, if present, are absolute `https://` URLs.
  - asset fields such as `composerIcon`, `logo`, and `screenshots` are omitted unless real files exist.
  - no unsupported fields such as `hooks`.
- [ ] Run the test and confirm it fails because the manifest is missing.
- [ ] Add manifest with metadata adapted from `.claude-plugin/plugin.json`:
  - `name`: `webnovel-writer`
  - `version`: keep current semantic version, initially `6.0.0`
  - `description`: mention long-form webnovel writing system
  - `author.name`: reuse `.claude-plugin/plugin.json` author name
  - `author.url`: repository owner URL if available
  - `skills`: `./skills/`
  - `interface.displayName`: `Webnovel Writer`
  - `interface.shortDescription`: one-line Codex plugin subtitle
  - `interface.longDescription`: 1 paragraph covering skills, data chain, and dashboard
  - `interface.developerName`: author or project maintainer name
  - `interface.category`: `Writing`
  - `interface.capabilities`: `["Interactive", "Write"]`
  - `interface.defaultPrompt`: at most 3 short prompts
  - Do not include `hooks`, `apps`, `mcpServers`, `composerIcon`, `logo`, or `screenshots` unless the referenced companion files/assets are created in the same task.
- [ ] Run:
  ```bash
  python3 /Users/miaoz/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py webnovel-writer
  pytest webnovel-writer/scripts/data_modules/tests/test_codex_manifest.py -q
  ```
  Expected: validator pass and test pass.
- [ ] Commit:
  ```bash
  git add webnovel-writer/.codex-plugin/plugin.json webnovel-writer/scripts/data_modules/tests/test_codex_manifest.py
  git commit -m "feat(codex): add plugin manifest"
  ```

## Chunk 2: Runtime Path Compatibility

### Task 3: Add Codex-aware environment resolution

**Files:**
- Modify: `webnovel-writer/scripts/project_locator.py`
- Modify: `webnovel-writer/scripts/data_modules/config.py`
- Test: `webnovel-writer/scripts/data_modules/tests/test_project_locator.py`
- Test: `webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py`

- [ ] Add tests for env precedence:
  - `WEBNOVEL_WORKSPACE_ROOT` or `CODEX_WORKSPACE_ROOT` can substitute for `CLAUDE_PROJECT_DIR`.
  - `WEBNOVEL_HOME` or `CODEX_HOME` can substitute for `CLAUDE_HOME`.
  - existing Claude env vars still pass.
- [ ] Run the targeted tests and confirm the new cases fail.
- [ ] Implement minimal env lookup helpers:
  - workspace hint order: explicit `--project-root` > `WEBNOVEL_WORKSPACE_ROOT` > `CODEX_WORKSPACE_ROOT` > `CLAUDE_PROJECT_DIR` > `PWD`
  - home/config order: `WEBNOVEL_HOME` > `WEBNOVEL_CLAUDE_HOME` > `CODEX_HOME` > `CLAUDE_HOME` > platform default
- [ ] Keep compatibility comments clear and short.
- [ ] Run:
  ```bash
  pytest webnovel-writer/scripts/data_modules/tests/test_project_locator.py \
         webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py -q
  ```
  Expected: pass.
- [ ] Commit:
  ```bash
  git add webnovel-writer/scripts/project_locator.py webnovel-writer/scripts/data_modules/config.py webnovel-writer/scripts/data_modules/tests/
  git commit -m "fix(runtime): support codex workspace and home env"
  ```

### Task 4: Standardize skill environment snippets

**Files:**
- Modify: all `webnovel-writer/skills/*/SKILL.md`
- Test: `webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py`

- [ ] Add prompt-integrity tests that fail on hard required `CLAUDE_PLUGIN_ROOT:?` snippets without a Codex fallback.
- [ ] First update path/env-only skills (`webnovel-dashboard`, `webnovel-learn`, `webnovel-query`) to use a dual-runtime convention:
  ```bash
  export WORKSPACE_ROOT="${WEBNOVEL_WORKSPACE_ROOT:-${CODEX_WORKSPACE_ROOT:-${CLAUDE_PROJECT_DIR:-$PWD}}}"
  export WEBNOVEL_PLUGIN_ROOT="${WEBNOVEL_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
  ```
- [ ] Then update orchestration-heavy skills (`webnovel-init`, `webnovel-plan`, `webnovel-write`, `webnovel-review`, `webnovel-amend`) with the same env convention, leaving `Agent` semantics untouched until Chunk 3.
- [ ] For Codex instructions, add: if `WEBNOVEL_PLUGIN_ROOT` is empty, resolve plugin-relative paths from the loaded `SKILL.md` location and use `../../scripts`.
- [ ] Replace "固定路径：`${CLAUDE_PLUGIN_ROOT}/scripts`" with "script path must resolve to plugin `scripts/`".
- [ ] Keep Claude examples working by preserving `CLAUDE_PLUGIN_ROOT` fallback.
- [ ] Run prompt integrity tests.
- [ ] Commit:
  ```bash
  git add webnovel-writer/skills webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py
  git commit -m "docs(skills): add dual-runtime path guidance"
  ```

## Chunk 3: Replace Claude-Only Orchestration

### Task 5: Create Codex inline agent protocols

**Files:**
- Create: `webnovel-writer/references/codex/agent-protocols.md`
- Create if needed: `webnovel-writer/references/codex/protocols/context-agent.md`
- Create if needed: `webnovel-writer/references/codex/protocols/reviewer.md`
- Create if needed: `webnovel-writer/references/codex/protocols/data-agent.md`
- Create if needed: `webnovel-writer/references/codex/protocols/deconstruction-agent.md`
- Modify: `webnovel-writer/agents/*.md`
- Test: `webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py`

- [ ] Create `agent-protocols.md` with four sections or links:
  - `context-agent inline protocol`
  - `reviewer inline protocol`
  - `data-agent inline protocol`
  - `deconstruction-agent inline protocol`
- [ ] If `agent-protocols.md` would exceed about 250 lines, split each protocol into `references/codex/protocols/*.md` and keep `agent-protocols.md` as the routing index.
- [ ] Each protocol must state inputs, required reads, required JSON artifacts, and failure handling.
- [ ] In `agents/*.md`, add a short header: "Claude Code subagent spec; Codex uses `references/codex/agent-protocols.md`."
- [ ] Add tests that confirm the Codex protocol file mentions all required artifact names:
  - `review_results.json`
  - `fulfillment_result.json`
  - `disambiguation_result.json`
  - `extraction_result.json`
- [ ] Run tests and commit:
  ```bash
  pytest webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py -q
  ```
  Expected: pass and confirm all protocol artifact names are present.
- [ ] Commit:
  ```bash
  git add webnovel-writer/references/codex webnovel-writer/agents webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py
  git commit -m "docs(codex): add inline agent protocols"
  ```

### Task 6: Adapt `webnovel-write`, `webnovel-review`, and `webnovel-amend`

**Files:**
- Modify: `webnovel-writer/skills/webnovel-write/SKILL.md`
- Modify: `webnovel-writer/skills/webnovel-review/SKILL.md`
- Modify: `webnovel-writer/skills/webnovel-amend/SKILL.md`
- Test: `webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py`

- [ ] Add tests that fail if a skill says "must use `Agent`" without also giving a Codex inline alternative.
- [ ] In each skill, keep the Claude `Agent(subagent_type=...)` block under "Claude Code path".
- [ ] Add "Codex path" immediately after each `Agent` block:
  - read `references/codex/agent-protocols.md`
  - execute the named inline protocol in the current model session
  - write the same JSON files before running the existing CLI pipeline
- [ ] Replace `AskUserQuestion` hard requirements with "ask the user directly when unavailable".
- [ ] Keep artifact schemas unchanged so Python CLI does not need branching.
- [ ] Run prompt integrity tests and a CLI smoke command:
  ```bash
  pytest webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py -q
  python -X utf8 webnovel-writer/scripts/webnovel.py preflight --format json
  ```
- [ ] Commit:
  ```bash
  git add webnovel-writer/skills/webnovel-write webnovel-writer/skills/webnovel-review webnovel-writer/skills/webnovel-amend webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py
  git commit -m "docs(skills): add codex inline orchestration path"
  ```

### Task 7: Adapt `webnovel-init`

**Files:**
- Modify: `webnovel-writer/skills/webnovel-init/SKILL.md`
- Test: `webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py`

- [ ] Add tests that flag Claude-only `WebSearch`, `WebFetch`, and `AskUserQuestion` requirements without Codex fallback wording.
- [ ] Replace tool list wording with capability wording:
  - "use web search if available and required by time-sensitive market claims"
  - "ask the user directly for unresolved decisions"
  - "Codex: use the inline deconstruction protocol when subagents are unavailable"
- [ ] Keep Claude Code `Agent(webnovel-writer:deconstruction-agent)` block as the Claude path.
- [ ] Add Codex path that uses `references/codex/agent-protocols.md`.
- [ ] Run tests and commit:
  ```bash
  pytest webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py -q
  ```
  Expected: pass; `webnovel-init` contains both Claude deconstruction-agent path and Codex inline deconstruction protocol path.
- [ ] Commit:
  ```bash
  git add webnovel-writer/skills/webnovel-init webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py
  git commit -m "docs(init): add codex-compatible interaction path"
  ```

## Chunk 4: Documentation And Install Flow

### Task 8: Update user-facing docs

**Files:**
- Modify: `README.md`
- Modify: `docs/guides/commands.md`
- Modify: `docs/operations/operations.md`
- Optional create: `docs/guides/codex-install.md`

- [ ] Add README "Codex installation" section:
  - local plugin source path
  - validation command
  - install/reinstall command once marketplace entry exists
  - note that current Claude Code install remains supported
- [ ] Add command examples that use `WEBNOVEL_PLUGIN_ROOT` / resolved Codex plugin root instead of only `<CLAUDE_PLUGIN_ROOT>`.
- [ ] Document that Codex write/review/amend run single-agent inline protocols unless a subagent tool is explicitly available.
- [ ] Run a docs grep:
  ```bash
  rg -n "Claude Code only|只能|CLAUDE_PLUGIN_ROOT" README.md docs webnovel-writer/skills
  ```
  Expected: any remaining Claude-only wording is either in Claude-specific sections or has Codex alternative.
- [ ] Commit:
  ```bash
  git add README.md docs webnovel-writer/skills
  git commit -m "docs: document codex plugin usage"
  ```

## Chunk 5: Validation, Packaging, And Local Install

### Task 9: Run full validation suite

**Files:**
- No direct file changes unless failures expose bugs.

- [ ] Run:
  ```bash
  python3 /Users/miaoz/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py webnovel-writer
  pytest -q
  python -X utf8 webnovel-writer/scripts/webnovel.py preflight --format json
  ```
- [ ] If dashboard-related code changed, also run:
  ```bash
  npm --prefix webnovel-writer/dashboard/frontend run build
  ```
- [ ] Fix only failures caused by this adaptation.

### Task 10: Local marketplace install for Codex testing

**Files:**
- Create or modify only when local install is requested: `.agents/plugins/marketplace.json`
- Do not modify the story submodule.

- [ ] Choose the local install mode before editing:
  - **Repo-local marketplace mode (recommended for this repository):** add a repo-local marketplace that points at the checked-out `webnovel-writer/` plugin directory.
  - **Personal marketplace mode:** sync or place the plugin source at `~/plugins/webnovel-writer` and use `~/.agents/plugins/marketplace.json`.
- [ ] For reinstalling an already-installed repo-local plugin, update the Codex cachebuster before `codex plugin add`:
  ```bash
  python3 /Users/miaoz/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py webnovel-writer
  ```
  Expected: manifest version keeps the base semver and gains or replaces a `+codex.<timestamp>` suffix.
- [ ] For repo-local marketplace mode, create `.agents/plugins/marketplace.json` with:
  ```json
  {
    "name": "webnovel-writer-local",
    "interface": {
      "displayName": "Webnovel Writer Local"
    },
    "plugins": [
      {
        "name": "webnovel-writer",
        "source": {
          "source": "local",
          "path": "./webnovel-writer"
        },
        "policy": {
          "installation": "AVAILABLE",
          "authentication": "ON_INSTALL"
        },
        "category": "Writing"
      }
    ]
  }
  ```
  Expected: marketplace source path resolves from the repository root when installed with `codex plugin marketplace add .`.
- [ ] Note in the implementation report that repo-local mode intentionally uses `source.path: "./webnovel-writer"` to point at this repository's existing plugin directory. This is intentionally different from plugin-creator's default personal marketplace layout `./plugins/<plugin-name>`.
- [ ] If Codex rejects `./webnovel-writer` for repo-local marketplace mode, stop and switch to personal marketplace mode instead of hand-editing around the schema.
- [ ] For personal marketplace mode, use plugin-creator helpers in this order. If `~/plugins/webnovel-writer` already exists, do not use `--force`; either confirm its marketplace entry already exists or stop and use repo-local marketplace mode.
  ```bash
  mkdir -p ~/plugins
  test ! -d ~/plugins/webnovel-writer
  python3 /Users/miaoz/.codex/skills/.system/plugin-creator/scripts/create_basic_plugin.py webnovel-writer --with-marketplace
  rsync -a --delete --exclude '.git' --exclude '__pycache__' webnovel-writer/ ~/plugins/webnovel-writer/
  python3 /Users/miaoz/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py ~/plugins/webnovel-writer
  python3 /Users/miaoz/.codex/skills/.system/plugin-creator/scripts/read_marketplace_name.py
  ```
  Expected: scaffold creates or updates the personal marketplace before the real plugin files are synced over; `read_marketplace_name.py` prints the marketplace name, normally `personal`.
- [ ] Validate the plugin source that will be installed:
  ```bash
  python3 /Users/miaoz/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py webnovel-writer
  ```
  For personal marketplace mode, validate `~/plugins/webnovel-writer` instead.
- [ ] Register the repo-local marketplace if using repo-local mode:
  ```bash
  codex plugin marketplace add .
  codex plugin marketplace list
  ```
  Expected: list includes `webnovel-writer-local` with this repository as root.
- [ ] Install or reinstall from the selected marketplace:
  ```bash
  codex plugin add webnovel-writer@webnovel-writer-local
  ```
  For personal marketplace mode, replace `webnovel-writer-local` with the value printed by `read_marketplace_name.py`.
  Expected: command exits 0 and the plugin appears in `codex plugin list`.
- [ ] Start a new Codex thread and verify the `webnovel-*` skills appear.
  Expected: the new thread lists or can trigger `webnovel-init`, `webnovel-plan`, `webnovel-write`, `webnovel-review`, `webnovel-amend`, `webnovel-query`, `webnovel-dashboard`, and `webnovel-learn`.

### Task 11: Final audit and commit/push

**Files:**
- All changed files from previous chunks.

- [ ] Run `git status --short` and ensure no unrelated story submodule changes are staged.
- [ ] Run `git diff --submodule` and verify the story submodule pointer has not changed.
- [ ] If `git status --short` still shows ` m 从迷因资本到智能狂想`, leave it unstaged and mention it as user-owned story work in the final report.
- [ ] Run final verification commands from Task 9.
- [ ] Push only after explicit user request:
  ```bash
  git push
  ```

## Acceptance Criteria

- Codex validator accepts `webnovel-writer/.codex-plugin/plugin.json`.
- `.claude-plugin/plugin.json` remains present, valid JSON, and either unchanged or changed only in an explicitly reviewed Claude-compatible way.
- Skills no longer require Claude-only env vars or tools without a Codex fallback.
- `webnovel-write`, `webnovel-review`, and `webnovel-amend` can run their orchestration in Codex without `Agent(subagent_type=...)`.
- Existing Python CLI tests pass.
- README documents both Claude Code and Codex installation/use.
- No story submodule content is modified by this adaptation.
- `git diff --submodule` shows no story submodule pointer update from this adaptation.

## Risk Register

- **Subagent parity risk:** Codex single-agent inline protocols may be less isolated than Claude subagents. Mitigation: keep artifact schemas strict and verify with `review-pipeline` / `chapter-commit`.
- **Plugin root discovery risk:** Codex may not expose a plugin-root env var. Mitigation: skill text must instruct resolving paths relative to loaded `SKILL.md`; docs also allow explicit `WEBNOVEL_PLUGIN_ROOT`.
- **Prompt-integrity test drift:** Existing tests expect Claude `Agent` blocks. Mitigation: update tests to require both Claude path and Codex fallback rather than removing Claude path.
- **Marketplace workflow risk:** Repo-local versus personal marketplace paths differ. Mitigation: use plugin-creator scripts and avoid hand-editing marketplace files.
