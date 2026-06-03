from __future__ import annotations

import json
import re
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"


def test_codex_plugin_manifest_is_validation_ready():
    assert MANIFEST_PATH.is_file()

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["name"] == "webnovel-writer"
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", manifest["version"])
    assert manifest["author"]["name"]
    assert manifest["skills"] == "./skills/"

    interface = manifest["interface"]
    for field in [
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
        "defaultPrompt",
    ]:
        assert interface[field]

    assert interface["capabilities"] == ["Interactive", "Write"]
    assert len(interface["defaultPrompt"]) <= 3

    for field in ["websiteURL", "privacyPolicyURL", "termsOfServiceURL"]:
        if field in interface:
            assert interface[field].startswith("https://")

    for field in ["composerIcon", "logo", "screenshots"]:
        assert field not in interface

    for unsupported in ["hooks", "apps", "mcpServers"]:
        assert unsupported not in manifest
