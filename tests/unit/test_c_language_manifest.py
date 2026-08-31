from __future__ import annotations

from pathlib import Path

import pytest

from rommod.errors import ManifestError
from rommod.projects.manifest import CInjectChange, load_manifest, write_manifest


_BASE = """schema_version: 1
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
    source: src/payload.c
    cave: auto
    reserve: 64
"""


def test_c_inject_manifest_round_trips_explicit_cpp_language(tmp_path: Path):
    (tmp_path / "rommod.yaml").write_text(
        _BASE + "    language: cpp\n",
        encoding="utf-8",
    )

    manifest = load_manifest(tmp_path)
    change = manifest.changes[0]
    assert isinstance(change, CInjectChange)
    assert change.language == "cpp"

    write_manifest(tmp_path, manifest)
    assert load_manifest(tmp_path) == manifest


def test_c_inject_manifest_defaults_language_to_auto(tmp_path: Path):
    (tmp_path / "rommod.yaml").write_text(_BASE, encoding="utf-8")
    change = load_manifest(tmp_path).changes[0]
    assert isinstance(change, CInjectChange)
    assert change.language == "auto"


def test_c_inject_manifest_rejects_unknown_language(tmp_path: Path):
    (tmp_path / "rommod.yaml").write_text(
        _BASE + "    language: rust\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="language"):
        load_manifest(tmp_path)
