from __future__ import annotations

import json
from pathlib import Path

import pytest

from rommod.dev.emulator import launch_emulator_test, prepare_emulator_test
from rommod.errors import RomModError


def _write_config(root: Path, payload: dict[str, object]) -> None:
    path = root / "rommod" / "emulator.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_prepare_emulator_test_expands_rom_and_savestate_tokens(tmp_path: Path) -> None:
    rom = tmp_path / "build" / "game.nds"
    rom.parent.mkdir()
    rom.write_bytes(b"NDS")
    state = tmp_path / "test_states" / "evolution.state"
    state.parent.mkdir()
    state.write_bytes(b"STATE")
    _write_config(
        tmp_path,
        {
            "command": ["melonDS", "--load-state", "{savestate}", "{rom}"],
            "rom": "build/game.nds",
            "savestate": "test_states/evolution.state",
        },
    )

    plan = prepare_emulator_test(tmp_path)

    assert plan.rom == rom.resolve()
    assert plan.savestate == state.resolve()
    assert plan.command == (
        "melonDS",
        "--load-state",
        str(state.resolve()),
        str(rom.resolve()),
    )


def test_prepare_rejects_paths_that_escape_project(tmp_path: Path) -> None:
    _write_config(tmp_path, {"command": ["emu", "{rom}"], "rom": "../game.nds"})
    with pytest.raises(RomModError, match="outside project root"):
        prepare_emulator_test(tmp_path)


def test_launch_uses_prepared_command_without_shell(tmp_path: Path, monkeypatch) -> None:
    rom = tmp_path / "game.nds"
    rom.write_bytes(b"NDS")
    _write_config(tmp_path, {"command": ["emu", "{rom}"], "rom": "game.nds"})
    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 4321

    def fake_popen(command, *, cwd, shell):
        captured["command"] = tuple(command)
        captured["cwd"] = cwd
        captured["shell"] = shell
        return FakeProcess()

    monkeypatch.setattr("rommod.dev.emulator.subprocess.Popen", fake_popen)

    result = launch_emulator_test(tmp_path)

    assert result.pid == 4321
    assert captured["command"] == ("emu", str(rom.resolve()))
    assert captured["cwd"] == tmp_path.resolve()
    assert captured["shell"] is False
