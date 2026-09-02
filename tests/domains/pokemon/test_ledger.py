from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rommod.domains.pokemon.ledger import apply_ledger, load_ledger, plan_ledger
from rommod.errors import RomModError, SourceMismatchError


def _write_species(root: Path, identifier: str, learnset: list[list[object]]) -> Path:
    path = root / "res" / "pokemon" / identifier / "data.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "base_stats": {
                    "hp": 60,
                    "attack": 80,
                    "defense": 60,
                    "speed": 80,
                    "special_attack": 60,
                    "special_defense": 60,
                },
                "types": ["TYPE_NORMAL", "TYPE_NORMAL"],
                "abilities": ["ABILITY_NONE", "ABILITY_NONE"],
                "learnset": {
                    "by_level": learnset,
                    "by_tm": ["TM01"],
                    "by_tutor": ["MOVE_SWIFT"],
                },
                "evolutions": [],
                "pokedex_data": {"en": {"name": identifier.upper()}},
            },
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ledger_file(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def test_plan_replace_level_move_is_read_only_and_exact(tmp_path: Path) -> None:
    source = _write_species(tmp_path, "primeape", [[28, "MOVE_RAGE"], [35, "MOVE_SWAGGER"]])
    before = source.read_bytes()
    ledger = load_ledger(
        _ledger_file(
            tmp_path,
            {
                "version": 1,
                "domain": "pokemon",
                "changes": [
                    {
                        "species": "primeape",
                        "source_sha256": _digest(source),
                        "operation": "replace_level_move",
                        "from": [28, "MOVE_RAGE"],
                        "to": [29, "MOVE_BRICK_BREAK"],
                    }
                ],
            },
        )
    )

    plan = plan_ledger(tmp_path, ledger)

    assert source.read_bytes() == before
    assert len(plan.files) == 1
    change = plan.files[0].changes[0]
    assert change.species == "primeape"
    assert change.operation == "replace_level_move"
    assert change.before == (28, "MOVE_RAGE")
    assert change.after == (29, "MOVE_BRICK_BREAK")
    assert plan.files[0].source_path == Path("res/pokemon/primeape/data.json")


def test_apply_replace_preserves_unrelated_species_data(tmp_path: Path) -> None:
    source = _write_species(tmp_path, "primeape", [[28, "MOVE_RAGE"], [35, "MOVE_SWAGGER"]])
    ledger = load_ledger(
        _ledger_file(
            tmp_path,
            {
                "version": 1,
                "domain": "pokemon",
                "changes": [
                    {
                        "species": "primeape",
                        "source_sha256": _digest(source),
                        "operation": "replace_level_move",
                        "from": [28, "MOVE_RAGE"],
                        "to": [29, "MOVE_BRICK_BREAK"],
                    }
                ],
            },
        )
    )

    result = apply_ledger(tmp_path, ledger)
    data = json.loads(source.read_text(encoding="utf-8"))

    assert result.applied is True
    assert data["learnset"]["by_level"] == [[29, "MOVE_BRICK_BREAK"], [35, "MOVE_SWAGGER"]]
    assert data["learnset"]["by_tm"] == ["TM01"]
    assert data["learnset"]["by_tutor"] == ["MOVE_SWIFT"]
    assert data["base_stats"]["attack"] == 80


def test_apply_insert_orders_by_level_without_reordering_existing_same_level_entries(tmp_path: Path) -> None:
    source = _write_species(
        tmp_path,
        "persian",
        [[1, "MOVE_SWITCHEROO"], [1, "MOVE_SCRATCH"], [25, "MOVE_TAUNT"], [32, "MOVE_POWER_GEM"]],
    )
    ledger = load_ledger(
        _ledger_file(
            tmp_path,
            {
                "version": 1,
                "domain": "pokemon",
                "changes": [
                    {
                        "species": "persian",
                        "source_sha256": _digest(source),
                        "operation": "insert_level_move",
                        "entry": [29, "MOVE_SWITCHEROO"],
                    }
                ],
            },
        )
    )

    apply_ledger(tmp_path, ledger)
    learnset = json.loads(source.read_text(encoding="utf-8"))["learnset"]["by_level"]

    assert learnset == [
        [1, "MOVE_SWITCHEROO"],
        [1, "MOVE_SCRATCH"],
        [25, "MOVE_TAUNT"],
        [29, "MOVE_SWITCHEROO"],
        [32, "MOVE_POWER_GEM"],
    ]


def test_duplicate_insert_is_rejected(tmp_path: Path) -> None:
    _write_species(tmp_path, "persian", [[29, "MOVE_SWITCHEROO"]])
    ledger = load_ledger(
        _ledger_file(
            tmp_path,
            {
                "version": 1,
                "domain": "pokemon",
                "changes": [
                    {
                        "species": "persian",
                        "operation": "insert_level_move",
                        "entry": [29, "MOVE_SWITCHEROO"],
                    }
                ],
            },
        )
    )

    with pytest.raises(RomModError, match="already contains"):
        plan_ledger(tmp_path, ledger)


def test_source_sha_mismatch_is_rejected_before_write(tmp_path: Path) -> None:
    source = _write_species(tmp_path, "primeape", [[28, "MOVE_RAGE"]])
    before = source.read_bytes()
    ledger = load_ledger(
        _ledger_file(
            tmp_path,
            {
                "version": 1,
                "domain": "pokemon",
                "changes": [
                    {
                        "species": "primeape",
                        "source_sha256": "0" * 64,
                        "operation": "replace_level_move",
                        "from": [28, "MOVE_RAGE"],
                        "to": [29, "MOVE_BRICK_BREAK"],
                    }
                ],
            },
        )
    )

    with pytest.raises(SourceMismatchError, match="primeape"):
        apply_ledger(tmp_path, ledger)
    assert source.read_bytes() == before


def test_apply_requires_every_target_to_be_sha_pinned(tmp_path: Path) -> None:
    source = _write_species(tmp_path, "primeape", [[28, "MOVE_RAGE"]])
    before = source.read_bytes()
    ledger = load_ledger(
        _ledger_file(
            tmp_path,
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
    )

    assert plan_ledger(tmp_path, ledger).applied is False
    with pytest.raises(SourceMismatchError, match="source_sha256"):
        apply_ledger(tmp_path, ledger)
    assert source.read_bytes() == before


def test_all_files_preflight_before_any_write(tmp_path: Path) -> None:
    persian = _write_species(tmp_path, "persian", [[25, "MOVE_TAUNT"], [32, "MOVE_POWER_GEM"]])
    primeape = _write_species(tmp_path, "primeape", [[28, "MOVE_RAGE"]])
    persian_before = persian.read_bytes()
    ledger = load_ledger(
        _ledger_file(
            tmp_path,
            {
                "version": 1,
                "domain": "pokemon",
                "changes": [
                    {
                        "species": "persian",
                        "source_sha256": _digest(persian),
                        "operation": "insert_level_move",
                        "entry": [29, "MOVE_SWITCHEROO"],
                    },
                    {
                        "species": "primeape",
                        "source_sha256": _digest(primeape),
                        "operation": "replace_level_move",
                        "from": [27, "MOVE_RAGE"],
                        "to": [29, "MOVE_BRICK_BREAK"],
                    },
                ],
            },
        )
    )

    with pytest.raises(RomModError, match="expected learnset entry"):
        apply_ledger(tmp_path, ledger)

    assert persian.read_bytes() == persian_before
