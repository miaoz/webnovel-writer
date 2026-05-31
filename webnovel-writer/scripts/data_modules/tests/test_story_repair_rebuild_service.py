#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from data_modules.story_repair.rebuild_service import apply_rebuild_from_ledger, build_rebuild_plan


def test_rebuild_dry_run_plan_does_not_mutate_story_artifacts(tmp_path):
    story_root = tmp_path / ".story-system"
    webnovel_root = tmp_path / ".webnovel"
    (story_root / "commits").mkdir(parents=True)
    webnovel_root.mkdir()
    state_path = webnovel_root / "state.json"
    state_path.write_text(json.dumps({"progress": {"current_chapter": 1}}), encoding="utf-8")

    plan = build_rebuild_plan(tmp_path, start=1, end=3, dry_run=True)

    assert plan["chapters_to_rebuild_contracts"] == [1, 2, 3]
    assert plan["chapters_to_rebuild_commits"] == [1, 2, 3]
    assert plan["projection_targets"] == ["state", "index", "summary", "memory"]
    assert plan["requires_human_review"] is True
    assert json.loads(state_path.read_text(encoding="utf-8")) == {"progress": {"current_chapter": 1}}


def test_apply_rebuild_from_ledger_creates_contracts_commits_and_state(tmp_path):
    (tmp_path / ".webnovel").mkdir()
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps(
            {
                "progress": {"current_chapter": 1, "volumes_planned": [{"volume": 1, "chapters_range": "1-50"}]},
                "protagonist_state": {"location": {"last_chapter": 1}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    body_dir = tmp_path / "正文" / "第1卷"
    body_dir.mkdir(parents=True)
    (body_dir / "第0001章-开局.md").write_text("正文一", encoding="utf-8")
    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir()
    (outline_dir / "第1卷-详细大纲.md").write_text(
        "> 卷范围: 第1-2章\n\n### 第 1 章：开局\n- 目标: 开局\n- 时间锚点: D1\n\n### 第 2 章：下一章\n- 目标: 下一章\n",
        encoding="utf-8",
    )
    ledger = {
        "ledger_status": "accepted_for_repair",
        "chapters": [
            {
                "chapter": 1,
                "title": "开局",
                "time_anchor": "D1",
                "summary": "修复摘要",
                "source_body": "正文/第1卷/第0001章-开局.md",
                "source_outline_hash": "hash",
            }
        ],
    }
    ledger_path = tmp_path / "修复报告" / "chapter-ledger.json"
    ledger_path.parent.mkdir()
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")

    result = apply_rebuild_from_ledger(tmp_path, start=1, end=1, ledger_path=ledger_path)

    assert result["applied"] is True
    assert (tmp_path / ".story-system" / "chapters" / "chapter_001.json").is_file()
    assert (tmp_path / ".story-system" / "reviews" / "chapter_001.review.json").is_file()
    assert (tmp_path / ".story-system" / "commits" / "chapter_001.commit.json").is_file()
    assert (tmp_path / ".story-system" / "chapters" / "chapter_002.json").is_file()
    state = json.loads((tmp_path / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    assert state["progress"]["current_chapter"] == 1
    assert state["progress"]["volumes_planned"][0]["chapters_range"] == "1-2"
    assert state["protagonist_state"]["location"]["last_chapter"] == 1
