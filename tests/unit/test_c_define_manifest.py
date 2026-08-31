from __future__ import annotations

from pathlib import Path

import pytest

from rommod.errors import ManifestError
from rommod.projects.manifest import CInjectChange, load_manifest, write_manifest


def _write_manifest(tmp_path: Path, defines_yaml: str) -> None:
    (tmp_path / "rommod.yaml").write_text(
        f"""schema_version: 1
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
    defines:
{defines_yaml}
    cave: auto
    reserve: 64
""",
        encoding="utf-8",
    )


def test_c_inject_manifest_round_trips_preprocessor_defines(tmp_path: Path):
    _write_manifest(
        tmp_path,
        "      - ROMMOD_FEATURE=1\n      - GAME_REGION_US\n",
    )

    manifest = load_manifest(tmp_path)
    change = manifest.changes[0]
    assert isinstance(change, CInjectChange)
    assert change.defines == ("ROMMOD_FEATURE=1", "GAME_REGION_US")

    write_manifest(tmp_path, manifest)
    assert load_manifest(tmp_path) == manifest


def test_c_inject_manifest_rejects_unsafe_define_name(tmp_path: Path):
    _write_manifest(tmp_path, "      - BAD-NAME=1\n")
    with pytest.raises(ManifestError, match="defines"):
        load_manifest(tmp_path)


def test_c_inject_manifest_rejects_non_string_define(tmp_path: Path):
    _write_manifest(tmp_path, "      - 123\n")
    with pytest.raises(ManifestError, match="defines"):
        load_manifest(tmp_path)
