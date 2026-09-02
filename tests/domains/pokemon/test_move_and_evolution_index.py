from __future__ import annotations

import json
from pathlib import Path

from rommod.domains.pokemon.discovery import discover_move_files
from rommod.domains.pokemon.loader import load_repository_index


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _write_species(root: Path, identifier: str, evolutions: list | None = None) -> None:
    _write_json(
        root / "res" / "pokemon" / identifier / "data.json",
        {
            "base_stats": {
                "hp": 39,
                "attack": 52,
                "defense": 43,
                "speed": 65,
                "special_attack": 60,
                "special_defense": 50,
            },
            "types": ["TYPE_FIRE", "TYPE_FIRE"],
            "abilities": ["ABILITY_BLAZE", "ABILITY_NONE"],
            "learnset": {"by_level": [[1, "MOVE_SCRATCH"]]},
            "evolutions": evolutions or [],
            "pokedex_data": {"en": {"name": identifier.upper()}},
        },
    )


def _write_move(root: Path, identifier: str, name: str, power: int = 40) -> None:
    _write_json(
        root / "res" / "moves" / identifier / "data.json",
        {
            "name": name,
            "class": "CLASS_SPECIAL",
            "type": "TYPE_FIRE",
            "power": power,
            "accuracy": 100,
            "pp": 25,
        },
    )


def test_discover_move_files_is_deterministic(tmp_path: Path) -> None:
    _write_move(tmp_path, "flamethrower", "Flamethrower", 95)
    _write_move(tmp_path, "ember", "Ember")

    paths = discover_move_files(tmp_path)

    assert [path.relative_to(tmp_path).as_posix() for path in paths] == [
        "res/moves/ember/data.json",
        "res/moves/flamethrower/data.json",
    ]


def test_repository_index_loads_real_move_metadata_and_level_evolutions(tmp_path: Path) -> None:
    _write_species(
        tmp_path,
        "charmander",
        evolutions=[["EVO_LEVEL", 16, "SPECIES_CHARMELEON"]],
    )
    _write_move(tmp_path, "ember", "Ember")

    index = load_repository_index(tmp_path)

    ember = index.moves["ember"]
    assert ember.display_name == "Ember"
    assert ember.move_type == "TYPE_FIRE"
    assert ember.category == "CLASS_SPECIAL"
    assert ember.power == 40
    assert ember.accuracy == 100
    assert ember.pp == 25
    assert ember.source_path is not None
    assert ember.source_path.as_posix() == "res/moves/ember/data.json"

    assert len(index.evolutions) == 1
    evolution = index.evolutions[0]
    assert evolution.source == "charmander"
    assert evolution.target == "charmeleon"
    assert evolution.method == "EVO_LEVEL"
    assert evolution.level == 16
    assert not any("move metadata" in warning.lower() for warning in index.warnings)


def test_repository_index_preserves_nonlevel_evolution_method_without_fake_level(tmp_path: Path) -> None:
    _write_species(
        tmp_path,
        "eevee",
        evolutions=[["EVO_USE_ITEM", "ITEM_FIRE_STONE", "SPECIES_FLAREON"]],
    )

    index = load_repository_index(tmp_path)

    evolution = index.evolutions[0]
    assert evolution.source == "eevee"
    assert evolution.target == "flareon"
    assert evolution.method == "EVO_USE_ITEM"
    assert evolution.level is None
