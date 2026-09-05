"""Configured emulator launch workflow for developer testing."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rommod.errors import RomModError


@dataclass(frozen=True)
class EmulatorTestPlan:
    root: Path
    rom: Path
    savestate: Path | None
    command: tuple[str, ...]


@dataclass(frozen=True)
class EmulatorLaunchResult:
    plan: EmulatorTestPlan
    pid: int


def _inside_root(root: Path, raw: str, label: str) -> Path:
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RomModError(f"{label} is outside project root: {raw}") from exc
    return candidate


def _load_config(root: Path) -> dict[str, object]:
    path = root / "rommod" / "emulator.json"
    if not path.is_file():
        raise RomModError(f"emulator config not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RomModError(f"invalid emulator config: {path}") from exc
    if not isinstance(payload, dict):
        raise RomModError("emulator config must contain a JSON object")
    return payload


def prepare_emulator_test(root: Path) -> EmulatorTestPlan:
    """Resolve and validate an emulator command without launching it."""

    root = Path(root).resolve()
    if not root.is_dir():
        raise RomModError(f"project root does not exist: {root}")

    config = _load_config(root)

    raw_command = config.get("command")
    if (
        not isinstance(raw_command, list)
        or not raw_command
        or any(not isinstance(part, str) or not part for part in raw_command)
    ):
        raise RomModError("emulator config 'command' must be a non-empty list of strings")

    raw_rom = config.get("rom")
    if not isinstance(raw_rom, str) or not raw_rom:
        raise RomModError("emulator config requires a project-relative 'rom' path")
    rom = _inside_root(root, raw_rom, "ROM path")
    if not rom.is_file():
        raise RomModError(f"configured ROM does not exist: {rom}")

    raw_state = config.get("savestate")
    savestate: Path | None = None
    if raw_state is not None:
        if not isinstance(raw_state, str) or not raw_state:
            raise RomModError("emulator config 'savestate' must be a project-relative path")
        savestate = _inside_root(root, raw_state, "savestate path")
        if not savestate.is_file():
            raise RomModError(f"configured savestate does not exist: {savestate}")

    command: list[str] = []
    for part in raw_command:
        assert isinstance(part, str)
        expanded = part.replace("{rom}", str(rom))
        if "{savestate}" in expanded:
            if savestate is None:
                raise RomModError("emulator command references {savestate} but no savestate is configured")
            expanded = expanded.replace("{savestate}", str(savestate))
        command.append(expanded)

    if not any("{rom}" in part for part in raw_command):
        raise RomModError("emulator command must include the {rom} placeholder")

    return EmulatorTestPlan(
        root=root,
        rom=rom,
        savestate=savestate,
        command=tuple(command),
    )


def launch_emulator_test(root: Path) -> EmulatorLaunchResult:
    """Launch the configured emulator command directly, never through a shell."""

    plan = prepare_emulator_test(root)
    try:
        process = subprocess.Popen(
            plan.command,
            cwd=plan.root,
            shell=False,
        )
    except OSError as exc:
        raise RomModError(f"failed to launch emulator command: {plan.command[0]}") from exc
    return EmulatorLaunchResult(plan=plan, pid=process.pid)
