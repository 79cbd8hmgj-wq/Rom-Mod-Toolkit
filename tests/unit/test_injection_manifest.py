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


def test_thumb_short_inject_manifest_round_trip(tmp_path: Path):
    manifest = ProjectManifest(
        schema_version=1,
        platform="nds",
        source=SourceConfig(rom="../game.nds", sha256="a" * 64),
        output=OutputConfig(rom="build/output/game.nds"),
        changes=(
            InjectChange(
                target="arm9",
                symbol_file="analysis/symbols.json",
                hook="ThumbHook",
                expected=bytes.fromhex("05 06"),
                script="asm/payload.asm",
                cave="auto",
                reserve=16,
            ),
        ),
    )
    write_manifest(tmp_path, manifest)
    assert load_manifest(tmp_path) == manifest


def test_thumb_long_inject_manifest_round_trip_with_scratch_register(tmp_path: Path):
    manifest = ProjectManifest(
        schema_version=1,
        platform="nds",
        source=SourceConfig(rom="../game.nds", sha256="a" * 64),
        output=OutputConfig(rom="build/output/game.nds"),
        changes=(
            InjectChange(
                target="arm9",
                symbol_file="analysis/symbols.json",
                hook="ThumbHook",
                expected=bytes.fromhex("05 06 07 08 09 0A 0B 0C"),
                script="asm/payload.asm",
                cave="auto",
                reserve=24,
                scratch_register="r3",
            ),
        ),
    )
    write_manifest(tmp_path, manifest)
    assert load_manifest(tmp_path) == manifest
