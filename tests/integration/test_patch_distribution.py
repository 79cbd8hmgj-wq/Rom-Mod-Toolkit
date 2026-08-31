from __future__ import annotations

import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from rommod.patching.distribution import create_project_patch, generate_binary_patch
from rommod.projects.manifest import BytePatchChange, ToolsConfig, write_manifest
from rommod.projects.project import init_project


def _tool(name: str, env: str) -> str:
    value = os.environ.get(env) or shutil.which(name)
    if not value:
        pytest.skip(f"{name} executable not available")
    return str(Path(value).absolute())


def test_generate_bps_and_ips_with_flips(tmp_path: Path):
    source = tmp_path / "source.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"ROMMOD-source-" * 32)
    target.write_bytes(b"ROMMOD-target-" * 32 + b"tail")
    tools = ToolsConfig(flips=_tool("flips", "ROMMOD_FLIPS"))

    for patch_format in ("bps", "ips"):
        result = generate_binary_patch(
            tmp_path,
            source,
            target,
            patch_format=patch_format,
            output=tmp_path / f"mod.{patch_format}",
            tools=tools,
        )
        assert result.output_path.is_file()
        assert result.patch_format == patch_format
        assert result.verified is True
        assert result.patch_sha256


def test_generate_xdelta_with_xdelta3(tmp_path: Path):
    source = tmp_path / "source.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"A" * 4096 + b"B" * 4096)
    target.write_bytes(b"A" * 4096 + b"CHANGED" + b"B" * 4089)
    tools = ToolsConfig(xdelta3=_tool("xdelta3", "ROMMOD_XDELTA3"))

    result = generate_binary_patch(
        tmp_path,
        source,
        target,
        patch_format="xdelta",
        output=tmp_path / "mod.xdelta",
        tools=tools,
    )
    assert result.output_path.is_file()
    assert result.patch_format == "xdelta"
    assert result.verified is True


def test_project_patch_rebuilds_and_writes_report(synthetic_rom_path: Path, tmp_path: Path):
    project = tmp_path / "mod"
    manifest = init_project(synthetic_rom_path, project)
    manifest = replace(
        manifest,
        changes=(BytePatchChange("arm9", 4, bytes([5, 6]), b"\xFA\xFB"),),
        tools=ToolsConfig(flips=_tool("flips", "ROMMOD_FLIPS")),
    )
    write_manifest(project, manifest)

    result = create_project_patch(project, "bps")
    expected_patch = (project / manifest.output.rom).with_suffix(".bps")
    assert result.output_path == expected_patch
    assert result.output_path.is_file()
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["format"] == "bps"
    assert report["verified"] is True
    assert report["source_sha256"] == manifest.source.sha256
    assert report["target_sha256"]
    assert report["patch_sha256"] == result.patch_sha256
