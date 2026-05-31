#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from chapter_outline_loader import load_chapter_outline
    from chapter_paths import volume_num_for_chapter
except ImportError:  # pragma: no cover
    from scripts.chapter_outline_loader import load_chapter_outline
    from scripts.chapter_paths import volume_num_for_chapter

from data_modules.story_contracts import StoryContractPaths, read_json_if_exists
from data_modules.story_repair.outline_catalog import load_outline_catalog


@dataclass(frozen=True)
class PrewriteGateResult:
    chapter: int
    ready: bool
    blocking_reasons: list[str]
    warnings: list[str]
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter": self.chapter,
            "ready": self.ready,
            "blocking_reasons": list(self.blocking_reasons),
            "warnings": list(self.warnings),
            "provenance": dict(self.provenance),
        }


def _read_state(project_root: Path) -> dict[str, Any]:
    path = project_root / ".webnovel" / "state.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


def _latest_accepted_commit(paths: StoryContractPaths, before_or_at: int) -> tuple[int, dict[str, Any] | None]:
    for chapter in range(before_or_at, 0, -1):
        payload = read_json_if_exists(paths.commit_json(chapter))
        if payload and (payload.get("meta") or {}).get("status") == "accepted":
            return chapter, payload
    return 0, None


def _outline_record(project_root: Path, chapter: int):
    for record in load_outline_catalog(project_root):
        if record.global_chapter == chapter:
            return record
    return None


def _contract_goal(chapter_contract: dict[str, Any]) -> str:
    candidates = [
        ((chapter_contract.get("chapter_brief") or {}).get("chapter_directive") or {}).get("goal"),
        (chapter_contract.get("chapter_directive") or {}).get("goal"),
        (chapter_contract.get("override_allowed") or {}).get("chapter_focus"),
    ]
    for value in candidates:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _contract_outline_hash(chapter_contract: dict[str, Any]) -> str:
    for source in (
        chapter_contract.get("provenance") or {},
        chapter_contract.get("source") or {},
        chapter_contract.get("meta") or {},
    ):
        value = str(source.get("outline_hash") or source.get("source_outline_hash") or "").strip()
        if value:
            return value
    return ""


def _location_lag(state: dict[str, Any], latest_commit_chapter: int) -> bool:
    location = ((state.get("protagonist_state") or {}).get("location") or {})
    if not isinstance(location, dict):
        return False
    try:
        last_location = int(location.get("last_chapter") or 0)
    except (TypeError, ValueError):
        last_location = 0
    return bool(latest_commit_chapter and last_location and latest_commit_chapter - last_location > 1)


def run_prewrite_gate(project_root: Path, chapter: int, *, rewrite: bool = False) -> PrewriteGateResult:
    project_root = Path(project_root)
    paths = StoryContractPaths.from_project_root(project_root)
    blocking: list[str] = []
    warnings: list[str] = []

    master = read_json_if_exists(paths.master_json)
    chapter_contract = read_json_if_exists(paths.chapter_json(chapter))
    review_contract = read_json_if_exists(paths.review_json(chapter))
    volume = volume_num_for_chapter(chapter, project_root=project_root)
    volume_contract = read_json_if_exists(paths.volume_json(volume))
    target_commit = read_json_if_exists(paths.commit_json(chapter))
    previous_chapter, previous_commit = _latest_accepted_commit(paths, chapter - 1)
    state = _read_state(project_root)

    if not master:
        blocking.append("missing_master_contract")
    if not chapter_contract:
        blocking.append("missing_chapter_contract")
    if not review_contract:
        blocking.append("missing_review_contract")
    if not volume_contract:
        blocking.append("missing_volume_contract")
    if target_commit and not rewrite:
        blocking.append("target_commit_exists")
    if chapter > 1 and previous_chapter != chapter - 1:
        blocking.append("previous_accepted_commit_not_latest")
    if _location_lag(state, previous_chapter):
        blocking.append("state_location_lag")

    outline_text = load_chapter_outline(project_root, chapter, max_chars=None)
    outline_record = _outline_record(project_root, chapter)
    if outline_text.startswith("⚠️") or outline_record is None:
        blocking.append("outline_section_missing")
    elif chapter_contract:
        expected_hash = _contract_outline_hash(chapter_contract)
        if expected_hash and expected_hash != outline_record.outline_hash:
            blocking.append("outline_hash_mismatch")

    if chapter_contract and not _contract_goal(chapter_contract):
        blocking.append("missing_chapter_goal")

    commit_mode = ((previous_commit or {}).get("provenance") or {}).get("commit_mode", "")
    if commit_mode == "repair_backfill":
        warnings.append("previous_commit_is_repair_backfill_not_native_write_proof")

    provenance = {
        "previous_accepted_commit": previous_chapter,
        "previous_commit_mode": commit_mode,
        "volume": volume,
        "outline_sha256": outline_record.outline_hash if outline_record else hashlib.sha256(outline_text.encode("utf-8")).hexdigest(),
        "target_commit_exists": bool(target_commit),
    }
    return PrewriteGateResult(
        chapter=chapter,
        ready=not blocking,
        blocking_reasons=blocking,
        warnings=warnings,
        provenance=provenance,
    )
