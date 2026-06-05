from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[2]


def test_markdown_eval_fixtures_are_outside_agents_tree():
    agents_fixture_root = PLUGIN_ROOT / "agents/evals/files"

    assert not list(agents_fixture_root.rglob("*.md"))


def test_eval_prompts_use_top_level_fixture_path():
    eval_files = [
        PLUGIN_ROOT / "agents/evals/evals.json",
        PLUGIN_ROOT / "skills/webnovel-write/evals/evals.json",
        PLUGIN_ROOT / "skills/webnovel-review/evals/evals.json",
    ]

    for eval_file in eval_files:
        text = eval_file.read_text(encoding="utf-8")
        assert "agents/evals/files/test-project" not in text
        assert "evals/files/test-project" in text
