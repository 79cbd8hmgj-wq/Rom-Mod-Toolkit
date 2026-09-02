from __future__ import annotations

import json
from pathlib import Path

from rommod.domains.pokemon.diff import diff_repositories


def _write_species(
    root: Path,
    identifier: str,
    *,
    stats: dict[str, int],
    moves: list[list[object]],
) -> None:
    path = root / "res" / "pokemon" / identifier / "data.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "base_stats": stats,
                "types": ["TYPE_ROCK", "TYPE_GROUND"],
                "abilities": ["ABILITY_ROCK_HEAD"],
                "learnset": {"by_level": moves},
                "evolutions": [],
                "pokedex_data": {"en": {"name": identifier.upper()}},
            }
        ),
        encoding="utf-8",
    )


def _stats(*, attack: int) -> dict[str, int]:
    return {
        "hp": 80,
        "attack": attack,
        "defense": 130,
        "special_attack": 45,
        "special_defense": 80,
        "speed": 45,
    }


def test_diff_repositories_reports_semantic_stats_and_learnset_changes(tmp_path: Path) -> None:
    before = tmp_path / "before"
    after = tmp_path / "after"
    _write_species(
        before,
        "golem",
        stats=_stats(attack=120),
        moves=[[35, "MOVE_EXPLOSION"], [56, "MOVE_FLARE_BLITZ"]],
    )
    _write_species(
        after,
        "golem",
        stats=_stats(attack=130),
        moves=[[35, "MOVE_ROCK_SLIDE"], [46, "MOVE_FLARE_BLITZ"]],
    )

    payload = diff_repositories(before, after).to_dict()

    assert payload["domain"] == "pokemon"
    assert payload["changed_species"] == 1
    species = payload["species"][0]
    assert species["species"] == "golem"
    assert species["stats"] == [{"stat": "attack", "before": 120, "after": 130}]
    assert species["bst"] == {"before": 500, "after": 510}
    assert species["learnset"] == [
        {
            "move": "MOVE_EXPLOSION",
            "kind": "removed",
            "before_level": 35,
            "after_level": None,
        },
        {
            "move": "MOVE_FLARE_BLITZ",
            "kind": "level",
            "before_level": 56,
            "after_level": 46,
        },
        {
            "move": "MOVE_ROCK_SLIDE",
            "kind": "added",
            "before_level": None,
            "after_level": 35,
        },
    ]
