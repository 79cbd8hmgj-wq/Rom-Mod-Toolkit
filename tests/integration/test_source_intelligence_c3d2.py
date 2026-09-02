from __future__ import annotations

import json
from pathlib import Path

from rommod.domains.pokemon.analysis import analyze_repository
from rommod.domains.pokemon.loader import load_repository_index


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _species(
    root: Path,
    identifier: str,
    *,
    types: list[str],
    learnset: list[list[object]],
    evolutions: list[list[object]] | None = None,
) -> None:
    _write(
        root / "res" / "pokemon" / identifier / "data.json",
        {
            "base_stats": {
                "hp": 60,
                "attack": 80,
                "defense": 60,
                "speed": 80,
                "special_attack": 60,
                "special_defense": 60,
            },
            "types": types,
            "abilities": ["ABILITY_NONE", "ABILITY_NONE"],
            "learnset": {"by_level": learnset},
            "evolutions": evolutions or [],
            "pokedex_data": {"en": {"name": identifier.upper()}},
        },
    )


def _move(
    root: Path,
    identifier: str,
    *,
    move_type: str,
    move_class: str,
    power: int,
) -> None:
    _write(
        root / "res" / "moves" / identifier / "data.json",
        {
            "name": identifier.replace("_", " ").title(),
            "class": move_class,
            "type": move_type,
            "power": power,
            "accuracy": 100,
            "pp": 20,
        },
    )


def test_loader_and_analyzer_reproduce_c3d2_source_findings(tmp_path: Path) -> None:
    _species(
        tmp_path,
        "persian",
        types=["TYPE_NORMAL", "TYPE_NORMAL"],
        learnset=[[1, "MOVE_SWITCHEROO"], [6, "MOVE_BITE"]],
    )
    _species(
        tmp_path,
        "mankey",
        types=["TYPE_FIGHTING", "TYPE_FIGHTING"],
        learnset=[[25, "MOVE_ASSURANCE"], [33, "MOVE_SWAGGER"]],
        evolutions=[["EVO_LEVEL", 28, "SPECIES_PRIMEAPE"]],
    )
    _species(
        tmp_path,
        "primeape",
        types=["TYPE_FIGHTING", "TYPE_FIGHTING"],
        learnset=[[28, "MOVE_RAGE"], [35, "MOVE_SWAGGER"], [41, "MOVE_CROSS_CHOP"]],
    )
    _species(
        tmp_path,
        "ponyta",
        types=["TYPE_FIRE", "TYPE_FIRE"],
        learnset=[[37, "MOVE_FIRE_BLAST"], [42, "MOVE_BOUNCE"], [46, "MOVE_FLARE_BLITZ"]],
        evolutions=[["EVO_LEVEL", 40, "SPECIES_RAPIDASH"]],
    )
    _species(
        tmp_path,
        "rapidash",
        types=["TYPE_FIRE", "TYPE_FIRE"],
        learnset=[[40, "MOVE_FURY_ATTACK"], [47, "MOVE_BOUNCE"], [56, "MOVE_FLARE_BLITZ"]],
    )

    _move(tmp_path, "switcheroo", move_type="TYPE_DARK", move_class="CLASS_STATUS", power=0)
    _move(tmp_path, "bite", move_type="TYPE_DARK", move_class="CLASS_PHYSICAL", power=60)
    _move(tmp_path, "rage", move_type="TYPE_NORMAL", move_class="CLASS_PHYSICAL", power=20)
    _move(tmp_path, "swagger", move_type="TYPE_NORMAL", move_class="CLASS_STATUS", power=0)
    _move(tmp_path, "cross_chop", move_type="TYPE_FIGHTING", move_class="CLASS_PHYSICAL", power=100)
    _move(tmp_path, "bounce", move_type="TYPE_FLYING", move_class="CLASS_PHYSICAL", power=85)
    _move(tmp_path, "flare_blitz", move_type="TYPE_FIRE", move_class="CLASS_PHYSICAL", power=120)
    _move(tmp_path, "fury_attack", move_type="TYPE_NORMAL", move_class="CLASS_PHYSICAL", power=15)
    _move(tmp_path, "fire_blast", move_type="TYPE_FIRE", move_class="CLASS_SPECIAL", power=120)

    findings = analyze_repository(load_repository_index(tmp_path))
    keys = {
        (finding.code, finding.species, finding.move, finding.gap_levels)
        for finding in findings
    }

    assert ("level-one-only-status", "persian", "switcheroo", None) in keys
    assert ("evolution-level-non-stab", "primeape", "rage", None) in keys
    assert ("post-evolution-stab-gap", "primeape", "cross_chop", 13) in keys
    assert ("evolution-move-delay", "rapidash", "bounce", 5) in keys
    assert ("evolution-move-delay", "rapidash", "flare_blitz", 10) in keys
