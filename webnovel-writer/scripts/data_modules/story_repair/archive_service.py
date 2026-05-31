#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from data_modules.story_repair.provenance_auditor import audit_project


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stale_archive_plan(project_root: Path) -> list[dict[str, Any]]:
    project_root = Path(project_root)
    audit = audit_project(project_root)
    rows = list(audit.get("stale_files") or [])
    tmp_dir = project_root / ".webnovel" / "tmp"
    if tmp_dir.is_dir():
        for path in sorted(tmp_dir.glob("*")):
            if path.is_file():
                rows.append(
                    {
                        "path": path.relative_to(project_root).as_posix(),
                        "chapter": 0,
                        "reason": "legacy_tmp_artifact",
                    }
                )
    return rows


def archive_stale_artifacts(
    project_root: Path,
    *,
    apply: bool = False,
    archive_name: str | None = None,
) -> dict[str, Any]:
    project_root = Path(project_root)
    archive_name = archive_name or f"restructure-{datetime.now().strftime('%Y%m%d')}"
    archive_root = project_root / ".webnovel" / "archive" / archive_name
    rows = stale_archive_plan(project_root)
    manifest: list[dict[str, Any]] = []

    for row in rows:
        source = project_root / row["path"]
        target = archive_root / row["path"]
        item = {
            "old_path": row["path"],
            "new_path": target.relative_to(project_root).as_posix(),
            "reason": row.get("reason", "stale_artifact"),
            "sha256": _sha256(source) if source.is_file() else "",
        }
        manifest.append(item)
        if apply and source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))

    manifest_path = archive_root / "manifest.json"
    if apply:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "apply": apply,
        "archive_root": archive_root.relative_to(project_root).as_posix(),
        "files": manifest,
        "manifest": manifest_path.relative_to(project_root).as_posix(),
    }

