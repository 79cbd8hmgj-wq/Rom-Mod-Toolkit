from __future__ import annotations

from pathlib import Path

from rommod.projects.manifest import (
    ArmipsChange,
    OutputConfig,
    ProjectManifest,
    SourceConfig,
    ToolsConfig,
    load_manifest,
    write_manifest,
)


def test_armips_manifest_round_trip(tmp_path: Path):
    manifest = ProjectManifest(
        schema_version=1,
        platform="nds",
        source=SourceConfig(rom="../game.nds", sha256="a" * 64),
        output=OutputConfig(rom="build/output/game-modded.nds"),
        changes=(
            ArmipsChange(
                target="arm9",
                script="asm/patch.asm",
                symbols="reports/patch.sym",
            ),
        ),
        tools=ToolsConfig(armips="tools/armips"),
    )
    write_manifest(tmp_path, manifest)
    assert load_manifest(tmp_path) == manifest


def test_armips_symbols_are_optional(tmp_path: Path):
    (tmp_path / "rommod.yaml").write_text(
        """schema_version: 1
platform: nds
source:
  rom: ../game.nds
  sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
output:
  rom: build/output/game.nds
changes:
  - type: armips
    target: overlay9:3
    script: asm/patch.asm
""",
        encoding="utf-8",
    )
    change = load_manifest(tmp_path).changes[0]
    assert isinstance(change, ArmipsChange)
    assert change.symbols is None
