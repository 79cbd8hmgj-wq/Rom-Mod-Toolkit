from __future__ import annotations

import json
from pathlib import Path

import pytest

from rommod.dev.build import build_source_project
from rommod.errors import BuildError


def _pokemon_markers(root: Path) -> None:
    pokemon = root / "res" / "pokemon" / "pikachu"
    moves = root / "res" / "moves" / "tackle"
    pokemon.mkdir(parents=True)
    moves.mkdir(parents=True)
    (pokemon / "data.json").write_text(
        json.dumps({"learnset": {"by_level": []}, "evolutions": []}) + "\n",
        encoding="utf-8",
    )
    (moves / "data.json").write_text(json.dumps({"name": "Tackle"}) + "\n", encoding="utf-8")


def test_source_build_runs_native_make_and_records_new_rom_output(tmp_path: Path) -> None:
    _pokemon_markers(tmp_path)
    (tmp_path / "Makefile").write_text(
        "all:\n\tmkdir -p build\n\tprintf 'NDS' > build/game.nds\n",
        encoding="utf-8",
    )

    result = build_source_project(tmp_path)

    assert result.root == tmp_path.resolve()
    assert result.build_system == "make"
    assert result.command == ("make",)
    assert result.outputs == ("build/game.nds",)
    assert result.report_path == tmp_path / "rommod" / "reports" / "build.json"
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["success"] is True
    assert report["build_system"] == "make"
    assert report["command"] == ["make"]
    assert report["outputs"] == ["build/game.nds"]


def test_source_build_surfaces_native_build_failure(tmp_path: Path) -> None:
    _pokemon_markers(tmp_path)
    (tmp_path / "Makefile").write_text("all:\n\tfalse\n", encoding="utf-8")

    with pytest.raises(BuildError, match="native build failed"):
        build_source_project(tmp_path)
