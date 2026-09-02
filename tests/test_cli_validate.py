from __future__ import annotations

import json
from pathlib import Path

from rommod.cli import main


def test_validate_cli_returns_nonzero_and_json_for_source_issues(tmp_path: Path, capsys) -> None:
    species = tmp_path / "res" / "pokemon" / "primeape" / "data.json"
    species.parent.mkdir(parents=True, exist_ok=True)
    species.write_text(
        json.dumps(
            {
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
                "learnset": {"by_level": [[10, "MOVE_UNKNOWN"]]},
                "evolutions": [],
                "pokedex_data": {"en": {"name": "PRIMEAPE"}},
            }
        ),
        encoding="utf-8",
    )
    move = tmp_path / "res" / "moves" / "tackle" / "data.json"
    move.parent.mkdir(parents=True, exist_ok=True)
    move.write_text(
        json.dumps(
            {
                "name": "Tackle",
                "type": "TYPE_NORMAL",
                "class": "CLASS_PHYSICAL",
                "power": 40,
                "accuracy": 100,
                "pp": 35,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["validate", str(tmp_path)])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert payload["issues"][0]["code"] == "unknown-move"
