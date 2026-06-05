#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from data_modules.style_gate import run_style_gate_text


def test_style_gate_flags_meta_chapter_reference_and_cliche():
    text = (
        "# 第7章：还有高手\n\n"
        "这笔钱已经不是第 4 章时那种\"输掉就万劫不复\"的全部身家。\n"
    )

    result = run_style_gate_text(text, chapter=7)

    assert result["status"] == "fail"
    rule_ids = {issue["rule_id"] for issue in result["issues"]}
    assert "meta_chapter_reference" in rule_ids
    assert "cliche_label" in rule_ids
    assert result["blocking_count"] >= 2


def test_style_gate_allows_chapter_heading_but_blocks_body_chapter_reference():
    text = "# 第7章：还有高手\n\n顾宜看了一眼余额。\n"

    result = run_style_gate_text(text, chapter=7)

    assert result["status"] == "pass"
    assert result["blocking_count"] == 0


def test_style_gate_flags_dash_and_negation_contrast():
    text = "他停了一下——这不是迟疑，是标记。\n"

    result = run_style_gate_text(text, chapter=7)

    assert result["status"] == "fail"
    rule_ids = {issue["rule_id"] for issue in result["issues"]}
    assert "dash" in rule_ids
    assert "negation_contrast" in rule_ids


def test_style_gate_can_scan_chapter_file(tmp_path):
    chapter_file = tmp_path / "正文" / "第1卷" / "第007章-还有高手.md"
    chapter_file.parent.mkdir(parents=True)
    chapter_file.write_text("# 第7章：还有高手\n\n顾宜把鼠标移开。\n", encoding="utf-8")

    result = run_style_gate_text(chapter_file.read_text(encoding="utf-8"), chapter=7)

    assert result["status"] == "pass"
