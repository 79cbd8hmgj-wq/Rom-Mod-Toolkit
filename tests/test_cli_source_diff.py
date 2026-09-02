from __future__ import annotations

import json
from pathlib import Path

from rommod.cli import main


def _write_species(root: Path, attack: int) -> None:
    path = root / "res" / "pokemon" / "golem" / "data.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "base_stats": {
                    "hp": 80,
                    "attack": attack,
                    "defense": 130,
                    "special_attack": 45,
                    "special_defense": 80,
                    "speed": 45,
                },
                "types": ["TYPE_ROCK", "TYPE_GROUND"],
                "abilities": ["ABILITY_ROCK_HEAD"],
                "learnset": {"by_level": [[35, "MOVE_ROCK_SLIDE"]]},
                "evolutions": [],
                "pokedex_data": {"en": {"name": "GOLEM"}},
            }
        ),
        encoding="utf-8",
    )


def test_source_diff_cli_emits_machine_readable_semantic_diff(tmp_path: Path, capsys) -> None:
    before = tmp_path / "before"
    after = tmp_path / "after"
    _write_species(before, 120)
    _write_species(after, 130)

    exit_code = main(["source-diff", str(before), str(after), "--domain", "pokemon"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["domain"] == "pokemon"
    assert payload["changed_species"] == 1
    assert payload["species"][0]["stats"][0] == {
        "stat": "attack",
        "before": 120,
        "after": 130,
    }
