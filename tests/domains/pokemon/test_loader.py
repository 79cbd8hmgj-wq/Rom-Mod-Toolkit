from __future__ import annotations

import json
from pathlib import Path

import pytest

from rommod.domains.pokemon.discovery import discover_species_files
from rommod.domains.pokemon.loader import load_repository_index
from rommod.errors import RomModError


def _write_species(root: Path, identifier: str, data: dict) -> Path:
    path = root / "res" / "pokemon" / identifier / "data.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def _species_data(name: str = "Persian") -> dict:
    return {
        "name": name,
        "types": ["Normal"],
        "base_stats": {
            "hp": 65,
            "attack": 70,
            "defense": 60,
            "special_attack": 65,
            "special_defense": 65,
            "speed": 115,
        },
        "abilities": ["Limber", "Technician"],
        "level_up_moves": [
            {"level": 1, "move": "Switcheroo"},
            {"level": 6, "move": "Bite"},
        ],
    }


def test_discover_species_files_is_deterministic(tmp_path: Path) -> None:
    _write_species(tmp_path, "rapidash", _species_data("Rapidash"))
    _write_species(tmp_path, "persian", _species_data("Persian"))

    paths = discover_species_files(tmp_path)

    assert [path.relative_to(tmp_path).as_posix() for path in paths] == [
        "res/pokemon/persian/data.json",
        "res/pokemon/rapidash/data.json",
    ]


def test_load_repository_index_normalizes_species_and_learnset(tmp_path: Path) -> None:
    _write_species(tmp_path, "persian", _species_data())

    index = load_repository_index(tmp_path)
    persian = index.species["persian"]

    assert persian.identifier == "persian"
    assert persian.display_name == "Persian"
    assert persian.source_path.as_posix() == "res/pokemon/persian/data.json"
    assert persian.types == ("Normal",)
    assert persian.base_stats == (65, 70, 60, 65, 65, 115)
    assert persian.abilities == ("Limber", "Technician")
    assert [(entry.level, entry.move) for entry in persian.level_up_moves] == [
        (1, "Switcheroo"),
        (6, "Bite"),
    ]
    assert index.moves == {}
    assert any("move metadata" in warning.lower() for warning in index.warnings)


def test_load_repository_index_uses_directory_identifier_case_insensitively(tmp_path: Path) -> None:
    _write_species(tmp_path, "Mr_Mime", _species_data("Mr. Mime"))

    index = load_repository_index(tmp_path)

    assert "mr_mime" in index.species
    assert index.species["mr_mime"].display_name == "Mr. Mime"


def test_load_repository_index_names_malformed_source_path(tmp_path: Path) -> None:
    data = _species_data()
    del data["base_stats"]["speed"]
    _write_species(tmp_path, "persian", data)

    with pytest.raises(RomModError, match=r"res/pokemon/persian/data\.json.*speed"):
        load_repository_index(tmp_path)
