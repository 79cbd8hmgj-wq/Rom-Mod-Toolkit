from __future__ import annotations

from pathlib import Path

from rommod.cli import main


def test_cli_reports_toolkit_error_without_traceback(tmp_path: Path, capsys):
    missing = tmp_path / "missing.nds"
    assert main(["verify", str(missing)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error: NDS ROM is missing" in captured.err
    assert "Traceback" not in captured.err


def test_cli_end_to_end_untouched_project(synthetic_rom_path: Path, tmp_path: Path, capsys):
    project = tmp_path / "mod"

    assert main(["init", str(synthetic_rom_path), str(project)]) == 0
    assert main(["inspect", str(project)]) == 0
    assert main(["extract", str(project)]) == 0
    assert main(["build", str(project)]) == 0
    assert main(["verify", str(project)]) == 0

    captured = capsys.readouterr()
    assert "Initialized" in captured.out
    assert '"game_code": "TST1"' in captured.out
    assert '"valid": true' in captured.out
    assert (project / "build/output/synthetic-modded.nds").is_file()
    assert (project / "reports/build.json").is_file()
    assert (project / "build/extracted/arm9.bin").is_file()
