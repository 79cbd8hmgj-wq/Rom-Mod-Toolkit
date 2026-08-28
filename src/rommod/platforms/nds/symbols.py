"""Component-aware symbol interchange for NDS analysis output."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rommod.errors import ManifestError


_VALID_INSTRUCTION_SETS = {None, "arm", "thumb"}


@dataclass(frozen=True)
class ImportedSymbol:
    component: str
    address: int
    offset: int
    name: str
    kind: str
    instruction_set: str | None
    confidence: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class ImportedSymbolTable:
    symbols: tuple[ImportedSymbol, ...]

    def by_name(self, name: str, *, component: str | None = None) -> tuple[ImportedSymbol, ...]:
        return tuple(
            symbol
            for symbol in self.symbols
            if symbol.name == name and (component is None or symbol.component == component)
        )

    def for_component(self, component: str) -> tuple[ImportedSymbol, ...]:
        return tuple(symbol for symbol in self.symbols if symbol.component == component)


def _required_str(record: dict, key: str, field: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{field}.{key} must be a non-empty string")
    return value


def _required_int(record: dict, key: str, field: str, *, maximum: int | None = None) -> int:
    value = record.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ManifestError(f"{field}.{key} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise ManifestError(f"{field}.{key} exceeds 0x{maximum:X}")
    return value


def _parse_record(value: object, index: int) -> ImportedSymbol:
    field = f"symbols[{index}]"
    if not isinstance(value, dict):
        raise ManifestError(f"{field} must be a mapping")
    instruction_set = value.get("instruction_set")
    if instruction_set not in _VALID_INSTRUCTION_SETS:
        raise ManifestError(f"{field}.instruction_set must be 'arm', 'thumb', or null")
    kind = value.get("kind", "named")
    if not isinstance(kind, str) or not kind:
        raise ManifestError(f"{field}.kind must be a non-empty string")
    confidence = value.get("confidence", "unknown")
    if not isinstance(confidence, str) or not confidence:
        raise ManifestError(f"{field}.confidence must be a non-empty string")
    raw_evidence = value.get("evidence", [])
    if not isinstance(raw_evidence, list) or any(not isinstance(item, str) for item in raw_evidence):
        raise ManifestError(f"{field}.evidence must be a list of strings")
    return ImportedSymbol(
        component=_required_str(value, "component", field),
        address=_required_int(value, "address", field, maximum=0xFFFFFFFF),
        offset=_required_int(value, "offset", field),
        name=_required_str(value, "name", field),
        kind=kind,
        instruction_set=instruction_set,
        confidence=confidence,
        evidence=tuple(raw_evidence),
    )


def load_symbol_table(path: Path) -> ImportedSymbolTable:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"Symbol file not found: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Invalid JSON in symbol file {source}: {exc}") from exc

    if isinstance(raw, dict):
        raw_symbols = raw.get("symbols")
    else:
        raw_symbols = raw
    if not isinstance(raw_symbols, list):
        raise ManifestError("Symbol file must be a JSON array or an object containing a symbols array")
    return ImportedSymbolTable(tuple(_parse_record(value, index) for index, value in enumerate(raw_symbols)))
