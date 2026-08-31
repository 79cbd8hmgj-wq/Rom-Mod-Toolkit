from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from rommod.projects.manifest import ToolsConfig, load_manifest, write_manifest
from rommod.projects.project import init_project


def test_patch_tool_paths_round_trip(synthetic_rom_path: Path, tmp_path: Path):
    project = tmp_path / "mod"
    manifest = init_project(synthetic_rom_path, project)
    manifest = replace(
        manifest,
        tools=ToolsConfig(flips="tools/flips", xdelta3="tools/xdelta3"),
    )
    write_manifest(project, manifest)

    loaded = load_manifest(project)
    assert loaded.tools.flips == "tools/flips"
    assert loaded.tools.xdelta3 == "tools/xdelta3"
