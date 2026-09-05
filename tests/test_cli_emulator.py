from __future__ import annotations

import json
from pathlib import Path

from rommod.cli import main


def test_test_command_can_dry_run_emulator_plan(tmp_path: Path, capsys) -> None:
    rom = tmp_path / "build" / "game.nds"
    rom.parent.mkdir()
    rom.write_bytes(b"NDS")
    config = tmp_path / "rommod" / "emulator.json"
    config.parent.mkdir()
    config.write_text(
        json.dumps({"command": ["emu", "{rom}"], "rom": "build/game.nds"}),
        encoding="utf-8",
    )

    assert main(["test", str(tmp_path), "--dry-run"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["launched"] is False
    assert payload["rom"] == str(rom.resolve())
    assert payload["command"] == ["emu", str(rom.resolve())]
