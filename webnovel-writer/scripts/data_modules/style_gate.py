#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from chapter_paths import find_chapter_file


RULES_BEGIN = "<!-- STYLE_GATE_RULES:BEGIN -->"
RULES_END = "<!-- STYLE_GATE_RULES:END -->"


def _plugin_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _polish_guide_path() -> Path:
    return _plugin_root() / "skills" / "webnovel-write" / "references" / "polish-guide.md"


def _load_style_gate_rules() -> dict[str, Any]:
    path = _polish_guide_path()
    text = path.read_text(encoding="utf-8")
    start = text.find(RULES_BEGIN)
    end = text.find(RULES_END)
    if start < 0 or end < 0 or end <= start:
        raise ValueError(f"style gate rules block missing in {path}")
    block = text[start + len(RULES_BEGIN):end]
    match = re.search(r"```json\s*(\{.*?\})\s*```", block, flags=re.DOTALL)
    if not match:
        raise ValueError(f"style gate rules JSON block missing in {path}")
    return json.loads(match.group(1))


def _is_chapter_heading(line: str) -> bool:
    return bool(
        re.match(
            r"^\s*#{1,6}\s*第\s*[0-9零〇一二两三四五六七八九十百]+\s*章\b",
            line,
        )
    )


def _issue(
    *,
    rule_id: str,
    rule: dict[str, Any],
    line_no: int,
    evidence: str,
) -> dict[str, Any]:
    description = str(rule.get("description") or rule_id)
    fix_hint = str(rule.get("fix_hint") or "改写该句，保留事实，去掉模板痕迹。")
    return {
        "rule_id": rule_id,
        "severity": str(rule.get("severity") or "critical"),
        "category": str(rule.get("category") or "ai_flavor"),
        "location": f"line {line_no}",
        "description": description,
        "evidence": evidence.strip()[:220],
        "fix_hint": fix_hint,
        "blocking": bool(rule.get("blocking", True)),
    }


def _scan_pattern_rule(
    *,
    rule_id: str,
    rule: dict[str, Any],
    line: str,
    line_no: int,
) -> list[dict[str, Any]]:
    if rule.get("skip_chapter_heading") and _is_chapter_heading(line):
        return []
    pattern = str(rule.get("pattern") or "")
    if not pattern:
        return []
    if re.search(pattern, line):
        return [_issue(rule_id=rule_id, rule=rule, line_no=line_no, evidence=line)]
    return []


def _scan_literal_any_rule(
    *,
    rule_id: str,
    rule: dict[str, Any],
    line: str,
    line_no: int,
) -> list[dict[str, Any]]:
    if rule.get("skip_chapter_heading") and _is_chapter_heading(line):
        return []
    phrases = [str(item) for item in rule.get("phrases", []) if str(item)]
    hits = [phrase for phrase in phrases if phrase in line]
    if not hits:
        return []
    issue = _issue(rule_id=rule_id, rule=rule, line_no=line_no, evidence=line)
    issue["matched"] = hits
    return [issue]


def run_style_gate_text(text: str, *, chapter: int | None = None) -> dict[str, Any]:
    rules_payload = _load_style_gate_rules()
    rules = dict(rules_payload.get("rules") or {})
    issues: list[dict[str, Any]] = []

    for line_no, line in enumerate(text.splitlines(), start=1):
        for rule_id, rule in rules.items():
            if not isinstance(rule, dict):
                continue
            rule_type = str(rule.get("type") or "regex")
            if rule_type == "literal_any":
                issues.extend(
                    _scan_literal_any_rule(
                        rule_id=rule_id,
                        rule=rule,
                        line=line,
                        line_no=line_no,
                    )
                )
            else:
                issues.extend(
                    _scan_pattern_rule(
                        rule_id=rule_id,
                        rule=rule,
                        line=line,
                        line_no=line_no,
                    )
                )

    blocking_count = sum(1 for issue in issues if issue.get("blocking"))
    return {
        "schema_version": "style-gate/v1",
        "chapter": chapter,
        "status": "fail" if blocking_count else "pass",
        "blocking_count": blocking_count,
        "issues": issues,
    }


def run_style_gate_file(path: Path, *, chapter: int | None = None) -> dict[str, Any]:
    result = run_style_gate_text(path.read_text(encoding="utf-8"), chapter=chapter)
    result["path"] = str(path)
    return result


def run_style_gate_project(
    project_root: Path,
    chapter: int,
    *,
    require_body: bool = True,
) -> dict[str, Any]:
    path = find_chapter_file(Path(project_root), chapter)
    if not path or not path.is_file():
        if not require_body:
            return {
                "schema_version": "style-gate/v1",
                "chapter": chapter,
                "status": "pass",
                "blocking_count": 0,
                "issues": [],
                "path": "",
                "skipped": "chapter_body_missing",
            }
        return {
            "schema_version": "style-gate/v1",
            "chapter": chapter,
            "status": "fail",
            "blocking_count": 1,
            "issues": [
                {
                    "rule_id": "missing_chapter_body",
                    "severity": "critical",
                    "category": "continuity",
                    "location": "chapter file",
                    "description": "未找到当前章节正文，无法执行文风门禁。",
                    "evidence": f"chapter={chapter}",
                    "fix_hint": "先生成或恢复当前章节正文文件，再重新执行 style-gate。",
                    "blocking": True,
                }
            ],
            "path": "",
        }
    return run_style_gate_file(path, chapter=chapter)
