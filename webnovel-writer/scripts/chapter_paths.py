#!/usr/bin/env python3
"""
Chapter file path helpers.

This project supports two chapter numbering modes:

1) **Global continuous** (legacy): chapters numbered 1..N across all volumes.
   Volume number = (chapter_num - 1) // chapters_per_volume + 1.

2) **Per-volume** (current default): each volume restarts at chapter 1.
   Volume number is explicit; global numbers are derived from state.json
   ``volumes_planned[].chapters_range`` by summing prior volume lengths.

Prefer the ``(volume_num, chapter_in_volume)`` pair for new code.
Legacy callers that pass only ``chapter_num`` will resolve via
``state.json`` when available, falling back to the old math-based formula.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional


_CHAPTER_NUM_RE = re.compile(r"第(?P<num>\d+)章")
_OUTLINE_HEADING_RE = re.compile(
    r"^#{1,6}\s*第\s*(?P<num>\d+)\s*章[：:]\s*(?P<title>.+?)\s*$", re.MULTILINE
)
_SPLIT_OUTLINE_FILENAME_RE = re.compile(
    r"^第0*(?P<num>\d+)章[-—_ ]+(?P<title>.+?)\.md$"
)
_OUTLINE_VOLUME_FILE_RE = re.compile(r"第\s*(?P<volume>\d+)\s*卷.*详细大纲\.md$")
_OUTLINE_RANGE_RE = re.compile(r"卷范围\s*[：:]\s*第\s*(?P<start>\d+)\s*-\s*(?P<end>\d+)\s*章")


# ---------------------------------------------------------------------------
#  State.json helpers
# ---------------------------------------------------------------------------

def _load_state(project_root: Path) -> dict | None:
    state_path = project_root / ".webnovel" / "state.json"
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_volumes_planned(project_root: Path) -> list[dict]:
    """Return ``volumes_planned`` list from state.json, or []."""
    state = _load_state(project_root)
    if not state:
        return []
    progress = state.get("progress")
    if not isinstance(progress, dict):
        return []
    vp = progress.get("volumes_planned")
    return vp if isinstance(vp, list) else []


def _parse_chapter_count(chapters_range: str) -> int:
    """Parse 'start-end' range string and return the count of chapters.

    Examples
    --------
    '1-50'  -> 50
    '1-46'  -> 46
    '10-20' -> 11
    """
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(chapters_range or ""))
    if not m:
        return 0
    start, end = int(m.group(1)), int(m.group(2))
    return max(0, end - start + 1)


def _parse_outline_chapter_count(text: str) -> int:
    match = _OUTLINE_RANGE_RE.search(text or "")
    if match:
        start, end = int(match.group("start")), int(match.group("end"))
        return max(0, end - start + 1)

    chapters = [
        int(item)
        for item in re.findall(r"^###\s*第\s*(\d+)\s*章[：:]", text or "", flags=re.MULTILINE)
    ]
    return max(chapters or [0])


def _load_outline_volume_counts(project_root: Path) -> dict[int, int]:
    outline_dir = project_root / "大纲"
    if not outline_dir.is_dir():
        return {}
    counts: dict[int, int] = {}
    for path in sorted(outline_dir.glob("第*卷*详细大纲.md")):
        match = _OUTLINE_VOLUME_FILE_RE.search(path.name)
        if not match:
            continue
        volume = int(match.group("volume"))
        try:
            count = _parse_outline_chapter_count(path.read_text(encoding="utf-8"))
        except OSError:
            count = 0
        if count > 0:
            counts[volume] = count
    return counts


def _compute_global_offsets(project_root: Path) -> dict[int, int]:
    """Return ``{volume_num: global_offset_before_this_volume}``.

    The offset is the sum of chapter counts of all *preceding* volumes.
    Volume 1 always has offset 0.
    """
    outline_counts = _load_outline_volume_counts(project_root)
    if outline_counts:
        offsets: dict[int, int] = {}
        running = 0
        for volume in sorted(outline_counts):
            offsets[volume] = running
            running += outline_counts[volume]
        return offsets

    volumes = _load_volumes_planned(project_root)
    offsets: dict[int, int] = {}
    running = 0
    for item in volumes:
        if not isinstance(item, dict):
            continue
        vol = item.get("volume")
        if not isinstance(vol, int) or vol < 1:
            continue
        offsets[vol] = running
        running += _parse_chapter_count(item.get("chapters_range", ""))
    return offsets


def _current_volume(project_root: Path) -> int | None:
    state = _load_state(project_root)
    if not state:
        return None
    progress = state.get("progress")
    if not isinstance(progress, dict):
        return None
    cv = progress.get("current_volume")
    return cv if isinstance(cv, int) and cv >= 1 else None


# ---------------------------------------------------------------------------
#  Numbering conversion (per-volume <-> global)
# ---------------------------------------------------------------------------

def global_from_volume_chapter(
    project_root: Path, volume_num: int, chapter_in_volume: int
) -> int:
    """Convert a per-volume chapter number to a global chapter number.

    Reads ``volumes_planned`` from state.json to compute the offset.

    Returns:
        Global chapter number, or ``chapter_in_volume`` unchanged if
        state.json is unavailable (fallback: assume V1).
    """
    offsets = _compute_global_offsets(project_root)
    offset = offsets.get(volume_num, 0)
    return offset + chapter_in_volume


def volume_chapter_from_global(
    project_root: Path, global_chapter_num: int
) -> tuple[int, int]:
    """Convert a global chapter number to ``(volume_num, chapter_in_volume)``.

    Returns:
        ``(1, global_chapter_num)`` if state.json is unavailable.
    """
    offsets = _compute_global_offsets(project_root)
    volumes = sorted(offsets.keys())
    for vol in reversed(volumes):
        offset = offsets[vol]
        if global_chapter_num > offset:
            return vol, global_chapter_num - offset
    # Fallback: everything is in volume 1
    return 1, global_chapter_num


# ---------------------------------------------------------------------------
#  Volume-number resolution
# ---------------------------------------------------------------------------

def volume_num_for_chapter(
    chapter_num: int,
    *,
    chapters_per_volume: int = 50,
    project_root: Path | None = None,
) -> int:
    """Resolve which volume *chapter_num* belongs to.

    When *project_root* is provided and state.json contains
    ``volumes_planned``, the per-volume chapter counts are consulted.
    Otherwise falls back to the legacy formula
    ``(chapter_num - 1) // chapters_per_volume + 1``.

    .. note::
        If the project uses per-volume numbering (every volume starts at
        chapter 1), this function requires *project_root* to disambiguate.
        Without it the legacy formula will produce wrong results for any
        volume beyond the first.
    """
    if chapter_num <= 0:
        raise ValueError("chapter_num must be >= 1")

    if project_root is not None:
        offsets = _compute_global_offsets(project_root)
        if offsets:
            # Walk volumes in descending order to find the highest offset
            # that is strictly less than chapter_num.
            for vol in sorted(offsets.keys(), reverse=True):
                if chapter_num > offsets[vol]:
                    return vol
            return 1

    return (chapter_num - 1) // chapters_per_volume + 1


# ---------------------------------------------------------------------------
#  Chapter-num extraction
# ---------------------------------------------------------------------------

def extract_chapter_num_from_filename(filename: str) -> Optional[int]:
    m = _CHAPTER_NUM_RE.search(filename)
    if not m:
        return None
    try:
        return int(m.group("num"))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
#  Title helpers
# ---------------------------------------------------------------------------

def _safe_title_for_filename(title: str) -> str:
    cleaned = title.strip()
    if not cleaned:
        return ""

    try:
        from security_utils import sanitize_filename
    except ImportError:  # pragma: no cover
        from scripts.security_utils import sanitize_filename

    safe_title = sanitize_filename(cleaned, max_length=60)
    return "" if safe_title == "unnamed_entity" else safe_title


def _extract_title_from_outline_text(outline_text: str, chapter_num: int) -> str:
    for match in _OUTLINE_HEADING_RE.finditer(outline_text):
        if int(match.group("num")) != chapter_num:
            continue
        return _safe_title_for_filename(match.group("title"))
    return ""


def _extract_title_from_split_outline_filename(
    outline_dir: Path, chapter_num: int
) -> str:
    patterns = [
        f"第{chapter_num}章*.md",
        f"第{chapter_num:02d}章*.md",
        f"第{chapter_num:03d}章*.md",
        f"第{chapter_num:04d}章*.md",
    ]
    for pattern in patterns:
        for path in sorted(outline_dir.glob(pattern)):
            match = _SPLIT_OUTLINE_FILENAME_RE.match(path.name)
            if not match:
                continue
            if int(match.group("num")) != chapter_num:
                continue
            title = _safe_title_for_filename(match.group("title"))
            if title:
                return title
    return ""


def extract_chapter_title(project_root: Path, chapter_num: int) -> str:
    """Extract chapter title from the detailed outline.

    *chapter_num* is interpreted as **volume-local** when the project
    state has a ``current_volume`` and per-volume ``volumes_planned``.
    """
    try:
        from chapter_outline_loader import load_chapter_outline
    except ImportError:  # pragma: no cover
        from scripts.chapter_outline_loader import load_chapter_outline

    outline_text = load_chapter_outline(project_root, chapter_num, max_chars=None)
    if not outline_text.startswith("⚠️"):
        title = _extract_title_from_outline_text(outline_text, chapter_num)
        if title:
            return title

    outline_dir = project_root / "大纲"
    if outline_dir.exists():
        return _extract_title_from_split_outline_filename(outline_dir, chapter_num)
    return ""


# ---------------------------------------------------------------------------
#  File-name builders
# ---------------------------------------------------------------------------

def _build_chapter_filename(
    project_root: Path,
    chapter_num: int,
    *,
    use_volume_layout: bool,
    volume_num: int | None = None,
) -> str:
    """Build a chapter filename.

    When *use_volume_layout* and *volume_num* are both set, the three-digit
    pad is used and chapter_num is treated as volume-local.
    """
    if use_volume_layout and volume_num is not None:
        padded = f"{chapter_num:03d}"
    elif use_volume_layout:
        padded = f"{chapter_num:03d}"
    else:
        padded = f"{chapter_num:04d}"

    title = extract_chapter_title(project_root, chapter_num)
    if title:
        return f"第{padded}章-{title}.md"
    return f"第{padded}章.md"


# ---------------------------------------------------------------------------
#  File finder  (public API)
# ---------------------------------------------------------------------------

def find_chapter_file(
    project_root: Path,
    chapter_num: int,
    *,
    volume_num: int | None = None,
) -> Optional[Path]:
    """Find an existing chapter file for *chapter_num*.

    When *volume_num* is given, *chapter_num* is treated as volume-local
    and only ``正文/第{volume_num}卷/`` is searched.

    When *volume_num* is not given, the legacy behaviour applies:
    - flat layout: ``正文/第NNNN章*.md``
    - volume layout: ``正文/第{auto_vol}卷/第NNN章*.md``
      where *auto_vol* is resolved via :func:`volume_num_for_chapter`.

    Returns the first match (stable sorted order) or ``None``.
    """
    chapters_dir = project_root / "正文"
    if not chapters_dir.exists():
        return None

    # --- explicit volume: only search that volume directory ---------------
    if volume_num is not None:
        vol_dir = chapters_dir / f"第{volume_num}卷"
        if not vol_dir.exists():
            return None
        candidates = sorted(
            vol_dir.glob(f"第{chapter_num:03d}章*.md")
        ) + sorted(vol_dir.glob(f"第{chapter_num:04d}章*.md"))
        for c in candidates:
            if c.is_file():
                return c
        return None

    # --- legacy behaviour -------------------------------------------------
    legacy = chapters_dir / f"第{chapter_num:04d}章.md"
    if legacy.exists():
        return legacy

    auto_vol = volume_num_for_chapter(chapter_num, project_root=project_root)
    vol_dir = chapters_dir / f"第{auto_vol}卷"
    if vol_dir.exists():
        candidates = sorted(
            vol_dir.glob(f"第{chapter_num:03d}章*.md")
        ) + sorted(vol_dir.glob(f"第{chapter_num:04d}章*.md"))
        for c in candidates:
            if c.is_file():
                return c

    # Fallback: search anywhere under 正文/
    candidates = sorted(
        chapters_dir.rglob(f"第{chapter_num:03d}章*.md")
    ) + sorted(chapters_dir.rglob(f"第{chapter_num:04d}章*.md"))
    for c in candidates:
        if c.is_file():
            return c

    return None


def default_chapter_draft_path(
    project_root: Path,
    chapter_num: int,
    *,
    use_volume_layout: bool = False,
    volume_num: int | None = None,
) -> Path:
    """Preferred draft path when creating a new chapter file.

    Args:
        project_root: Project root directory.
        chapter_num: Chapter number.  When *volume_num* is set this is
            the **volume-local** chapter number (e.g. 5 for "Vol 2 Ch 5").
        use_volume_layout: If True, places the file under
            ``正文/第N卷/第NNN章-标题.md``.
        volume_num: Explicit volume number.  Required for per-volume
            numbering; when omitted the legacy auto-detection is used.
    """
    if use_volume_layout:
        vol = volume_num or volume_num_for_chapter(
            chapter_num, project_root=project_root
        )
        vol_dir = project_root / "正文" / f"第{vol}卷"
        return vol_dir / _build_chapter_filename(
            project_root,
            chapter_num,
            use_volume_layout=True,
            volume_num=vol,
        )
    else:
        return project_root / "正文" / _build_chapter_filename(
            project_root, chapter_num, use_volume_layout=False
        )
