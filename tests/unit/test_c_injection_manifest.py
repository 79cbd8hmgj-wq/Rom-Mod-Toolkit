from __future__ import annotations

from pathlib import Path

from rommod.projects.manifest import (
    CInjectChange,
    OutputConfig,
    ProjectManifest,
    SourceConfig,
    ToolsConfig,
    load_manifest,
    write_manifest,
)


def test_c_inject_manifest_round_trip(tmp_path: Path):
    manifest = ProjectManifest(
        schema_version=1,
        platform="nds",
        source=SourceConfig(rom="../game.nds", sha256="a" * 64),
        output=OutputConfig(rom="build/output/game.nds"),
        changes=(
            CInjectChange(
                target="arm9",
                symbol_file="analysis/symbols.json",
                hook="HookSite",
                expected=bytes.fromhex("05 06 07 08"),
                source="src/payload.c",
                cave="auto",
                reserve=32,
                fill=0,
            ),
        ),
        tools=ToolsConfig(
            armips="tools/armips",
            clang="tools/clang",
            ld_lld="tools/ld.lld",
            llvm_objcopy="tools/llvm-objcopy",
        ),
    )
    write_manifest(tmp_path, manifest)
    assert load_manifest(tmp_path) == manifest
