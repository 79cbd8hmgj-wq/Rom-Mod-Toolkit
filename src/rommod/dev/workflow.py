"""One-command source-project developer cycle."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rommod.core.atomic import atomic_write_bytes
from rommod.dev.build import build_source_project
from rommod.dev.emulator import launch_emulator_test, prepare_emulator_test
from rommod.domains.pokemon.ledger import apply_ledger, load_ledger
from rommod.domains.pokemon.validation import validate_repository
from rommod.errors import BuildError, RomModError
from rommod.platforms.nds.validation import verify_rom


@dataclass(frozen=True)
class DevCycleResult:
    root: Path
    ledger_path: Path | None
    ledger_files: int
    source_validation: dict[str, object]
    outputs: tuple[str, ...]
    rom_verification: tuple[dict[str, object], ...]
    emulator: dict[str, object]
    report_path: Path

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "success": True,
            "root": str(self.root),
            "ledger": (
                {
                    "path": str(self.ledger_path),
                    "applied": True,
                    "file_count": self.ledger_files,
                }
                if self.ledger_path is not None
                else None
            ),
            "source_validation": self.source_validation,
            "outputs": list(self.outputs),
            "rom_verification": list(self.rom_verification),
            "emulator": self.emulator,
            "report": str(self.report_path),
        }


def _inside_root(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise BuildError(f"native build reported output outside project root: {relative}") from exc
    return candidate


def _emulator_payload(root: Path, mode: str) -> dict[str, object]:
    if mode == "none":
        return {"mode": "none", "launched": False}
    if mode == "dry-run":
        plan = prepare_emulator_test(root)
        return {
            "mode": "dry-run",
            "launched": False,
            "rom": str(plan.rom),
            "savestate": str(plan.savestate) if plan.savestate is not None else None,
            "command": list(plan.command),
        }
    if mode == "launch":
        launched = launch_emulator_test(root)
        return {
            "mode": "launch",
            "launched": True,
            "pid": launched.pid,
            "rom": str(launched.plan.rom),
            "savestate": (
                str(launched.plan.savestate)
                if launched.plan.savestate is not None
                else None
            ),
            "command": list(launched.plan.command),
        }
    raise RomModError(f"unsupported emulator mode: {mode}")


def _write_report(result: DevCycleResult) -> None:
    atomic_write_bytes(
        result.report_path,
        (json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )


def run_dev_cycle(
    root: Path,
    *,
    ledger_path: Path | None = None,
    emulator_mode: str = "none",
) -> DevCycleResult:
    """Apply an approved ledger, validate source, build, verify outputs, and optionally launch."""

    resolved = Path(root).resolve()
    if not resolved.is_dir():
        raise BuildError(f"source project does not exist: {resolved}")

    applied_ledger_path: Path | None = None
    ledger_files = 0
    if ledger_path is not None:
        applied_ledger_path = Path(ledger_path).resolve()
        ledger = load_ledger(applied_ledger_path)
        ledger_result = apply_ledger(resolved, ledger)
        ledger_files = len(ledger_result.files)

    validation = validate_repository(resolved)
    if not validation.valid:
        raise BuildError(
            f"source validation failed with {len(validation.issues)} issue(s); "
            "run 'rommod validate' for details"
        )

    build = build_source_project(resolved)
    verification_rows: list[dict[str, object]] = []
    for relative in build.outputs:
        output = _inside_root(resolved, relative)
        verification = verify_rom(output)
        verification_rows.append(
            {
                "output": relative,
                "valid": verification.valid,
                "checks": list(verification.checks),
            }
        )

    emulator = _emulator_payload(resolved, emulator_mode)
    report_path = resolved / "rommod" / "reports" / "dev.json"
    result = DevCycleResult(
        root=resolved,
        ledger_path=applied_ledger_path,
        ledger_files=ledger_files,
        source_validation=validation.to_dict(),
        outputs=build.outputs,
        rom_verification=tuple(verification_rows),
        emulator=emulator,
        report_path=report_path,
    )
    _write_report(result)
    return result
