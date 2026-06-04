# Claude Code / Codex 兼容版说明

本文档说明 `webnovel-writer` 兼容版的运行方式。兼容版不是 fork，也不是两套插件；Claude Code 与 Codex 共用同一套 `scripts/`、`skills/`、`references/`、`templates/`、`dashboard/` 和书项目数据结构。

## 兼容原则

- 插件核心只维护一份：`webnovel-writer/`
- Claude Code 使用 `.claude-plugin/plugin.json`
- Codex 使用 `.codex-plugin/plugin.json`
- 书项目仍由 `PROJECT_ROOT` 承载，`.story-system/` 是主链真源，`.webnovel/` 是 read-model / projection
- Claude Code 的 `Agent(...)` 调用保留；Codex 使用 `references/codex/agent-protocols.md` 中的 inline protocol 生成同样 artifacts

## 目录角色

| 名称 | 含义 |
|------|------|
| `WORKSPACE_ROOT` | 当前工作区，可包含多本书 |
| `PROJECT_ROOT` | 单本书项目根目录，包含 `.webnovel/state.json` |
| `WEBNOVEL_PLUGIN_ROOT` | 插件根目录，必须包含 `scripts/`、`skills/`、`references/` |
| `CLAUDE_PLUGIN_ROOT` | Claude Code 提供的插件根目录，兼容版会作为 fallback 使用 |

## 环境变量优先级

工作区解析：

```bash
WEBNOVEL_WORKSPACE_ROOT > CODEX_WORKSPACE_ROOT > CLAUDE_PROJECT_DIR > PWD
```

用户级配置根目录：

```bash
WEBNOVEL_HOME > WEBNOVEL_CLAUDE_HOME > CODEX_HOME > CLAUDE_HOME > ~/.claude
```

插件根目录：

```bash
WEBNOVEL_PLUGIN_ROOT > CLAUDE_PLUGIN_ROOT > 从当前 SKILL.md 位置解析插件根
```

Codex 中建议显式设置：

```bash
export WEBNOVEL_WORKSPACE_ROOT="/path/to/workspace"
export WEBNOVEL_PLUGIN_ROOT="/path/to/webnovel-writer/webnovel-writer"
```

## 安装方式

### Claude Code

```bash
claude plugin marketplace add lingfengQAQ/webnovel-writer --scope user
claude plugin install webnovel-writer@webnovel-writer-marketplace --scope user
```

### Codex

先验证插件 manifest：

```bash
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py webnovel-writer
```

如果已经把本仓库加入 Codex marketplace：

```bash
codex plugin marketplace add <marketplace-root>
codex plugin add webnovel-writer@<marketplace-name>
```

本仓库没有默认提交 `.agents/plugins/marketplace.json`。需要本地 marketplace 时，应显式创建并选择 repo-local 或 personal marketplace 模式，避免把个人 Codex 配置混入仓库。

## 使用方式

Claude Code 与 Codex 都使用同一组 skill：

```bash
/webnovel-init
/webnovel-plan 1
/webnovel-write 1
/webnovel-review 1-5
/webnovel-amend 3
/webnovel-query 伏笔
/webnovel-dashboard
/webnovel-learn "本章的危机钩设计有效"
```

CLI 统一入口：

```bash
python -X utf8 "${WEBNOVEL_PLUGIN_ROOT}/scripts/webnovel.py" --project-root "${PROJECT_ROOT}" preflight --format json
```

Story System 主链检查：

```bash
python -X utf8 "${WEBNOVEL_PLUGIN_ROOT}/scripts/webnovel.py" --project-root "${PROJECT_ROOT}" story-events --health
```

## Agent 兼容方式

Claude Code 路径：

- `webnovel-write` 调用 `context-agent`、`reviewer`、`data-agent`
- `webnovel-review` 调用 `reviewer`
- `webnovel-amend` 调用 `reviewer`、`data-agent`
- `webnovel-init` 可调用 `deconstruction-agent`

Codex 路径：

- 读取 `references/codex/agent-protocols.md`
- 在当前会话中执行对应 inline protocol
- 写出与 Claude Agent 相同的 JSON artifacts

关键 artifacts：

```text
.webnovel/tmp/review_results.json
.webnovel/tmp/fulfillment_result.json
.webnovel/tmp/disambiguation_result.json
.webnovel/tmp/extraction_result.json
```

只要这些 artifacts 的 schema 不变，后续 `review-pipeline` 和 `chapter-commit` 不需要区分运行时。

## 验证命令

```bash
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py webnovel-writer
python3 -m json.tool webnovel-writer/.claude-plugin/plugin.json >/dev/null
python3 -m json.tool webnovel-writer/.codex-plugin/plugin.json >/dev/null
.venv/bin/python -X utf8 webnovel-writer/scripts/webnovel.py preflight --format json
.venv/bin/pytest -q
```

若只改 prompt / 文档，可先跑：

```bash
.venv/bin/pytest webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py \
  webnovel-writer/scripts/data_modules/tests/test_codex_manifest.py -q --no-cov
```

## 常见问题

### Codex 找不到 `scripts/webnovel.py`

检查 `WEBNOVEL_PLUGIN_ROOT` 是否指向插件根目录，而不是外层仓库根目录：

```bash
ls "${WEBNOVEL_PLUGIN_ROOT}/scripts/webnovel.py"
```

正确路径通常类似：

```text
/path/to/webnovel-writer/webnovel-writer
```

### Codex 没有 subagent 工具

这是预期情况。使用 `references/codex/agent-protocols.md` 中的 inline protocol，仍然生成相同 artifacts。

### `preflight` 命中了错误书项目

显式设置工作区或项目根：

```bash
export WEBNOVEL_WORKSPACE_ROOT="/path/to/workspace"
python -X utf8 "${WEBNOVEL_PLUGIN_ROOT}/scripts/webnovel.py" --project-root "/path/to/book" preflight --format json
```

### 不要把故事内容改进插件提交

中文书名目录是故事内容 submodule。兼容版适配只改插件本体，不应混入故事正文、大纲或子模块 pointer，除非任务明确要求。

## 兼容边界

- Codex inline protocol 不提供 Claude subagent 的上下文隔离，但 artifacts 和 CLI 校验会约束输出。
- Dashboard 仍是同一套 FastAPI/Vite 面板；只有 dashboard 代码改动时才需要重跑前端 build。
- `.claude-plugin/plugin.json` 与 `.codex-plugin/plugin.json` 都必须保留。
