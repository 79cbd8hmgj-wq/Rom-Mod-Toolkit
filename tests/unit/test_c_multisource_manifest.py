from __future__ import annotations

from pathlib import Path

import pytest

from rommod.errors import ManifestError
from rommod.projects.manifest import CInjectChange, load_manifest, write_manifest


def _manifest(change_body: str) -> str:
    return f"""schema_version: 1
platform: nds
source:
  rom: ../game.nds
  sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
output:
  rom: build/output/game.nds
changes:
  - type: c_inject
    target: arm9
    symbol_file: analysis/symbols.json
    hook: HookSite
    expected: "05 06 07 08"
{change_body}    cave: auto
    reserve: 48
"""


def test_c_inject_manifest_accepts_sources_list(tmp_path: Path):
    (tmp_path / "rommod.yaml").write_text(
        _manifest(
            "    sources:\n"
            "      - src/payload.c\n"
            "      - src/helper.c\n"
        ),
        encoding="utf-8",
    )

    manifest = load_manifest(tmp_path)
    change = manifest.changes[0]
    assert isinstance(change, CInjectChange)
    assert change.source is None
    assert change.sources == ("src/payload.c", "src/helper.c")

    write_manifest(tmp_path, manifest)
    assert load_manifest(tmp_path) == manifest


def test_c_inject_manifest_rejects_source_and_sources_together(tmp_path: Path):
    (tmp_path / "rommod.yaml").write_text(
        _manifest(
            "    source: src/payload.c\n"
            "    sources:\n"
            "      - src/helper.c\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="exactly one"):
        load_manifest(tmp_path)


def test_c_inject_manifest_rejects_missing_source_declaration(tmp_path: Path):
    (tmp_path / "rommod.yaml").write_text(_manifest(""), encoding="utf-8")
    with pytest.raises(ManifestError, match="exactly one"):
        load_manifest(tmp_path)
