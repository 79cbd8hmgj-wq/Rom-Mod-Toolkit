from __future__ import annotations

import json
from pathlib import Path

from rommod.cli import main


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_source_analyze_cli_emits_machine_readable_pokemon_findings(
    tmp_path: Path,
    capsys,
) -> None:
    _write(
        tmp_path / "res" / "pokemon" / "persian" / "data.json",
        {
            "base_stats": {
                "hp": 65,
                "attack": 70,
                "defense": 60,
                "speed": 115,
                "special_attack": 65,
                "special_defense": 65,
            },
            "types": ["TYPE_NORMAL", "TYPE_NORMAL"],
            "abilities": ["ABILITY_LIMBER", "ABILITY_TECHNICIAN"],
            "learnset": {"by_level": [[1, "MOVE_SWITCHEROO"], [6, "MOVE_BITE"]]},
            "evolutions": [],
            "pokedex_data": {"en": {"name": "PERSIAN"}},
        },
    )
    _write(
        tmp_path / "res" / "moves" / "switcheroo" / "data.json",
        {
            "name": "Switcheroo",
            "class": "CLASS_STATUS",
            "type": "TYPE_DARK",
            "power": 0,
            "accuracy": 100,
            "pp": 10,
        },
    )

    exit_code = main(["source-analyze", str(tmp_path), "--domain", "pokemon"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["domain"] == "pokemon"
    assert output["species_count"] == 1
    assert output["move_count"] == 1
    assert output["evolution_count"] == 0
    assert output["findings"][0]["code"] == "level-one-only-status"
    assert output["findings"][0]["species"] == "persian"
    assert output["findings"][0]["move"] == "switcheroo"
    assert output["findings"][0]["source_path"] == "res/pokemon/persian/data.json"
