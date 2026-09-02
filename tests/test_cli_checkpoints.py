from __future__ import annotations

import json
from pathlib import Path

from rommod.cli import main


def _seed(root: Path, attack: int) -> None:
    species = root / "res" / "pokemon" / "golem" / "data.json"
    species.parent.mkdir(parents=True, exist_ok=True)
    species.write_text(
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
                "learnset": {"by_level": [], "other": []},
                "evolutions": [],
                "pokedex_data": {"en": {"name": "GOLEM"}},
            }
        ),
        encoding="utf-8",
    )


def test_checkpoint_and_compare_cli(tmp_path: Path, capsys) -> None:
    _seed(tmp_path, 120)
    assert main(["checkpoint", "before", "--root", str(tmp_path)]) == 0
    first_payload = json.loads(capsys.readouterr().out)
    first = Path(first_payload["directory"])

    _seed(tmp_path, 130)
    assert main(["checkpoint", "after", "--root", str(tmp_path)]) == 0
    second_payload = json.loads(capsys.readouterr().out)
    second = Path(second_payload["directory"])

    assert main(["compare", str(first), str(second)]) == 0
    diff = json.loads(capsys.readouterr().out)
    assert diff["changed_species"] == 1
    assert diff["species"][0]["bst"] == {"before": 500, "after": 510}
