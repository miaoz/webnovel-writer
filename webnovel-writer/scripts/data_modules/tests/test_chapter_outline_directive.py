#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from chapter_outline_loader import load_chapter_execution_directive
from chapter_paths import global_from_volume_chapter, volume_chapter_from_global, volume_num_for_chapter


def test_load_chapter_execution_directive_from_volume_outline(tmp_path):
    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir()
    (tmp_path / ".webnovel").mkdir()
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps({"progress": {"volumes_planned": [{"volume": 1, "chapters_range": "1-50"}]}}),
        encoding="utf-8",
    )
    (outline_dir / "第1卷-详细大纲.md").write_text(
        "\n".join(
            [
                "### 第一章：债从天降",
                "- 目标：搞清楚借据条款的荒谬",
                "- 阻力：杂役不能随意离开宗门",
                "- 代价：暴露自己懂账",
                "- 时间锚点：D-Day 清晨",
                "- 章内跨度：一炷香",
                "- 倒计时状态：三日内还债",
                "- Strand：债务调查",
                "- 反派层级：小反派",
                "- 关键实体：陆鸣、借据、利息",
                "- CBN：醒来发现债务",
                "- CPNs：检查借据；发现复利陷阱",
                "- CEN：决定去井边打听",
                "- 必须覆盖节点：借据金额；复利算法",
                "- 本章禁区：不得离开宗门；不得提前摊牌",
                "- 章末未闭合问题：谁改了借据？",
                "- 钩子类型：信息钩",
                "- 钩子强度：中",
                "",
                "### 第二章：井边口风",
                "- 目标：打听债主来历",
            ]
        ),
        encoding="utf-8",
    )

    directive = load_chapter_execution_directive(tmp_path, 1)

    assert directive["goal"] == "搞清楚借据条款的荒谬"
    assert directive["time_anchor"] == "D-Day 清晨"
    assert directive["chapter_span"] == "一炷香"
    assert directive["countdown"] == "三日内还债"
    assert directive["cpns"] == ["检查借据", "发现复利陷阱"]
    assert "不得离开宗门" in directive["forbidden_zones"]
    assert "借据" in directive["key_entities"]
    assert directive["chapter_end_open_question"] == "谁改了借据？"


def test_volume_global_conversion_prefers_outline_ranges_over_stale_state(tmp_path):
    (tmp_path / ".webnovel").mkdir()
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps(
            {
                "progress": {
                    "volumes_planned": [
                        {"volume": 1, "chapters_range": "1-50"},
                        {"volume": 2, "chapters_range": "1-50"},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir()
    (outline_dir / "第1卷-详细大纲.md").write_text(
        "> 卷范围: 第1-48章\n\n### 第 48 章：卷一尾声\n- 目标: 收束",
        encoding="utf-8",
    )
    (outline_dir / "第2卷-详细大纲.md").write_text(
        "> 卷范围: 第1-50章\n\n### 第 1 章：卷二开局\n- 目标: 开局",
        encoding="utf-8",
    )

    assert global_from_volume_chapter(tmp_path, 1, 33) == 33
    assert global_from_volume_chapter(tmp_path, 2, 1) == 49
    assert volume_chapter_from_global(tmp_path, 49) == (2, 1)
    assert volume_num_for_chapter(49, project_root=tmp_path) == 2
