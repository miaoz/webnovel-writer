#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import json

from data_modules.story_repair.outline_catalog import load_outline_catalog


def test_load_outline_catalog_parses_current_detailed_outline_format(tmp_path):
    (tmp_path / ".webnovel").mkdir()
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps({"progress": {"volumes_planned": [{"volume": 1, "chapters_range": "1-48"}]}}),
        encoding="utf-8",
    )
    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir()
    outline_text = "\n".join(
        [
            "# 第 1 卷 详细大纲：迷因猎手",
            "",
            "> 卷范围: 第1-48章（2024.3.12 ~ 2024.5.13）",
            "",
            "### 第 33 章：盘点第一桶金",
            "",
            "- 目标: 盘点第一桶金，把资产结构讲清楚",
            "- 时间锚点: 2024年5月4日",
            "- 章内时间跨度: 1天",
            "- 关键实体: 顾宜、杜雨薇、BOME",
            "- 章末未闭合问题: 钱到了，下一步怎么安排？",
            "- 钩子: 出金群里真正赚钱的人都沉默了",
            "",
            "### 第 34 章：赚钱的都在出金群",
            "",
            "- 目标: 继续出金线",
            "- 时间锚点: 2024年5月5日",
        ]
    )
    (outline_dir / "第1卷-详细大纲.md").write_text(outline_text, encoding="utf-8")

    records = load_outline_catalog(tmp_path)

    record = records[0]
    assert record.volume == 1
    assert record.chapter_in_volume == 33
    assert record.global_chapter == 33
    assert record.title == "盘点第一桶金"
    assert record.goal == "盘点第一桶金，把资产结构讲清楚"
    assert record.time_anchor == "2024年5月4日"
    assert record.chapter_span == "1天"
    assert record.hook == "出金群里真正赚钱的人都沉默了"
    assert record.end_open_question == "钱到了，下一步怎么安排？"
    assert record.key_entities == ["顾宜", "杜雨薇", "BOME"]
    assert record.source_file == "大纲/第1卷-详细大纲.md"
    assert record.outline_hash == hashlib.sha256(record.raw_section.encode("utf-8")).hexdigest()


def test_load_outline_catalog_uses_outline_range_for_global_offsets(tmp_path):
    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir()
    (outline_dir / "第1卷-详细大纲.md").write_text(
        "> 卷范围: 第1-48章\n\n### 第 48 章：卷一尾声\n- 目标: 收束\n",
        encoding="utf-8",
    )
    (outline_dir / "第2卷-详细大纲.md").write_text(
        "> 卷范围: 第1-50章\n\n### 第 1 章：卷二开局\n- 目标: 开局\n",
        encoding="utf-8",
    )

    records = load_outline_catalog(tmp_path)

    by_title = {record.title: record for record in records}
    assert by_title["卷一尾声"].global_chapter == 48
    assert by_title["卷二开局"].global_chapter == 49
