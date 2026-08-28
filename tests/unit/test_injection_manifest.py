from __future__ import annotations

from pathlib import Path

from rommod.projects.manifest import (
    InjectChange,
    OutputConfig,
    ProjectManifest,
    SourceConfig,
    write_manifest,
    load_manifest,
)


def test_inject_manifest_round_trip(tmp_path: Path):
    manifest = ProjectManifest(
        schema_version=1,
        platform="nds",
        source=SourceConfig(rom="../game.nds", sha256="a" * 64),
        output=OutputConfig(rom="build/output/game.nds"),
        changes=(
            InjectChange(
                target="arm9",
                symbol_file="analysis/symbols.json",
                hook="HookSite",
                expected=bytes.fromhex("05 06 07 08"),
                script="asm/payload.asm",
                cave="auto",
                reserve=16,
                fill=0,
                symbols="reports/inject.sym",
            ),
        ),
    )
    write_manifest(tmp_path, manifest)
    assert load_manifest(tmp_path) == manifest
