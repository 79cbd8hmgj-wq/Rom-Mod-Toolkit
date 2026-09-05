from __future__ import annotations

import json
from pathlib import Path

from rommod.cli import main


class _Result:
    def __init__(self, root: Path) -> None:
        self._root = root

    def to_dict(self) -> dict[str, object]:
        return {
            "success": True,
            "root": str(self._root.resolve()),
            "outputs": ["build/game.nds"],
            "emulator": {"mode": "dry-run", "launched": False},
        }


def test_dev_cli_forwards_ledger_and_emulator_mode(tmp_path: Path, capsys, monkeypatch) -> None:
    ledger = tmp_path / "approved.json"
    ledger.write_text("{}\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(root: Path, *, ledger_path: Path | None, emulator_mode: str):
        captured["root"] = root
        captured["ledger_path"] = ledger_path
        captured["emulator_mode"] = emulator_mode
        return _Result(root)

    monkeypatch.setattr("rommod.cli.run_dev_cycle", fake_run)

    assert (
        main(
            [
                "dev",
                str(tmp_path),
                "--ledger",
                str(ledger),
                "--dry-run-emulator",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert captured["root"] == tmp_path
    assert captured["ledger_path"] == ledger
    assert captured["emulator_mode"] == "dry-run"
