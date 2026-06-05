# Codex Agent Protocols

This file defines Codex inline replacements for Claude Code subagents. Use these protocols when the skill asks for an `Agent(...)` call but the active runtime has no Claude Code Agent tool. Keep the same inputs, file artifacts, and CLI handoff so the Python pipeline does not branch by runtime.

General rules:

- Resolve `PROJECT_ROOT` and `SCRIPTS_DIR` before starting.
- Do not invent missing project facts. If required inputs are absent, stop and report the blocking reason.
- Write only the JSON artifacts explicitly named by the protocol.
- Keep `.webnovel/state.json` and `index.db` as read-model/projection data unless a CLI command updates them.

## context-agent inline protocol

Purpose: produce the writing brief that supports drafting.

Inputs:

- `project_root`
- `scripts_dir`
- `volume`
- `chapter` (volume-local chapter number)
- optional user constraints or project style rules

Required reads:

- `python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" prewrite-check --volume {volume} --chapter {chapter}`
- `python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" memory-contract load-context --volume {volume} --chapter {chapter}`
- `大纲/第{volume}卷-详细大纲.md`, locating the exact `### 第{chapter}章` section
- `.story-system/MASTER_SETTING.json`
- `.story-system/volumes/volume_{volume:03d}.json`
- `.story-system/chapters/chapter_{global_chapter:03d}.json`
- `.story-system/reviews/chapter_{global_chapter:03d}.review.json`
- latest accepted `.story-system/commits/chapter_*.commit.json` when continuity depends on prior facts

Output artifact:

- No JSON file is required. Output one writing brief in the current Codex response or scratch step, ordered as:
  1. hard chapter constraints
  2. CBN / CPNs / CEN and must-cover nodes
  3. forbidden zones
  4. style, reasoning, character, and anti-pattern guidance
  5. ending pressure and unresolved question

Failure handling:

- If `prewrite-check.ready` is false, stop and report its `blocking_reasons`.
- If the chapter goal is still a placeholder, stop and ask for the real outline goal or repair the outline first.
- If story contracts are missing, run the story-system refresh step from the calling skill before retrying.

## reviewer inline protocol

Purpose: inspect a chapter and write reviewer schema output.

Inputs:

- `project_root`
- `scripts_dir`
- `volume`
- `chapter`
- `chapter_file`
- `webnovel-writer/skills/webnovel-write/references/polish-guide.md` when checking style constraints
- optional project style or anti-AI rules

Required reads:

- `chapter_file`
- `.story-system/reviews/chapter_{global_chapter:03d}.review.json`
- latest accepted `.story-system/commits/chapter_*.commit.json`
- relevant state/index lookups through `webnovel.py` when checking entities, timeline, relationships, or recent changes
- `webnovel-writer/skills/webnovel-write/references/polish-guide.md` when checking `ai_flavor`
- project-specific style rules if the user provides them

Required JSON artifact:

- Write `${PROJECT_ROOT}/.webnovel/tmp/review_results.json`.
- Top-level schema:

```json
{
  "issues": [
    {
      "severity": "critical | high | medium | low",
      "category": "continuity | setting | character | timeline | ai_flavor | logic | pacing | other",
      "location": "line/paragraph or quoted span",
      "description": "verifiable problem",
      "evidence": "chapter text vs project fact",
      "fix_hint": "minimal repair direction",
      "blocking": true
    }
  ],
  "summary": "N issues: X blocking, Y high priority"
}
```

Failure handling:

- If the chapter file is missing or empty, write one critical blocking issue.
- If a data source cannot be read, continue only for dimensions that can still be verified and mention the skipped source in `summary`.
- Do not output `overall_score`; the review pipeline derives metrics.

## data-agent inline protocol

Purpose: extract chapter facts and write commit artifacts.

Inputs:

- `project_root`
- `scripts_dir`
- `volume`
- `chapter`
- `chapter_file`
- existing `${PROJECT_ROOT}/.webnovel/tmp/review_results.json`

Required reads:

- `chapter_file`
- `.story-system/chapters/chapter_{global_chapter:03d}.json`
- `.story-system/reviews/chapter_{global_chapter:03d}.review.json`
- `${PROJECT_ROOT}/.webnovel/tmp/review_results.json`
- entity and alias lookups through `webnovel.py index get-core-entities`, `recent-appearances`, `get-aliases`, and `get-by-alias` as needed

Required JSON artifacts:

- Write `${PROJECT_ROOT}/.webnovel/tmp/fulfillment_result.json` with top-level arrays:
  - `planned_nodes`
  - `covered_nodes`
  - `missed_nodes`
  - `extra_nodes`
- Write `${PROJECT_ROOT}/.webnovel/tmp/disambiguation_result.json` with top-level `pending` array.
- Write `${PROJECT_ROOT}/.webnovel/tmp/extraction_result.json` with:
  - `accepted_events`
  - `state_deltas`
  - `entity_deltas`
  - `entities_appeared`
  - `scenes`
  - `summary_text`
  - optional `dominant_strand`

Failure handling:

- If entity confidence is below 0.5, put the case into `disambiguation_result.json.pending` instead of inventing an id.
- If a must-cover node is absent, record it in `missed_nodes`; do not silently mark it covered.
- Do not write state, index, summaries, memory, or vector stores directly. The caller runs `chapter-commit`.

## deconstruction-agent inline protocol

Purpose: deconstruct reference material for `webnovel-init` without contaminating the new book canon.

Inputs:

- `reference_title`
- `reference_source`
- `reference_text_path`
- `reference_text_excerpt`
- `analysis_mode` (`quick`, `deep`, or `auto`)
- `init_goal`
- `target_genre`

Required reads:

- If `reference_text_path` is present, read it only as source material.
- If only an excerpt is provided, use the excerpt and mark coverage accordingly.
- If only title/platform clues are provided, do not invent plot facts from memory.

Required JSON artifact:

- Return one `init_reference_research` JSON object to the init flow. Do not write files.
- Include transferable patterns such as `reader_promise`, `opening_hook_patterns`, `cool_point_loops`, `protagonist_patterns`, `antagonist_pressure_patterns`, `pacing_notes`, `borrowable_structures`, `do_not_copy`, `differentiation_requirements`, `init_candidates`, `quality`, and `resume_state`.

Failure handling:

- With no readable text or excerpt, return `quality.passed=false` and explain the missing source.
- If confidence is below 0.85, mark `needs_review` and avoid stable init candidates.
- Never copy original character names, places, organizations, power names, plot facts, or signature scenes into the new canon.
