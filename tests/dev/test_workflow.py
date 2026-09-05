from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rommod.dev.build import SourceBuildResult
from rommod.dev.emulator import EmulatorTestPlan
from rommod.dev.workflow import run_dev_cycle
from rommod.errors import BuildError


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _seed_valid_repo(root: Path, *, attack: int = 105) -> Path:
    species = root / "res" / "pokemon" / "primeape" / "data.json"
    _write_json(
        species,
        {
            "base_stats": {
                "hp": 70,
                "attack": attack,
                "defense": 65,
                "special_attack": 50,
                "special_defense": 70,
                "speed": 110,
            },
            "types": ["TYPE_FIGHTING"],
            "abilities": ["ABILITY_VITAL_SPIRIT"],
            "learnset": {"by_level": []},
            "evolutions": [],
            "pokedex_data": {"en": {"name": "PRIMEAPE"}},
        },
    )
    _write_json(
        root / "res" / "moves" / "tackle" / "data.json",
        {
            "name": "Tackle",
            "type": "TYPE_NORMAL",
            "class": "CLASS_PHYSICAL",
            "power": 40,
            "accuracy": 100,
            "pp": 35,
        },
    )
    return species


def _fake_build(root: Path) -> SourceBuildResult:
    output = root / "build" / "game.nds"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"fake-nds")
    return SourceBuildResult(
        root=root.resolve(),
        build_system="make",
        command=("make",),
        outputs=("build/game.nds",),
        report_path=root / "rommod" / "reports" / "build.json",
    )


class _Verification:
    valid = True
    checks = ("header", "fresh_parse")


def test_dev_cycle_can_apply_pinned_ledger_then_validate_build_and_verify(
    tmp_path: Path,
    monkeypatch,
) -> None:
    species = _seed_valid_repo(tmp_path)
    digest = hashlib.sha256(species.read_bytes()).hexdigest()
    ledger = tmp_path / "approved.json"
    _write_json(
        ledger,
        {
            "version": 1,
            "domain": "pokemon",
            "changes": [
                {
                    "species": "primeape",
                    "source_sha256": digest,
                    "operation": "set_base_stat",
                    "stat": "attack",
                    "from": 105,
                    "to": 115,
                }
            ],
        },
    )
    verified: list[Path] = []

    monkeypatch.setattr("rommod.dev.workflow.build_source_project", _fake_build)
    monkeypatch.setattr(
        "rommod.dev.workflow.verify_rom",
        lambda path: verified.append(Path(path)) or _Verification(),
    )

    result = run_dev_cycle(tmp_path, ledger_path=ledger)

    data = json.loads(species.read_text(encoding="utf-8"))
    assert data["base_stats"]["attack"] == 115
    assert result.ledger_files == 1
    assert result.outputs == ("build/game.nds",)
    assert verified == [tmp_path / "build" / "game.nds"]
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["success"] is True
    assert report["ledger"]["file_count"] == 1
    assert report["rom_verification"][0]["checks"] == ["header", "fresh_parse"]


def test_dev_cycle_stops_before_build_when_source_validation_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    species = _seed_valid_repo(tmp_path)
    payload = json.loads(species.read_text(encoding="utf-8"))
    payload["learnset"]["by_level"] = [[10, "MOVE_DOES_NOT_EXIST"]]
    _write_json(species, payload)

    called = False

    def fail_if_built(root: Path):
        nonlocal called
        called = True
        return _fake_build(root)

    monkeypatch.setattr("rommod.dev.workflow.build_source_project", fail_if_built)

    with pytest.raises(BuildError, match="source validation failed"):
        run_dev_cycle(tmp_path)

    assert called is False


def test_dev_cycle_can_prepare_emulator_without_launching(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _seed_valid_repo(tmp_path)
    monkeypatch.setattr("rommod.dev.workflow.build_source_project", _fake_build)
    monkeypatch.setattr("rommod.dev.workflow.verify_rom", lambda path: _Verification())
    plan = EmulatorTestPlan(
        root=tmp_path.resolve(),
        rom=(tmp_path / "build" / "game.nds").resolve(),
        savestate=None,
        command=("melonDS", str((tmp_path / "build" / "game.nds").resolve())),
    )
    monkeypatch.setattr("rommod.dev.workflow.prepare_emulator_test", lambda root: plan)

    result = run_dev_cycle(tmp_path, emulator_mode="dry-run")

    assert result.emulator["mode"] == "dry-run"
    assert result.emulator["launched"] is False
    assert result.emulator["command"] == list(plan.command)
