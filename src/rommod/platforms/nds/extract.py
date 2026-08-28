"""Human-inspectable NDS project extraction."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from rommod.platforms.nds.binaries import get_main_binary
from rommod.platforms.nds.filesystem import extract_files
from rommod.platforms.nds.overlays import get_overlay_raw, list_overlays
from rommod.platforms.nds.rom import NdsRom
from rommod.projects.manifest import load_manifest
from rommod.projects.project import verify_source


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def extract_project(project_dir: Path) -> dict:
    project = Path(project_dir).resolve()
    manifest = load_manifest(project)
    source = verify_source(project, manifest)
    rom = NdsRom.load(source)

    extracted = project / "build/extracted"
    if extracted.exists():
        shutil.rmtree(extracted)
    extracted.mkdir(parents=True)

    metadata = asdict(rom.metadata())
    _write_json(extracted / "metadata.json", metadata)
    (extracted / "arm9.bin").write_bytes(get_main_binary(rom, "arm9"))
    (extracted / "arm7.bin").write_bytes(get_main_binary(rom, "arm7"))
    extract_files(rom, extracted / "nitrofs")

    overlay_counts: dict[str, int] = {}
    for processor in ("arm9", "arm7"):
        infos = list_overlays(rom, processor)
        overlay_counts[processor] = len(infos)
        base = extracted / "overlays" / processor
        base.mkdir(parents=True, exist_ok=True)
        for info in infos:
            (base / f"{info.overlay_id}.bin").write_bytes(
                get_overlay_raw(rom, processor, info.overlay_id)
            )
        _write_json(base / "index.json", [asdict(info) for info in infos])

    source_report = {
        "platform": "nds",
        "source": manifest.source.rom,
        "sha256": manifest.source.sha256,
        "size": rom.metadata().source_size,
    }
    _write_json(project / "reports/source.json", source_report)
    return {"platform": "nds", "metadata": metadata, "overlays": overlay_counts}
