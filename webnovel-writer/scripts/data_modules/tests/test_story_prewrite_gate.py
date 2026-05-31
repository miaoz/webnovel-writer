#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from data_modules.story_prewrite_gate import run_prewrite_gate


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_prewrite_gate_blocks_missing_contracts(tmp_path):
    (tmp_path / ".webnovel").mkdir()
    _write_json(tmp_path / ".webnovel" / "state.json", {"progress": {"current_chapter": 2}})
    (tmp_path / "大纲").mkdir()
    (tmp_path / "大纲" / "第1卷-详细大纲.md").write_text(
        "### 第 3 章：下一章\n- 目标: 写下一章\n", encoding="utf-8"
    )

    result = run_prewrite_gate(tmp_path, 3)

    assert result.ready is False
    assert "missing_chapter_contract" in result.blocking_reasons
    assert "missing_review_contract" in result.blocking_reasons


def test_prewrite_gate_ready_when_contracts_outline_and_previous_commit_exist(tmp_path):
    _write_json(
        tmp_path / ".webnovel" / "state.json",
        {
            "progress": {"current_chapter": 2, "volumes_planned": [{"volume": 1, "chapters_range": "1-48"}]},
            "protagonist_state": {"location": {"last_chapter": 2}},
        },
    )
    (tmp_path / "大纲").mkdir()
    (tmp_path / "大纲" / "第1卷-详细大纲.md").write_text(
        "### 第 3 章：下一章\n- 目标: 写下一章\n", encoding="utf-8"
    )
    _write_json(tmp_path / ".story-system" / "MASTER_SETTING.json", {"meta": {"contract_type": "MASTER_SETTING"}})
    _write_json(
        tmp_path / ".story-system" / "chapters" / "chapter_003.json",
        {"meta": {"chapter": 3}, "chapter_brief": {"chapter_directive": {"goal": "写下一章"}}},
    )
    _write_json(tmp_path / ".story-system" / "reviews" / "chapter_003.review.json", {"meta": {"chapter": 3}})
    _write_json(tmp_path / ".story-system" / "volumes" / "volume_001.json", {"meta": {"volume": 1}})
    _write_json(
        tmp_path / ".story-system" / "commits" / "chapter_002.commit.json",
        {"meta": {"chapter": 2, "status": "accepted"}, "provenance": {"commit_mode": "native_write"}},
    )

    result = run_prewrite_gate(tmp_path, 3)

    assert result.ready is True
    assert result.blocking_reasons == []
    assert result.provenance["previous_accepted_commit"] == 2


def test_prewrite_gate_blocks_existing_commit_without_rewrite(tmp_path):
    _write_json(tmp_path / ".webnovel" / "state.json", {"progress": {"current_chapter": 3}})
    (tmp_path / "大纲").mkdir()
    (tmp_path / "大纲" / "第1卷-详细大纲.md").write_text(
        "### 第 3 章：下一章\n- 目标: 写下一章\n", encoding="utf-8"
    )
    _write_json(tmp_path / ".story-system" / "chapters" / "chapter_003.json", {"meta": {"chapter": 3}})
    _write_json(tmp_path / ".story-system" / "reviews" / "chapter_003.review.json", {"meta": {"chapter": 3}})
    _write_json(tmp_path / ".story-system" / "commits" / "chapter_003.commit.json", {"meta": {"chapter": 3, "status": "accepted"}})

    blocked = run_prewrite_gate(tmp_path, 3)
    allowed = run_prewrite_gate(tmp_path, 3, rewrite=True)

    assert "target_commit_exists" in blocked.blocking_reasons
    assert "target_commit_exists" not in allowed.blocking_reasons
