#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import hashlib
from pathlib import Path
from typing import Any

try:
    from chapter_paths import find_chapter_file
except ImportError:  # pragma: no cover
    from scripts.chapter_paths import find_chapter_file

from data_modules.story_contracts import StoryContractPaths, read_json_if_exists
from data_modules.story_repair.outline_catalog import OutlineChapterRecord
from data_modules.story_repair.outline_catalog import load_outline_catalog


_SNAPSHOT_RE = re.compile(r"ch(?P<chapter>\d{3,4})\.json$")


def _read_state(project_root: Path) -> dict[str, Any]:
    path = project_root / ".webnovel" / "state.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


def _status_exists(path: Path) -> str:
    return "exists" if path.is_file() else "missing"


def _commit_status(payload: Any) -> str:
    if not payload:
        return "missing"
    return str((payload.get("meta") or {}).get("status") or "exists")


def _sha256_file(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _projection_status(payload: Any) -> str:
    if not payload:
        return "missing"
    projection = payload.get("projection_status") or {}
    if not isinstance(projection, dict) or not projection:
        return "unknown"
    values = {str(value) for value in projection.values()}
    if any(value.startswith("failed:") for value in values):
        return "failed"
    if "done" in values:
        return "done"
    if values <= {"skipped"}:
        return "skipped"
    return "pending"


def _classify(row: dict[str, Any]) -> str:
    if row["commit"] == "accepted" and (
        row["chapter_contract"] == "missing" or row["review_contract"] == "missing"
    ):
        return "accepted_commit_without_write_contracts"
    if row["body"] == "missing":
        return "missing_body"
    if row["chapter_contract"] == "missing" or row["review_contract"] == "missing":
        return "missing_write_contracts"
    if row["commit"] == "missing":
        return "missing_commit"
    if row.get("hash_mismatches"):
        return "provenance_hash_mismatch"
    return "native"


def _expected_outline_hash(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    for source in (
        payload.get("provenance") or {},
        payload.get("source") or {},
        payload.get("meta") or {},
    ):
        value = str(source.get("outline_hash") or source.get("source_outline_hash") or "").strip()
        if value:
            return value
    return ""


def _hash_mismatches(
    *,
    body_hash: str,
    outline_record: OutlineChapterRecord | None,
    commit_payload: dict[str, Any] | None,
    chapter_contract: dict[str, Any] | None,
    review_contract: dict[str, Any] | None,
) -> list[str]:
    if not commit_payload:
        return []

    mismatches: list[str] = []
    provenance = commit_payload.get("provenance") or {}
    expected_body = str(provenance.get("body_sha256") or "").strip()
    expected_commit_outline = str(provenance.get("outline_sha256") or "").strip()
    current_outline = outline_record.outline_hash if outline_record else ""

    if expected_body and body_hash and expected_body != body_hash:
        mismatches.append("body_sha256")
    if expected_commit_outline and current_outline and expected_commit_outline != current_outline:
        mismatches.append("commit_outline_sha256")

    expected_chapter_outline = _expected_outline_hash(chapter_contract)
    if expected_chapter_outline and current_outline and expected_chapter_outline != current_outline:
        mismatches.append("chapter_contract_outline_hash")

    expected_review_outline = _expected_outline_hash(review_contract)
    if expected_review_outline and current_outline and expected_review_outline != current_outline:
        mismatches.append("review_contract_outline_hash")

    return mismatches


def _stale_context_snapshots(project_root: Path) -> list[dict[str, Any]]:
    snapshots = project_root / ".webnovel" / "context_snapshots"
    rows: list[dict[str, Any]] = []
    if not snapshots.is_dir():
        return rows
    for path in sorted(snapshots.glob("ch*.json")):
        match = _SNAPSHOT_RE.match(path.name)
        chapter = int(match.group("chapter")) if match else 0
        rows.append(
            {
                "path": path.relative_to(project_root).as_posix(),
                "chapter": chapter,
                "reason": "legacy_context_snapshot",
            }
        )
    return rows


def _state_anomalies(state: dict[str, Any]) -> list[dict[str, Any]]:
    progress = state.get("progress") if isinstance(state.get("progress"), dict) else {}
    location = (
        (state.get("protagonist_state") or {}).get("location")
        if isinstance(state.get("protagonist_state"), dict)
        else {}
    )
    current = int(progress.get("current_chapter") or 0)
    last_location = int((location or {}).get("last_chapter") or 0)
    anomalies: list[dict[str, Any]] = []
    if current and last_location and last_location < current:
        anomalies.append(
            {
                "type": "state_location_lag",
                "current_chapter": current,
                "location_last_chapter": last_location,
            }
        )
    return anomalies


def _numbering_anomalies(project_root: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    catalog = load_outline_catalog(project_root)
    outline_counts: dict[int, int] = {}
    for record in catalog:
        outline_counts[record.volume] = max(outline_counts.get(record.volume, 0), record.chapter_in_volume)

    progress = state.get("progress") if isinstance(state.get("progress"), dict) else {}
    planned = progress.get("volumes_planned") if isinstance(progress.get("volumes_planned"), list) else []
    anomalies: list[dict[str, Any]] = []
    for item in planned:
        if not isinstance(item, dict):
            continue
        volume = int(item.get("volume") or 0)
        match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(item.get("chapters_range") or ""))
        if not volume or not match:
            continue
        state_count = int(match.group(2)) - int(match.group(1)) + 1
        outline_count = outline_counts.get(volume)
        if outline_count and outline_count != state_count:
            anomalies.append(
                {
                    "type": "volume_range_mismatch",
                    "volume": volume,
                    "state_count": state_count,
                    "outline_count": outline_count,
                }
            )
    return anomalies


def audit_project(project_root: Path, start: int = 1, end: int | None = None) -> dict[str, Any]:
    project_root = Path(project_root)
    paths = StoryContractPaths.from_project_root(project_root)
    state = _read_state(project_root)
    if end is None:
        end = int(((state.get("progress") or {}).get("current_chapter") or start))

    chapters: list[dict[str, Any]] = []
    contract_anomalies: list[dict[str, Any]] = []
    outline_by_chapter = {record.global_chapter: record for record in load_outline_catalog(project_root)}
    for chapter in range(start, end + 1):
        body = find_chapter_file(project_root, chapter)
        commit_payload = read_json_if_exists(paths.commit_json(chapter))
        chapter_contract = read_json_if_exists(paths.chapter_json(chapter))
        review_contract = read_json_if_exists(paths.review_json(chapter))
        body_hash = _sha256_file(body)
        outline_record = outline_by_chapter.get(chapter)
        outline_hash = outline_record.outline_hash if outline_record else ""
        row = {
            "chapter": chapter,
            "body": "exists" if body else "missing",
            "body_path": body.relative_to(project_root).as_posix() if body else "",
            "chapter_contract": _status_exists(paths.chapter_json(chapter)),
            "review_contract": _status_exists(paths.review_json(chapter)),
            "commit": _commit_status(commit_payload),
            "projection": _projection_status(commit_payload),
            "current_body_sha256": body_hash,
            "current_outline_sha256": outline_hash,
        }
        row["hash_mismatches"] = _hash_mismatches(
            body_hash=body_hash,
            outline_record=outline_record,
            commit_payload=commit_payload,
            chapter_contract=chapter_contract,
            review_contract=review_contract,
        )
        row["classification"] = _classify(row)
        row["repair_required"] = row["classification"] != "native"
        chapters.append(row)
        if row["chapter_contract"] == "missing" or row["review_contract"] == "missing":
            contract_anomalies.append(
                {
                    "chapter": chapter,
                    "missing": [
                        name
                        for name in ("chapter_contract", "review_contract")
                        if row[name] == "missing"
                    ],
                }
            )

    recommended_actions: list[str] = []
    if any(row["repair_required"] for row in chapters):
        recommended_actions.append("run_story_repair_rebuild_from_accepted_ledger")
    if _stale_context_snapshots(project_root):
        recommended_actions.append("archive_legacy_context_snapshots")

    return {
        "chapters": chapters,
        "state_anomalies": _state_anomalies(state),
        "stale_files": _stale_context_snapshots(project_root),
        "contract_anomalies": contract_anomalies,
        "numbering_anomalies": _numbering_anomalies(project_root, state),
        "recommended_actions": recommended_actions,
    }
