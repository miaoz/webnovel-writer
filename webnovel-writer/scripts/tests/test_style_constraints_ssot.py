from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
POLISH_GUIDE = PLUGIN_ROOT / "skills/webnovel-write/references/polish-guide.md"
ANTI_AI_GUIDE = PLUGIN_ROOT / "skills/webnovel-write/references/anti-ai-guide.md"
STYLE_ADAPTER = PLUGIN_ROOT / "skills/webnovel-write/references/style-adapter.md"
DASH = "\u2014" * 2


def read(relative_path: str) -> str:
    return (PLUGIN_ROOT / relative_path).read_text(encoding="utf-8")


def test_polish_guide_defines_concrete_style_rules():
    text = POLISH_GUIDE.read_text(encoding="utf-8")

    assert "句式规则" in text
    assert "标点节奏" in text
    assert "破折号" in text
    assert "不是X" in text
    assert DASH in text


def test_stage_guides_keep_distinct_operational_roles():
    anti_ai = ANTI_AI_GUIDE.read_text(encoding="utf-8")
    style_adapter = STYLE_ADAPTER.read_text(encoding="utf-8")

    assert "Step 2" in anti_ai
    assert "写作任务书" in anti_ai
    assert "执行方式" in anti_ai
    assert "输出要求" in anti_ai

    assert "Step 4" in style_adapter
    assert "输入" in style_adapter
    assert "输出" in style_adapter
    assert "禁改项" in style_adapter
    assert "执行流程" in style_adapter
    assert "改写日志" in style_adapter


def test_rule_consumers_reference_polish_guide_without_copying_rules():
    delegates = [
        "skills/webnovel-write/references/anti-ai-guide.md",
        "skills/webnovel-write/references/style-adapter.md",
        "agents/reviewer.md",
        "agents/context-agent.md",
        "references/codex/agent-protocols.md",
        "skills/webnovel-revise/SKILL.md",
    ]
    forbidden_snippets = [
        "正文禁止使用破折号",
        "全文不得出现破折号",
        "不是X，而是Y",
        "不是X，是Y",
        "破折号（",
        DASH,
        "你最容易犯的错",
        "写作时的 5 个即时检查",
        "替代方案速查表",
        "AI痕迹快速替换",
        "缓缓/淡淡/微微",
        "他搁下杯子",
        "他没抬头",
    ]

    for relative_path in delegates:
        text = read(relative_path)
        assert "polish-guide.md" in text, relative_path
        for snippet in forbidden_snippets:
            assert snippet not in text, f"{relative_path} copies concrete rule: {snippet}"


def test_skill_files_do_not_contain_migration_notes_or_source_meta():
    skill_files = [
        "skills/webnovel-write/SKILL.md",
        "skills/webnovel-review/SKILL.md",
        "skills/webnovel-revise/SKILL.md",
    ]
    forbidden_snippets = [
        "唯一文风约束源",
        "唯一风格源",
        "统一文风约束",
        "兼容旧引用",
        "迁移",
        "跳转",
    ]

    for relative_path in skill_files:
        text = read(relative_path)
        for snippet in forbidden_snippets:
            assert snippet not in text, f"{relative_path} contains patch meta: {snippet}"
