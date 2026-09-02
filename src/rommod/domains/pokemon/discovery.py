"""Read-only discovery for Pokémon decomp source files."""

from __future__ import annotations

from pathlib import Path


def _discover_data_files(root: Path, collection: str) -> list[Path]:
    resolved_root = root.resolve()
    paths = [
        path
        for path in (resolved_root / "res" / collection).glob("*/data.json")
        if path.is_file()
    ]
    return sorted(paths, key=lambda path: path.relative_to(resolved_root).as_posix().casefold())


def discover_species_files(root: Path) -> list[Path]:
    """Return existing `res/pokemon/*/data.json` files in deterministic order."""

    return _discover_data_files(root, "pokemon")


def discover_move_files(root: Path) -> list[Path]:
    """Return existing `res/moves/*/data.json` files in deterministic order."""

    return _discover_data_files(root, "moves")
