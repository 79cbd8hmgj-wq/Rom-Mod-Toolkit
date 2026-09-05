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


def test_set_base_stat_is_exact_guarded_and_preserves_unrelated_data(tmp_path: Path) -> None:
    source = _write_species(tmp_path, "golem", [[35, "MOVE_ROCK_BLAST"]])
    digest = _digest(source)
    ledger = load_ledger(
        _ledger_file(
            tmp_path,
            {
                "version": 1,
                "domain": "pokemon",
                "changes": [
                    {
                        "species": "golem",
                        "source_sha256": digest,
                        "operation": "set_base_stat",
                        "stat": "attack",
                        "from": 80,
                        "to": 120,
                    }
                ],
            },
        )
    )

    plan = plan_ledger(tmp_path, ledger)
    planned = plan.files[0].changes[0]
    assert planned.operation == "set_base_stat"
    assert planned.field == "attack"
    assert planned.before == 80
    assert planned.after == 120

    apply_ledger(tmp_path, ledger)
    data = json.loads(source.read_text(encoding="utf-8"))
    assert data["base_stats"]["attack"] == 120
    assert data["base_stats"]["hp"] == 60
    assert data["learnset"]["by_level"] == [[35, "MOVE_ROCK_BLAST"]]


def test_set_types_and_abilities_use_exact_whole_field_guards(tmp_path: Path) -> None:
    source = _write_species(tmp_path, "persian", [[25, "MOVE_TAUNT"]])
    digest = _digest(source)
    ledger = load_ledger(
        _ledger_file(
            tmp_path,
            {
                "version": 1,
                "domain": "pokemon",
                "changes": [
                    {
                        "species": "persian",
                        "source_sha256": digest,
                        "operation": "set_types",
                        "from": ["TYPE_NORMAL", "TYPE_NORMAL"],
                        "to": ["TYPE_NORMAL"],
                    },
                    {
                        "species": "persian",
                        "source_sha256": digest,
                        "operation": "set_abilities",
                        "from": ["ABILITY_NONE", "ABILITY_NONE"],
                        "to": ["ABILITY_LIMBER", "ABILITY_TECHNICIAN"],
                    },
                ],
            },
        )
    )

    plan = plan_ledger(tmp_path, ledger)
    assert plan.files[0].changes[0].before == ("TYPE_NORMAL", "TYPE_NORMAL")
    assert plan.files[0].changes[0].after == ("TYPE_NORMAL",)
    assert plan.files[0].changes[1].before == ("ABILITY_NONE", "ABILITY_NONE")
    assert plan.files[0].changes[1].after == ("ABILITY_LIMBER", "ABILITY_TECHNICIAN")

    apply_ledger(tmp_path, ledger)
    data = json.loads(source.read_text(encoding="utf-8"))
    assert data["types"] == ["TYPE_NORMAL"]
    assert data["abilities"] == ["ABILITY_LIMBER", "ABILITY_TECHNICIAN"]


def test_mixed_multi_file_ledger_preflights_stat_mismatch_before_any_write(tmp_path: Path) -> None:
    persian = _write_species(tmp_path, "persian", [[25, "MOVE_TAUNT"]])
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
                        "operation": "set_base_stat",
                        "stat": "speed",
                        "from": 80,
                        "to": 115,
                    },
                    {
                        "species": "primeape",
                        "source_sha256": _digest(primeape),
                        "operation": "set_base_stat",
                        "stat": "attack",
                        "from": 81,
                        "to": 115,
                    },
                ],
            },
        )
    )

    with pytest.raises(RomModError, match="base_stats.attack"):
        apply_ledger(tmp_path, ledger)

    assert persian.read_bytes() == persian_before
