from __future__ import annotations

import json
from pathlib import Path

from rommod.discovery.scanner import scan_project, write_scan_reports


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _pokemon_decomp(root: Path) -> None:
    (root / "Makefile").write_text(
        "CC := arm-none-eabi-gcc\nROM := build/game.nds\n",
        encoding="utf-8",
    )
    _write_json(
        root / "res" / "pokemon" / "pikachu" / "data.json",
        {
            "base_stats": {"hp": 35},
            "learnset": {"by_level": []},
            "evolutions": [],
        },
    )
    _write_json(root / "res" / "moves" / "tackle" / "data.json", {"name": "Tackle"})
    (root / "res" / "trainers").mkdir(parents=True)
    (root / "res" / "items").mkdir(parents=True)
    (root / "res" / "text").mkdir(parents=True)
    (root / "build").mkdir(parents=True)
    (root / "build" / "game.nds").write_bytes(b"NDS")


def test_scan_project_detects_pokemon_decomp_capabilities(tmp_path: Path) -> None:
    _pokemon_decomp(tmp_path)

    report = scan_project(tmp_path)

    assert report.root == tmp_path.resolve()
    assert report.platform == "nds"
    assert report.project_type == "pokemon_decomp"
    assert report.build_system == "make"
    assert report.toolchains == ("arm-none-eabi",)
    assert report.systems_detected == {
        "pokemon": True,
        "moves": True,
        "evolutions": True,
        "trainers": True,
        "items": True,
        "text": True,
    }
    assert report.rom_outputs == ("build/game.nds",)


def test_scan_project_is_read_only_until_reports_are_requested(tmp_path: Path) -> None:
    _pokemon_decomp(tmp_path)

    report = scan_project(tmp_path)

    assert not (tmp_path / "rommod").exists()

    project_path, report_path = write_scan_reports(report)

    assert project_path == tmp_path / "rommod" / "project.json"
    assert report_path == tmp_path / "rommod" / "reports" / "project_scan.json"
    project = json.loads(project_path.read_text(encoding="utf-8"))
    full_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert project["schema_version"] == 1
    assert project["platform"] == "nds"
    assert project["project_type"] == "pokemon_decomp"
    assert project["build_system"] == "make"
    assert full_report["rom_outputs"] == ["build/game.nds"]
    assert full_report["systems_detected"]["pokemon"] is True
