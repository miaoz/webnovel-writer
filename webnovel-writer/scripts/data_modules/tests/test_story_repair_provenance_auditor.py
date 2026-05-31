#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import hashlib

from data_modules.story_repair.provenance_auditor import audit_project


def _write_contracts(project_root, chapter: int) -> None:
    story_root = project_root / ".story-system"
    (story_root / "chapters").mkdir(parents=True, exist_ok=True)
    (story_root / "reviews").mkdir(parents=True, exist_ok=True)
    (story_root / "chapters" / f"chapter_{chapter:03d}.json").write_text("{}", encoding="utf-8")
    (story_root / "reviews" / f"chapter_{chapter:03d}.review.json").write_text("{}", encoding="utf-8")


def _write_body(project_root, chapter: int) -> None:
    body_dir = project_root / "正文" / "第1卷"
    body_dir.mkdir(parents=True, exist_ok=True)
    (body_dir / f"第{chapter:04d}章-测试.md").write_text("正文", encoding="utf-8")


def test_audit_requires_current_body_and_outline_hashes(tmp_path):
    body_dir = tmp_path / "正文" / "第1卷"
    body_dir.mkdir(parents=True)
    body_path = body_dir / "第0001章-测试.md"
    body_path.write_text("新版正文", encoding="utf-8")

    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir()
    outline_section = "### 第 1 章：测试\n- 目标: 新版目标\n"
    outline_dir.joinpath("第1卷-详细大纲.md").write_text(
        "> 卷范围: 第1-1章\n\n" + outline_section,
        encoding="utf-8",
    )
    current_outline_hash = hashlib.sha256(outline_section.strip().encode("utf-8")).hexdigest()

    story_root = tmp_path / ".story-system"
    for directory in ("chapters", "reviews", "commits"):
        (story_root / directory).mkdir(parents=True, exist_ok=True)
    stale_hash = "0" * 64
    (story_root / "chapters" / "chapter_001.json").write_text(
        json.dumps({"provenance": {"outline_hash": stale_hash}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (story_root / "reviews" / "chapter_001.review.json").write_text(
        json.dumps({"provenance": {"outline_hash": stale_hash}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (story_root / "commits" / "chapter_001.commit.json").write_text(
        json.dumps(
            {
                "meta": {"chapter": 1, "status": "accepted"},
                "provenance": {"body_sha256": stale_hash, "outline_sha256": stale_hash},
                "projection_status": {"state": "done"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = audit_project(tmp_path, start=1, end=1)

    row = report["chapters"][0]
    assert row["classification"] == "provenance_hash_mismatch"
    assert row["repair_required"] is True
    assert row["hash_mismatches"] == [
        "body_sha256",
        "commit_outline_sha256",
        "chapter_contract_outline_hash",
        "review_contract_outline_hash",
    ]
    assert row["current_body_sha256"] == hashlib.sha256(body_path.read_bytes()).hexdigest()
    assert row["current_outline_sha256"] == current_outline_hash


def test_audit_classifies_accepted_commit_without_write_contracts(tmp_path):
    (tmp_path / ".webnovel" / "context_snapshots").mkdir(parents=True)
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps(
            {
                "progress": {"current_chapter": 33},
                "protagonist_state": {"location": {"current": "旧地点", "last_chapter": 19}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / ".webnovel" / "context_snapshots" / "ch0019.json").write_text("{}", encoding="utf-8")
    body_dir = tmp_path / "正文" / "第1卷"
    body_dir.mkdir(parents=True)
    (body_dir / "第0033章-盘点.md").write_text("正文", encoding="utf-8")
    commits_dir = tmp_path / ".story-system" / "commits"
    commits_dir.mkdir(parents=True)
    (commits_dir / "chapter_033.commit.json").write_text(
        json.dumps(
            {
                "meta": {"chapter": 33, "status": "accepted"},
                "projection_status": {"state": "done"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = audit_project(tmp_path, start=33, end=33)

    row = report["chapters"][0]
    assert row["chapter"] == 33
    assert row["body"] == "exists"
    assert row["chapter_contract"] == "missing"
    assert row["review_contract"] == "missing"
    assert row["commit"] == "accepted"
    assert row["projection"] == "done"
    assert row["classification"] == "accepted_commit_without_write_contracts"
    assert row["repair_required"] is True
    assert any(item["type"] == "state_location_lag" for item in report["state_anomalies"])
    assert any(item["path"].endswith("ch0019.json") for item in report["stale_files"])


def test_audit_reports_missing_body_commit_and_projection_states(tmp_path):
    (tmp_path / ".webnovel").mkdir(parents=True)
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps(
            {
                "progress": {
                    "current_chapter": 4,
                    "volumes_planned": [{"volume": 1, "chapters_range": "1-3"}],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir()
    (outline_dir / "第1卷-详细大纲.md").write_text(
        "\n".join(["### 第 1 章：一", "### 第 2 章：二", "### 第 3 章：三", "### 第 4 章：四"]),
        encoding="utf-8",
    )
    commits_dir = tmp_path / ".story-system" / "commits"
    commits_dir.mkdir(parents=True)
    for chapter, projection in {
        1: {"state": "failed: disk"},
        2: {"state": "skipped"},
        4: {"state": "queued"},
    }.items():
        (commits_dir / f"chapter_{chapter:03d}.commit.json").write_text(
            json.dumps({"meta": {"chapter": chapter, "status": "rejected"}, "projection_status": projection}),
            encoding="utf-8",
        )
    _write_body(tmp_path, 2)
    _write_body(tmp_path, 3)
    _write_body(tmp_path, 4)
    _write_contracts(tmp_path, 1)
    _write_contracts(tmp_path, 3)
    _write_contracts(tmp_path, 4)

    report = audit_project(tmp_path, start=1, end=4)

    rows = {row["chapter"]: row for row in report["chapters"]}
    assert rows[1]["classification"] == "missing_body"
    assert rows[1]["projection"] == "failed"
    assert rows[2]["classification"] == "missing_write_contracts"
    assert rows[2]["projection"] == "skipped"
    assert rows[3]["classification"] == "missing_commit"
    assert rows[3]["projection"] == "missing"
    assert rows[4]["projection"] == "pending"
    assert report["numbering_anomalies"] == [
        {"type": "volume_range_mismatch", "volume": 1, "state_count": 3, "outline_count": 4}
    ]
    assert "run_story_repair_rebuild_from_accepted_ledger" in report["recommended_actions"]
