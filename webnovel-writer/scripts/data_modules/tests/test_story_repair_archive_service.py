#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from data_modules.story_repair.archive_service import archive_stale_artifacts, stale_archive_plan


def test_archive_stale_artifacts_dry_run_keeps_sources(tmp_path):
    snapshots = tmp_path / ".webnovel" / "context_snapshots"
    snapshots.mkdir(parents=True)
    source = snapshots / "ch0011.json"
    source.write_text('{"chapter": 11}', encoding="utf-8")
    tmp_dir = tmp_path / ".webnovel" / "tmp"
    tmp_dir.mkdir(parents=True)
    tmp_file = tmp_dir / "review_results.json"
    tmp_file.write_text("{}", encoding="utf-8")

    plan = stale_archive_plan(tmp_path)
    result = archive_stale_artifacts(tmp_path, apply=False, archive_name="test-archive")

    assert {item["reason"] for item in plan} == {"legacy_context_snapshot", "legacy_tmp_artifact"}
    assert len(result["files"]) == 2
    assert result["apply"] is False
    assert source.is_file()
    assert tmp_file.is_file()
    assert not (tmp_path / result["manifest"]).exists()


def test_archive_stale_artifacts_apply_moves_files_and_writes_manifest(tmp_path):
    snapshots = tmp_path / ".webnovel" / "context_snapshots"
    snapshots.mkdir(parents=True)
    source = snapshots / "ch0019.json"
    source.write_text('{"chapter": 19}', encoding="utf-8")
    tmp_dir = tmp_path / ".webnovel" / "tmp"
    tmp_dir.mkdir(parents=True)
    tmp_file = tmp_dir / "extraction_result.json"
    tmp_file.write_text('{"ok": true}', encoding="utf-8")

    result = archive_stale_artifacts(tmp_path, apply=True, archive_name="test-archive")

    assert result["apply"] is True
    assert not source.exists()
    assert not tmp_file.exists()
    manifest_path = tmp_path / result["manifest"]
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert {item["old_path"] for item in manifest} == {
        ".webnovel/context_snapshots/ch0019.json",
        ".webnovel/tmp/extraction_result.json",
    }
    for item in manifest:
        archived = tmp_path / item["new_path"]
        assert archived.is_file()
        assert item["sha256"]
