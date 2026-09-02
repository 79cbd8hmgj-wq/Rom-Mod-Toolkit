"""Read-only project reconnaissance with explicit metadata reporting."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rommod.core.atomic import atomic_write_bytes
from rommod.errors import RomModError


_BUILD_FILES = ("Makefile", "makefile", "GNUmakefile")
_TOOLCHAIN_MARKERS = (("arm-none-eabi", "arm-none-eabi"),)


@dataclass(frozen=True)
class ProjectScanReport:
    """Deterministic description of an existing ROM modification project."""

    root: Path
    platform: str
    project_type: str
    build_system: str | None
    toolchains: tuple[str, ...]
    systems_detected: dict[str, bool]
    rom_outputs: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "platform": self.platform,
            "project_type": self.project_type,
            "build_system": self.build_system,
            "toolchains": list(self.toolchains),
            "systems_detected": dict(self.systems_detected),
            "rom_outputs": list(self.rom_outputs),
        }


def _data_files(root: Path, collection: str) -> tuple[Path, ...]:
    directory = root / "res" / collection
    if not directory.is_dir():
        return ()
    return tuple(
        sorted(
            (path for path in directory.glob("*/data.json") if path.is_file()),
            key=lambda path: path.relative_to(root).as_posix().casefold(),
        )
    )


def _has_evolution_schema(root: Path, species_files: tuple[Path, ...]) -> bool:
    if (root / "res" / "evolutions").exists():
        return True
    for path in species_files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and "evolutions" in payload:
            return True
    return False


def _detect_build_system(root: Path) -> tuple[str | None, tuple[Path, ...]]:
    build_files = tuple(root / name for name in _BUILD_FILES if (root / name).is_file())
    return ("make" if build_files else None, build_files)


def _detect_toolchains(build_files: tuple[Path, ...]) -> tuple[str, ...]:
    text_parts: list[str] = []
    for path in build_files:
        try:
            text_parts.append(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    build_text = "\n".join(text_parts)
    found = [name for marker, name in _TOOLCHAIN_MARKERS if marker in build_text]
    return tuple(sorted(set(found), key=str.casefold))


def _discover_rom_outputs(root: Path) -> tuple[str, ...]:
    outputs = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*.nds")
        if path.is_file()
    ]
    return tuple(sorted(outputs, key=str.casefold))


def scan_project(root: Path) -> ProjectScanReport:
    """Inspect a project without modifying it."""

    resolved = Path(root).resolve()
    if not resolved.is_dir():
        raise RomModError(f"project root does not exist or is not a directory: {resolved}")

    species_files = _data_files(resolved, "pokemon")
    move_files = _data_files(resolved, "moves")
    systems = {
        "pokemon": bool(species_files),
        "moves": bool(move_files),
        "evolutions": _has_evolution_schema(resolved, species_files),
        "trainers": (resolved / "res" / "trainers").exists(),
        "items": (resolved / "res" / "items").exists(),
        "text": (resolved / "res" / "text").exists(),
    }
    pokemon_decomp = systems["pokemon"] and systems["moves"]
    rom_outputs = _discover_rom_outputs(resolved)
    platform = "nds" if pokemon_decomp or rom_outputs else "unknown"
    project_type = "pokemon_decomp" if pokemon_decomp else ("nds_project" if platform == "nds" else "unknown")
    build_system, build_files = _detect_build_system(resolved)

    return ProjectScanReport(
        root=resolved,
        platform=platform,
        project_type=project_type,
        build_system=build_system,
        toolchains=_detect_toolchains(build_files),
        systems_detected=systems,
        rom_outputs=rom_outputs,
    )


def _json_bytes(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_scan_reports(report: ProjectScanReport) -> tuple[Path, Path]:
    """Persist reusable project metadata and the full scan report atomically."""

    metadata_root = report.root / "rommod"
    project_path = metadata_root / "project.json"
    report_path = metadata_root / "reports" / "project_scan.json"

    project_payload: dict[str, object] = {
        "schema_version": 1,
        "platform": report.platform,
        "project_type": report.project_type,
        "build_system": report.build_system,
        "toolchains": list(report.toolchains),
    }
    atomic_write_bytes(project_path, _json_bytes(project_payload))
    atomic_write_bytes(report_path, _json_bytes(report.to_dict()))
    return project_path, report_path
