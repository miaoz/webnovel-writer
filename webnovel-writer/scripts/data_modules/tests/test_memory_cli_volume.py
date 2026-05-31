#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys


def test_memory_cli_load_context_accepts_volume_local_chapter(tmp_path, monkeypatch, capsys):
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
    (outline_dir / "第1卷-详细大纲.md").write_text("> 卷范围: 第1-48章\n", encoding="utf-8")
    (outline_dir / "第2卷-详细大纲.md").write_text("> 卷范围: 第1-50章\n", encoding="utf-8")
    seen = {}

    class FakePack:
        def to_dict(self):
            return {"chapter": seen["chapter"]}

    class FakeAdapter:
        def load_context(self, chapter):
            seen["chapter"] = chapter
            return FakePack()

    monkeypatch.setattr("memory_cli._adapter", lambda project_root: FakeAdapter())

    from memory_cli import main

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "memory_cli",
            "--project-root",
            str(tmp_path),
            "load-context",
            "--volume",
            "2",
            "--chapter",
            "1",
        ],
    )
    main()

    assert json.loads(capsys.readouterr().out)["chapter"] == 49
