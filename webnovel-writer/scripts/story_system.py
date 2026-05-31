#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from runtime_compat import enable_windows_utf8_stdio

from data_modules.runtime_contract_builder import RuntimeContractBuilder
from data_modules.story_contracts import persist_runtime_contracts, persist_story_seed
from data_modules.story_system_engine import StorySystemEngine, StorySystemRoutingError, is_placeholder_query
from chapter_paths import global_from_volume_chapter
from chapter_outline_loader import load_chapter_execution_directive


def _default_csv_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "references" / "csv"


def _resolve_project_root(raw: str) -> Path:
    if raw:
        return Path(raw).expanduser().resolve()

    from project_locator import resolve_project_root

    return resolve_project_root()


def _render_output(format_name: str, contract: dict) -> str:
    if format_name == "json":
        return json.dumps(contract, ensure_ascii=False, indent=2)
    if format_name == "markdown":
        lines = [
            "# Story System",
            f"- 题材：{contract['master_setting']['route'].get('primary_genre', '')}",
        ]
        if contract.get("chapter_brief"):
            lines.append(
                f"- 章节焦点：{contract['chapter_brief']['override_allowed'].get('chapter_focus', '')}"
            )
        return "\n".join(lines)
    return json.dumps(
        {
            "master": contract["master_setting"].get("route", {}),
            "chapter": (contract.get("chapter_brief") or {}).get("override_allowed", {}),
            "anti_patterns": [row.get("text", "") for row in contract.get("anti_patterns", [])],
        },
        ensure_ascii=False,
        indent=2,
    )


def _state_genre(project_root: Path) -> str:
    state_path = project_root / ".webnovel" / "state.json"
    if not state_path.is_file():
        return ""
    try:
        state: dict[str, Any] = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    for key in ("project_info", "project"):
        genre = str(((state.get(key) or {}).get("genre")) or "").strip()
        if genre:
            return genre
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Story system seed generator")
    parser.add_argument("query", help="题材 / 需求描述")
    parser.add_argument("--project-root", default="")
    parser.add_argument("--genre", default="")
    parser.add_argument("--volume", type=int, default=0)
    parser.add_argument("--chapter", type=int, default=0)
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--refresh-master", action="store_true")
    parser.add_argument("--emit-runtime-contracts", action="store_true")
    parser.add_argument("--csv-dir", default="")
    parser.add_argument("--format", choices=["json", "markdown", "both"], default="json")

    args = parser.parse_args()
    project_root = _resolve_project_root(args.project_root)
    csv_dir = Path(args.csv_dir).expanduser().resolve() if args.csv_dir else _default_csv_dir()
    requested_chapter = int(args.chapter or 0)
    volume_num = int(args.volume or 0) or None
    global_chapter = (
        global_from_volume_chapter(project_root, volume_num, requested_chapter)
        if volume_num and requested_chapter
        else requested_chapter
    )
    if is_placeholder_query(args.query):
        print(
            "warning: story-system query appears to be a placeholder; parse the real chapter goal from the outline.",
            file=sys.stderr,
        )
    chapter_directive = (
        load_chapter_execution_directive(project_root, requested_chapter, volume_num=volume_num)
        if requested_chapter
        else {}
    )
    engine = StorySystemEngine(csv_dir=csv_dir)
    genre = str(args.genre or "").strip() or _state_genre(project_root)
    try:
        contract = engine.build(
            query=args.query,
            genre=genre or None,
            chapter=global_chapter or None,
            chapter_directive=chapter_directive,
        )
    except StorySystemRoutingError as exc:
        parser.exit(2, f"error: {exc}\n")

    if args.persist:
        should_refresh_master = bool(
            args.refresh_master
            or not global_chapter
            or not (project_root / ".story-system" / "MASTER_SETTING.json").is_file()
        )
        persist_story_seed(
            project_root=project_root,
            master_payload=contract["master_setting"],
            chapter_payload=contract.get("chapter_brief"),
            anti_patterns=contract["anti_patterns"],
            refresh_master=should_refresh_master,
        )
    if args.emit_runtime_contracts:
        if not global_chapter:
            raise ValueError("--emit-runtime-contracts 需要 --chapter")
        volume_brief, review_contract = RuntimeContractBuilder(project_root).build_for_chapter(
            global_chapter,
            volume_num=volume_num,
            chapter_in_volume=requested_chapter if volume_num else None,
        )
        persist_runtime_contracts(project_root, global_chapter, volume_brief, review_contract, volume=volume_num)

    print(_render_output(args.format, contract))


if __name__ == "__main__":
    if sys.platform == "win32":
        enable_windows_utf8_stdio()
    main()
