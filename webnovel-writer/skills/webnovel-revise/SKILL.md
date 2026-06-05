---
name: webnovel-revise
description: 根据用户修改意见对已提交章节做受控修订；事实型修订必须先修改大纲/合同，再改正文并重新入链。
allowed-tools: Read Grep Write Edit Bash Agent
---

# Revision Skill

## 目标

把用户的修改意见转成可审计、受合同约束的章节修订：先判定修订类型，事实型修订必须大纲先行，正文改完后复用 `webnovel-amend` 的审查、事实提取、`CHAPTER_COMMIT` 覆盖和投影刷新链路。

适用：用户希望插件协助修改已提交章节，而不是自己手改 Markdown 后再 `/webnovel-amend`。

不适用：
- 只审查问题，用 `/webnovel-review`。
- 已经人工改完正文，只需要重新入链，用 `/webnovel-amend`。
- 未提交的新章，继续 `/webnovel-write` 的 Step 3-5。

## 硬规则

- 事实型修订必须大纲先行：人物状态、事件结果、道具归属、地点时间、关系变化、伏笔方向、章末结局等变化，在修改正文之前必须先更新对应大纲/合同。
- 一旦判定为事实型修订，必须阻断正文修改，先生成大纲修订提案并等待用户确认。
- 用户确认前不得改正文、不得改 `.webnovel/state.json`、不得改 `index.db`、不得伪造 review/data-agent artifact。
- 只做最小必要改动；默认不整章重写。
- 多章修订必须逐章串行，不并行。
- blocking review 未解决，不跑 data-agent / chapter-commit。
- `repair_backfill` 只用于历史重建；本流程必须用 `native_write`。
- `.story-system/` 合同树和 `大纲/` 是修订前置真源；`.webnovel/*` 是投影/read-model。

## 修订类型

| 类型 | 处理 |
|------|------|
| 表达/文风 | 可直接修正文，之后审查入链 |
| 节奏/删冗/补描写 | 可直接修正文，不能改变事实节点 |
| 正文纠错为既有大纲事实 | 不改大纲，只把正文拉回当前章纲/合同 |
| 本章事实变化 | 先改本章章纲和 runtime contracts，再改正文 |
| 后续事实变化 | 先改本章及受影响后续章纲/时间线，再改正文 |
| 卷级节奏变化 | 先改卷纲、节拍表、时间线和相关章纲 |
| 核心设定/世界规则变化 | 先提出 `amend-master` / `amend-volume` 级别修订提案，用户确认后再落地 |

## 流程

### Step 1：定位项目与章节

```bash
export WORKSPACE_ROOT="${WEBNOVEL_WORKSPACE_ROOT:-${CODEX_WORKSPACE_ROOT:-${CLAUDE_PROJECT_DIR:-$PWD}}}"
export WEBNOVEL_PLUGIN_ROOT="${WEBNOVEL_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
export SCRIPTS_DIR="${WEBNOVEL_PLUGIN_ROOT}/scripts"
export PROJECT_ROOT="$(python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where)"

python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" preflight
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" placeholder-scan --format text
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  prewrite-check --volume {volume_num} --chapter {chapter_in_volume} --rewrite
```

说明：script path must resolve to plugin `scripts/`；Codex 中如 `WEBNOVEL_PLUGIN_ROOT` 为空，先从当前加载的 `SKILL.md` 位置解析插件根目录（本 skill 为 `../..`），再使用 `../../scripts`。

若 `prewrite-check --rewrite` 的 `ready=false`，先修复 blocking_reasons，不进入修订。

### Step 2：读取修订上下文

必须读取：

- 当前章正文：`正文/第{volume_num}卷/第{chapter_in_volume}章-*.md`
- 当前章章纲：`大纲/第{volume_num}卷-详细大纲.md` 中对应章节，或拆分章纲文件
- 当前卷节拍表、时间线、卷纲
- `.story-system/MASTER_SETTING.json`
- `.story-system/volumes/volume_{NNN}.json`
- `.story-system/chapters/chapter_{NNN}.json`
- `.story-system/reviews/chapter_{NNN}.review.json`
- 最近 2-5 章 summary、核心角色状态、活跃伏笔（按修订范围按需读取）

### Step 3：修订影响分类

先把用户修改意见整理为 `.webnovel/tmp/revision_request.json`，至少包含：

```json
{
  "volume": 1,
  "chapter": 3,
  "user_request": "...",
  "revision_type": "fact_change",
  "affected_scope": "chapter|future_chapters|volume|master",
  "facts_to_change": [],
  "text_only_changes": [],
  "blocking": true,
  "requires_outline_first": true
}
```

判定为事实型修订时：

1. 标记 `requires_outline_first=true`。
2. 阻断正文修改。
3. 输出大纲修订提案。
4. 直接询问用户是否确认落地，确认前停止。

### Step 4A：非事实修订，生成正文修订任务书

若只涉及表达、文风、节奏、删冗、补描写，生成 `.webnovel/tmp/revision_plan.json`：

```json
{
  "mode": "text_only",
  "preserve_facts": true,
  "must_keep_nodes": [],
  "forbidden_changes": [],
  "target_sections": [],
  "style_constraints": [],
  "acceptance_checks": []
}
```

然后只按该任务书修改正文。不得新增未在大纲/合同中存在的事实。

### Step 4B：事实型修订，先改大纲/合同

事实型修订先生成大纲修订提案，不直接改正文。

提案保存到 `.webnovel/tmp/revision_outline_proposal.json`，至少包含：

```json
{
  "volume": 1,
  "chapter": 3,
  "affected_scope": "chapter",
  "outline_files": [],
  "contract_files": [],
  "timeline_changes": [],
  "chapter_outline_changes": [],
  "downstream_risk": [],
  "requires_user_confirmation": true
}
```

用户确认后，按影响范围落地：

- 本章事实变化：修改当前章纲。
- 后续事实变化：修改当前章纲、受影响后续章纲和时间线。
- 卷级节奏变化：修改卷纲、节拍表、时间线和相关章纲。
- 核心设定/世界规则变化：先提出 `amend-master` / `amend-volume` 级别修订提案；没有用户确认不得更新上层设定。

落地后必须从更新后的详细大纲解析真实 `CHAPTER_GOAL`，再刷新 runtime contracts：

```bash
GENRE="$(python -X utf8 -c "import json; s=json.load(open('${PROJECT_ROOT}/.webnovel/state.json',encoding='utf-8')); print((s.get('project_info') or {}).get('genre') or (s.get('project') or {}).get('genre',''))")"

python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  story-system "${CHAPTER_GOAL}" --genre "${GENRE}" --volume {volume_num} --chapter {chapter_in_volume} --persist --emit-runtime-contracts --format both

python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  prewrite-check --volume {volume_num} --chapter {chapter_in_volume} --rewrite
```

章节级刷新不得传 `--refresh-master`。

### Step 5：修改正文

基于当前章正文、用户确认过的修订任务书、更新后的章纲和 runtime contracts 修改正文。

要求：

- 只改必要段落。
- 保留已成立且未被用户要求改变的事实。
- 保留本章必须覆盖节点、禁区、章末开放问题和风格约束。
- 修改后保存 `.webnovel/tmp/revision_diff_summary.md`，说明改动范围、事实变化、未改原因。

### Step 6：审查当前正文

必须调用 `reviewer`，保存结构化 JSON。

#### Claude Code path

```text
Agent(
  subagent_type: "webnovel-writer:reviewer",
  prompt: "volume={volume_num} chapter={chapter_in_volume}; chapter_file=${CHAPTER_FILE}; project_root=${PROJECT_ROOT}; scripts_dir=${SCRIPTS_DIR}。这是按用户修订意见完成后的受控复审，严格输出 reviewer schema JSON，并保存到 ${PROJECT_ROOT}/.webnovel/tmp/review_results.json。重点检查：是否遵守更新后的章纲/合同、是否仍有旧事实残留、是否引入未确认事实、是否违反 polish-guide.md 中的文风约束。"
)
```

#### Codex path

读取 `../../references/codex/agent-protocols.md` 与 `../webnovel-write/references/polish-guide.md`，在当前会话执行 `reviewer inline protocol`。必须写出 `${PROJECT_ROOT}/.webnovel/tmp/review_results.json` 后再运行下方 `review-pipeline`。

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" review-pipeline \
  --volume {volume_num} --chapter {chapter_in_volume} \
  --review-results "${PROJECT_ROOT}/.webnovel/tmp/review_results.json" \
  --metrics-out "${PROJECT_ROOT}/.webnovel/tmp/review_metrics.json" \
  --report-file "审查报告/第{volume_num}卷第{chapter_in_volume}章受控修订审查报告.md" \
  --save-metrics
```

若存在 `blocking=true`，先修正文，再从 Step 6 重跑。

### Step 7：重新提取事实

必须调用 `data-agent`，基于修订后的正文重新生成三份 JSON。

#### Claude Code path

```text
Agent(
  subagent_type: "webnovel-writer:data-agent",
  prompt: "volume={volume_num} chapter={chapter_in_volume}; chapter_file=${CHAPTER_FILE}; project_root=${PROJECT_ROOT}; scripts_dir=${SCRIPTS_DIR}。这是用户受控修订后的重新入链：从当前正文提取事实，生成 .webnovel/tmp/fulfillment_result.json、disambiguation_result.json、extraction_result.json；fulfillment_result.json 必须顶层包含 planned_nodes/covered_nodes/missed_nodes/extra_nodes；disambiguation_result.json 必须顶层包含 pending；extraction_result.json 必须顶层包含 accepted_events/state_deltas/entity_deltas/entities_appeared/scenes/summary_text；accepted_events 子项必须包含 event_id/chapter/event_type/subject/payload；不直接写 state/index/summaries/memory。"
)
```

#### Codex path

读取 `../../references/codex/agent-protocols.md`，在当前会话执行 `data-agent inline protocol`。必须写出 `${PROJECT_ROOT}/.webnovel/tmp/fulfillment_result.json`、`${PROJECT_ROOT}/.webnovel/tmp/disambiguation_result.json`、`${PROJECT_ROOT}/.webnovel/tmp/extraction_result.json` 后再覆盖 CHAPTER_COMMIT。

### Step 8：覆盖 CHAPTER_COMMIT 并刷新投影

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" chapter-commit \
  --volume {volume_num} --chapter {chapter_in_volume} \
  --review-result "${PROJECT_ROOT}/.webnovel/tmp/review_results.json" \
  --fulfillment-result "${PROJECT_ROOT}/.webnovel/tmp/fulfillment_result.json" \
  --disambiguation-result "${PROJECT_ROOT}/.webnovel/tmp/disambiguation_result.json" \
  --extraction-result "${PROJECT_ROOT}/.webnovel/tmp/extraction_result.json" \
  --commit-mode native_write
```

若输出为 rejected，停止并报告 missed_nodes / pending / blocking_count。

### Step 9：验证

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  story-repair audit --chapters {global_chapter}-{global_chapter} --format json
```

成功标准：

- commit status 为 accepted。
- `projection_status` 全部为 done 或 skipped。
- audit 中该章 `repair_required=false`。
- 修订的是最新章时，下一章 `prewrite-check` 仍为 `ready=true`。
- 事实型修订的 `outline_sha256` 与 `CHAPTER_COMMIT` 使用的是更新后的大纲。

## 非最新章修订

如果修订章节早于 latest accepted commit，且改动改变了事实或伏笔，完成本章 revise 后继续审计从修订章到 latest 的范围，并列出可能需要复核或连带修订的后续章节。

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  story-repair audit --chapters {global_chapter}-{latest_chapter} --format json
```

## 失败恢复

- 分类不确定：默认当作事实可能变化处理，先生成提案让用户确认。
- 用户不同意大纲修订提案：不改正文，结束流程或改走非事实修订范围。
- review blocking：修正文后回 Step 6。
- data-agent JSON 格式不合格：只重跑 Step 7。
- `chapter-commit` rejected：根据 rejected 原因修复正文或 JSON 后回 Step 7。
- projection failed：只重跑 Step 8，必要时保留错误输出。
