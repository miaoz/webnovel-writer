#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

try:
    from chapter_paths import global_from_volume_chapter
except ImportError:  # pragma: no cover
    from scripts.chapter_paths import global_from_volume_chapter


_OUTLINE_FILE_RE = re.compile(r"第\s*(?P<volume>\d+)\s*卷.*详细大纲\.md$")
_RANGE_RE = re.compile(r"卷范围\s*[：:]\s*第\s*(?P<start>\d+)\s*-\s*(?P<end>\d+)\s*章")
_HEADING_RE = re.compile(
    r"^###\s*第\s*(?P<chapter>\d+)\s*章[：:]\s*(?P<title>.+?)\s*$",
    re.MULTILINE,
)
_FIELD_RE = re.compile(r"^\s*[-*]\s*(?P<label>[^：:]+)[：:]\s*(?P<value>.*?)\s*$")


@dataclass(frozen=True)
class OutlineChapterRecord:
    volume: int
    chapter_in_volume: int
    global_chapter: int
    title: str
    goal: str
    time_anchor: str
    chapter_span: str
    hook: str
    end_open_question: str
    key_entities: list[str]
    source_file: str
    outline_hash: str
    raw_section: str


def _volume_from_path(path: Path) -> int | None:
    match = _OUTLINE_FILE_RE.search(path.name)
    if not match:
        return None
    return int(match.group("volume"))


def _range_count(text: str) -> int | None:
    match = _RANGE_RE.search(text)
    if not match:
        return None
    start = int(match.group("start"))
    end = int(match.group("end"))
    if start <= 0 or end < start:
        return None
    return end - start + 1


def _outline_offsets(files: list[tuple[int, Path, str]]) -> dict[int, int]:
    offsets: dict[int, int] = {}
    running = 0
    for volume, _path, text in sorted(files, key=lambda item: item[0]):
        offsets[volume] = running
        running += _range_count(text) or 0
    return offsets


def _sections(text: str) -> list[tuple[int, str, str]]:
    matches = list(_HEADING_RE.finditer(text))
    sections: list[tuple[int, str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        raw_section = text[match.start():end].strip()
        sections.append((int(match.group("chapter")), match.group("title").strip(), raw_section))
    return sections


def _field_map(raw_section: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current_label = ""
    for line in raw_section.splitlines():
        match = _FIELD_RE.match(line)
        if match:
            current_label = match.group("label").strip()
            fields.setdefault(current_label, match.group("value").strip())
            continue
        if current_label and line.strip() and not line.lstrip().startswith("#"):
            fields[current_label] = f"{fields[current_label]} {line.strip()}".strip()
    return fields


def _split_entities(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[、,，；;|]+", value or "") if item.strip()]


def _source_file(project_root: Path, path: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def load_outline_catalog(project_root: Path) -> list[OutlineChapterRecord]:
    project_root = Path(project_root)
    outline_dir = project_root / "大纲"
    if not outline_dir.is_dir():
        return []

    files: list[tuple[int, Path, str]] = []
    for path in sorted(outline_dir.glob("第*卷*详细大纲.md")):
        volume = _volume_from_path(path)
        if volume is None:
            continue
        files.append((volume, path, path.read_text(encoding="utf-8")))

    outline_offsets = _outline_offsets(files)
    records: list[OutlineChapterRecord] = []
    for volume, path, text in files:
        for chapter, title, raw_section in _sections(text):
            fields = _field_map(raw_section)
            global_chapter = outline_offsets.get(volume, 0) + chapter
            if not outline_offsets:
                global_chapter = global_from_volume_chapter(project_root, volume, chapter)
            records.append(
                OutlineChapterRecord(
                    volume=volume,
                    chapter_in_volume=chapter,
                    global_chapter=global_chapter,
                    title=title,
                    goal=fields.get("目标", fields.get("本章目标", "")),
                    time_anchor=fields.get("时间锚点", fields.get("时间", "")),
                    chapter_span=fields.get("章内时间跨度", fields.get("章内跨度", "")),
                    hook=fields.get("钩子", fields.get("钩子类型", "")),
                    end_open_question=fields.get("章末未闭合问题", fields.get("章末问题", "")),
                    key_entities=_split_entities(fields.get("关键实体", fields.get("涉及实体", ""))),
                    source_file=_source_file(project_root, path),
                    outline_hash=hashlib.sha256(raw_section.encode("utf-8")).hexdigest(),
                    raw_section=raw_section,
                )
            )
    return sorted(records, key=lambda record: record.global_chapter)

