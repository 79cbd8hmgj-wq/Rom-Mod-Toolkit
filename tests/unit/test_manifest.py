from pathlib import Path

import pytest

from rommod.errors import ManifestError
from rommod.projects.manifest import (
    BytePatchChange,
    FileReplaceChange,
    OutputConfig,
    ProjectManifest,
    SourceConfig,
    load_manifest,
    write_manifest,
)


def test_manifest_round_trip(tmp_path: Path):
    manifest = ProjectManifest(
        schema_version=1,
        platform="nds",
        source=SourceConfig(rom="../game.nds", sha256="a" * 64),
        output=OutputConfig(rom="build/output/game-modded.nds"),
        changes=(
            FileReplaceChange(target="data/example.bin", source="files/example.bin"),
            BytePatchChange(target="arm9", offset=0x10, expected=b"\x01\x02", replacement=b"\xAA\xBB"),
        ),
    )
    write_manifest(tmp_path, manifest)
    assert load_manifest(tmp_path) == manifest


def test_manifest_rejects_unknown_change_type(tmp_path: Path):
    (tmp_path / "rommod.yaml").write_text(
        """schema_version: 1
platform: nds
source:
  rom: ../game.nds
  sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
output:
  rom: build/output/game.nds
changes:
  - type: mystery
""",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="changes\\[0\\].type"):
        load_manifest(tmp_path)
