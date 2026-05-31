---
name: webnovel-amend
description: 对已提交章节进行人工修订后，重新审查、提取事实并刷新 CHAPTER_COMMIT 与投影。
allowed-tools: Read Grep Write Edit Bash Agent AskUserQuestion
---

# Amendment Skill

## 目标

把已存在的正文修订重新接回主链：审查当前正文、重新提取事实、覆盖该章 `CHAPTER_COMMIT`，并刷新 state/index/summary/memory/vector 投影。

适用：作者在章节已 committed 后修改了正文，尤其是改动可能影响事件、人物状态、地点、伏笔、节点覆盖或章末钩子。

不适用：只想看质量问题，用 `/webnovel-review`；还没提交的新章，继续 `/webnovel-write` Step 3-5。

## 硬规则

- 默认把未知修订当作事实可能变化处理。
- 多章修订必须逐章串行，不并行。
- blocking review 未解决，不跑 data-agent / chapter-commit。
- `repair_backfill` 只用于历史重建；人工修订必须用 `native_write`。
- 不直接改 `.webnovel/state.json`、`index.db` 或 summaries，全部由 `chapter-commit` 投影刷新。

## 流程

### Step 1：定位项目与写前主链

```bash
export WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
export SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT:?}/scripts"
export PROJECT_ROOT="$(python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where)"

python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" preflight
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  prewrite-check --volume {volume_num} --chapter {chapter_in_volume} --rewrite
```

若 `ready=false`，先修复 blocking_reasons。缺 runtime 合同时，从详细大纲解析真实 `CHAPTER_GOAL` 后补齐：

```bash
GENRE="$(python -X utf8 -c "import json; s=json.load(open('${PROJECT_ROOT}/.webnovel/state.json',encoding='utf-8')); print((s.get('project_info') or {}).get('genre') or (s.get('project') or {}).get('genre',''))")"

python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  story-system "${CHAPTER_GOAL}" --genre "${GENRE}" --volume {volume_num} --chapter {chapter_in_volume} --persist --emit-runtime-contracts --format both
```

章节级修订不得传 `--refresh-master`。

### Step 2：审查当前正文

必须调用 `reviewer`，保存结构化 JSON。

```text
Agent(
  subagent_type: "webnovel-writer:reviewer",
  prompt: "volume={volume_num} chapter={chapter_in_volume}; chapter_file=${CHAPTER_FILE}; project_root=${PROJECT_ROOT}; scripts_dir=${SCRIPTS_DIR}。这是已提交章节的人工修订复审，严格输出 reviewer schema JSON，并保存到 ${PROJECT_ROOT}/.webnovel/tmp/review_results.json。"
)
```

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" review-pipeline \
  --volume {volume_num} --chapter {chapter_in_volume} \
  --review-results "${PROJECT_ROOT}/.webnovel/tmp/review_results.json" \
  --metrics-out "${PROJECT_ROOT}/.webnovel/tmp/review_metrics.json" \
  --report-file "审查报告/第{volume_num}卷第{chapter_in_volume}章修订审查报告.md" \
  --save-metrics
```

若存在 `blocking=true`，先询问用户是否立即修复。修复后从 Step 2 重跑。

### Step 3：重新提取事实

必须调用 `data-agent`，基于修订后的正文重新生成三份 JSON。

```text
Agent(
  subagent_type: "webnovel-writer:data-agent",
  prompt: "volume={volume_num} chapter={chapter_in_volume}; chapter_file=${CHAPTER_FILE}; project_root=${PROJECT_ROOT}; scripts_dir=${SCRIPTS_DIR}。这是人工修订后的重新入链：从当前正文提取事实，生成 .webnovel/tmp/fulfillment_result.json、disambiguation_result.json、extraction_result.json；fulfillment_result.json 必须顶层包含 planned_nodes/covered_nodes/missed_nodes/extra_nodes；disambiguation_result.json 必须顶层包含 pending；extraction_result.json 必须顶层包含 accepted_events/state_deltas/entity_deltas/entities_appeared/scenes/summary_text；accepted_events 子项必须包含 event_id/chapter/event_type/subject/payload；不直接写 state/index/summaries/memory。"
)
```

### Step 4：覆盖 CHAPTER_COMMIT 并刷新投影

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" chapter-commit \
  --volume {volume_num} --chapter {chapter_in_volume} \
  --review-result "${PROJECT_ROOT}/.webnovel/tmp/review_results.json" \
  --fulfillment-result "${PROJECT_ROOT}/.webnovel/tmp/fulfillment_result.json" \
  --disambiguation-result "${PROJECT_ROOT}/.webnovel/tmp/disambiguation_result.json" \
  --extraction-result "${PROJECT_ROOT}/.webnovel/tmp/extraction_result.json" \
  --commit-mode native_write
```

该步骤会用当前正文的 `body_sha256` 覆盖该章 commit，并重新应用 projections。若输出为 rejected，停止并报告 missed_nodes / pending / blocking_count。

### Step 5：验证

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  story-repair audit --chapters {global_chapter}-{global_chapter} --format json
```

成功标准：
- commit status 为 accepted。
- `projection_status` 全部为 done 或 skipped。
- audit 中该章 `repair_required=false`。
- 修订的是最新章时，下一章 `prewrite-check` 仍为 `ready=true`。

## 非最新章修订

如果修订章节早于 latest accepted commit，且改动改变了事实或伏笔，必须提醒用户：后续章节可能已基于旧事实写成。完成本章 amend 后，继续审计从修订章到 latest 的范围，并列出可能需要人工复核的后续章节。

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  story-repair audit --chapters {global_chapter}-{latest_chapter} --format json
```

## 失败恢复

- review blocking：修正文后回 Step 2。
- data-agent JSON 格式不合格：只重跑 Step 3。
- `chapter-commit` rejected：根据 rejected 原因修复正文或 JSON 后回 Step 3。
- projection failed：只重跑 Step 4，必要时保留错误输出。
