from __future__ import annotations

import json
from pathlib import Path

from rommod.cli import main


def _write_json(path: Path, data: dict, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=indent) + "\n", encoding="utf-8")


def _species(root: Path) -> Path:
    path = root / "res" / "pokemon" / "primeape" / "data.json"
    _write_json(
        path,
        {
            "base_stats": {
                "hp": 65,
                "attack": 105,
                "defense": 60,
                "speed": 95,
                "special_attack": 60,
                "special_defense": 70,
            },
            "types": ["TYPE_FIGHTING", "TYPE_FIGHTING"],
            "abilities": ["ABILITY_VITAL_SPIRIT", "ABILITY_ANGER_POINT"],
            "learnset": {"by_level": [[28, "MOVE_RAGE"], [35, "MOVE_SWAGGER"]]},
            "evolutions": [],
            "pokedex_data": {"en": {"name": "PRIMEAPE"}},
        },
        indent=4,
    )
    return path


def _ledger(root: Path) -> Path:
    path = root / "approved-ledger.json"
    _write_json(
        path,
        {
            "version": 1,
            "domain": "pokemon",
            "changes": [
                {
                    "species": "primeape",
                    "operation": "replace_level_move",
                    "from": [28, "MOVE_RAGE"],
                    "to": [29, "MOVE_BRICK_BREAK"],
                }
            ],
        },
    )
    return path


def test_source_ledger_cli_defaults_to_dry_run(tmp_path: Path, capsys) -> None:
    source = _species(tmp_path)
    ledger = _ledger(tmp_path)
    before = source.read_bytes()

    exit_code = main(["source-ledger", str(tmp_path), str(ledger)])

    assert exit_code == 0
    assert source.read_bytes() == before
    output = json.loads(capsys.readouterr().out)
    assert output["domain"] == "pokemon"
    assert output["applied"] is False
    assert output["file_count"] == 1
    assert output["files"][0]["source_path"] == "res/pokemon/primeape/data.json"
    assert output["files"][0]["changes"][0]["before"] == [28, "MOVE_RAGE"]
    assert output["files"][0]["changes"][0]["after"] == [29, "MOVE_BRICK_BREAK"]


def test_source_ledger_cli_requires_explicit_apply_to_write(tmp_path: Path, capsys) -> None:
    source = _species(tmp_path)
    ledger = _ledger(tmp_path)

    exit_code = main(["source-ledger", str(tmp_path), str(ledger), "--apply"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["applied"] is True
    data = json.loads(source.read_text(encoding="utf-8"))
    assert data["learnset"]["by_level"][0] == [29, "MOVE_BRICK_BREAK"]
