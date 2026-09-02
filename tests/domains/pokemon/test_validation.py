from __future__ import annotations

import json
from pathlib import Path

from rommod.domains.pokemon.validation import validate_repository


def _write(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _species(*, moves: list[list[object]], evolutions: list[list[object]]) -> dict[str, object]:
    return {
        "base_stats": {
            "hp": 70,
            "attack": 100,
            "defense": 70,
            "special_attack": 50,
            "special_defense": 70,
            "speed": 100,
        },
        "types": ["TYPE_FIGHTING", "TYPE_FIGHTING"],
        "abilities": ["ABILITY_VITAL_SPIRIT"],
        "learnset": {"by_level": moves},
        "evolutions": evolutions,
        "pokedex_data": {"en": {"name": "PRIMEAPE"}},
    }


def test_validate_repository_finds_reference_duplicate_and_level_problems(tmp_path: Path) -> None:
    _write(
        tmp_path / "res" / "pokemon" / "primeape" / "data.json",
        _species(
            moves=[
                [101, "MOVE_TACKLE"],
                [5, "MOVE_TACKLE"],
                [10, "MOVE_MISSING"],
            ],
            evolutions=[["EVO_LEVEL", 28, "SPECIES_MISSINGNO"]],
        ),
    )
    _write(
        tmp_path / "res" / "moves" / "tackle" / "data.json",
        {
            "name": "Tackle",
            "type": "TYPE_NORMAL",
            "class": "CLASS_PHYSICAL",
            "power": 40,
            "accuracy": 100,
            "pp": 35,
        },
    )

    report = validate_repository(tmp_path)
    payload = report.to_dict()

    assert payload["valid"] is False
    assert payload["issue_count"] == 4
    assert {issue["code"] for issue in payload["issues"]} == {
        "broken-evolution",
        "duplicate-learnset-move",
        "invalid-level",
        "unknown-move",
    }
    assert all(issue["species"] == "primeape" for issue in payload["issues"])


def test_validate_repository_accepts_consistent_source_data(tmp_path: Path) -> None:
    _write(
        tmp_path / "res" / "pokemon" / "primeape" / "data.json",
        _species(moves=[[28, "MOVE_TACKLE"]], evolutions=[]),
    )
    _write(
        tmp_path / "res" / "moves" / "tackle" / "data.json",
        {
            "name": "Tackle",
            "type": "TYPE_NORMAL",
            "class": "CLASS_PHYSICAL",
            "power": 40,
            "accuracy": 100,
            "pp": 35,
        },
    )

    report = validate_repository(tmp_path)

    assert report.valid is True
    assert report.issues == ()
