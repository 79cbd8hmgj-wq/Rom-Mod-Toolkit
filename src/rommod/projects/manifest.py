"""ROM mod project manifest model and YAML codec."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeAlias

import yaml

from rommod.errors import ManifestError


_HEX = set("0123456789abcdef")


@dataclass(frozen=True)
class SourceConfig:
    rom: str
    sha256: str


@dataclass(frozen=True)
class OutputConfig:
    rom: str


@dataclass(frozen=True)
class ToolsConfig:
    armips: str | None = None
    clang: str | None = None
    ld_lld: str | None = None
    llvm_objcopy: str | None = None


@dataclass(frozen=True)
class FileReplaceChange:
    target: str
    source: str
    type: Literal["file_replace"] = "file_replace"


@dataclass(frozen=True)
class BytePatchChange:
    target: str
    offset: int
    expected: bytes
    replacement: bytes
    type: Literal["byte_patch"] = "byte_patch"


@dataclass(frozen=True)
class ArmipsChange:
    target: str
    script: str
    symbols: str | None = None
    symbol_file: str | None = None
    symbol_component: str | None = None
    type: Literal["armips"] = "armips"


@dataclass(frozen=True)
class InjectChange:
    target: str
    symbol_file: str
    hook: str
    expected: bytes
    script: str
    cave: str | int
    reserve: int
    fill: int = 0
    symbols: str | None = None
    symbol_component: str | None = None
    scratch_register: str | None = None
    type: Literal["inject"] = "inject"


@dataclass(frozen=True)
class CInjectChange:
    target: str
    symbol_file: str
    hook: str
    expected: bytes
    source: str | None
    cave: str | int
    reserve: int
    fill: int = 0
    symbol_component: str | None = None
    scratch_register: str | None = None
    sources: tuple[str, ...] = ()
    type: Literal["c_inject"] = "c_inject"


Change: TypeAlias = FileReplaceChange | BytePatchChange | ArmipsChange | InjectChange | CInjectChange


@dataclass(frozen=True)
class ProjectManifest:
    schema_version: int
    platform: Literal["nds"]
    source: SourceConfig
    output: OutputConfig
    changes: tuple[Change, ...] = ()
    tools: ToolsConfig = field(default_factory=ToolsConfig)


def _require_mapping(value: object, field: str) -> dict:
    if not isinstance(value, dict):
        raise ManifestError(f"{field} must be a mapping")
    return value


def _require_str(mapping: dict, key: str, field: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{field}.{key} must be a non-empty string")
    return value


def _optional_str(mapping: dict, key: str, field: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{field}.{key} must be a non-empty string when provided")
    return value


def _parse_sha256(value: str) -> str:
    lowered = value.lower()
    if len(lowered) != 64 or any(ch not in _HEX for ch in lowered):
        raise ManifestError("source.sha256 must be 64 hexadecimal characters")
    return lowered


def _parse_offset(value: object, field: str) -> int:
    if isinstance(value, int):
        result = value
    elif isinstance(value, str):
        try:
            result = int(value, 0)
        except ValueError as exc:
            raise ManifestError(f"{field} must be an integer or 0x-prefixed integer") from exc
    else:
        raise ManifestError(f"{field} must be an integer or 0x-prefixed integer")
    if result < 0:
        raise ManifestError(f"{field} must be non-negative")
    return result


def _parse_hex_bytes(value: object, field: str) -> bytes:
    if not isinstance(value, str):
        raise ManifestError(f"{field} must be a hexadecimal byte string")
    compact = "".join(value.split())
    if len(compact) % 2 or any(ch.lower() not in _HEX for ch in compact):
        raise ManifestError(f"{field} must contain complete hexadecimal bytes")
    return bytes.fromhex(compact)


def _parse_positive_int(value: object, field: str) -> int:
    result = _parse_offset(value, field)
    if result <= 0:
        raise ManifestError(f"{field} must be positive")
    return result


def _parse_fill_byte(value: object, field: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        result = value
    elif isinstance(value, str):
        compact = value.strip().lower().removeprefix("0x")
        if len(compact) != 2 or any(ch not in _HEX for ch in compact):
            raise ManifestError(f"{field} must be one hexadecimal byte")
        result = int(compact, 16)
    else:
        raise ManifestError(f"{field} must be an integer byte or two-digit hex string")
    if result < 0 or result > 0xFF:
        raise ManifestError(f"{field} must be between 0 and 255")
    return result


def _parse_cave(value: object, field: str) -> str | int:
    if value == "auto":
        return "auto"
    return _parse_offset(value, field)


def _parse_c_sources(mapping: dict, field: str) -> tuple[str | None, tuple[str, ...]]:
    has_source = "source" in mapping
    has_sources = "sources" in mapping
    if has_source == has_sources:
        raise ManifestError(f"{field} must provide exactly one of source or sources")
    if has_source:
        return _require_str(mapping, "source", field), ()

    raw_sources = mapping.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ManifestError(f"{field}.sources must be a non-empty list of strings")
    parsed: list[str] = []
    for source_index, item in enumerate(raw_sources):
        if not isinstance(item, str) or not item:
            raise ManifestError(f"{field}.sources[{source_index}] must be a non-empty string")
        parsed.append(item)
    return None, tuple(parsed)


def _parse_change(value: object, index: int) -> Change:
    field = f"changes[{index}]"
    mapping = _require_mapping(value, field)
    kind = mapping.get("type")
    if kind == "file_replace":
        return FileReplaceChange(
            target=_require_str(mapping, "target", field),
            source=_require_str(mapping, "source", field),
        )
    if kind == "byte_patch":
        return BytePatchChange(
            target=_require_str(mapping, "target", field),
            offset=_parse_offset(mapping.get("offset"), f"{field}.offset"),
            expected=_parse_hex_bytes(mapping.get("expected"), f"{field}.expected"),
            replacement=_parse_hex_bytes(mapping.get("replacement"), f"{field}.replacement"),
        )
    if kind == "armips":
        return ArmipsChange(
            target=_require_str(mapping, "target", field),
            script=_require_str(mapping, "script", field),
            symbols=_optional_str(mapping, "symbols", field),
            symbol_file=_optional_str(mapping, "symbol_file", field),
            symbol_component=_optional_str(mapping, "symbol_component", field),
        )
    if kind == "c_inject":
        expected = _parse_hex_bytes(mapping.get("expected"), f"{field}.expected")
        if len(expected) not in (2, 4, 8):
            raise ManifestError(
                f"{field}.expected must contain 2 bytes (Thumb short), "
                "4 bytes (ARM), or 8 bytes (Thumb long)"
            )
        reserve = _parse_positive_int(mapping.get("reserve"), f"{field}.reserve")
        if reserve % 4:
            raise ManifestError(f"{field}.reserve must be a multiple of 4")
        source, sources = _parse_c_sources(mapping, field)
        return CInjectChange(
            target=_require_str(mapping, "target", field),
            symbol_file=_require_str(mapping, "symbol_file", field),
            hook=_require_str(mapping, "hook", field),
            expected=expected,
            source=source,
            cave=_parse_cave(mapping.get("cave"), f"{field}.cave"),
            reserve=reserve,
            fill=_parse_fill_byte(mapping.get("fill", "00"), f"{field}.fill"),
            symbol_component=_optional_str(mapping, "symbol_component", field),
            scratch_register=_optional_str(mapping, "scratch_register", field),
            sources=sources,
        )
    if kind == "inject":
        expected = _parse_hex_bytes(mapping.get("expected"), f"{field}.expected")
        if len(expected) not in (2, 4, 8):
            raise ManifestError(
                f"{field}.expected must contain 2 bytes (Thumb short), "
                "4 bytes (ARM), or 8 bytes (Thumb long)"
            )
        reserve = _parse_positive_int(mapping.get("reserve"), f"{field}.reserve")
        if reserve % 4:
            raise ManifestError(f"{field}.reserve must be a multiple of 4")
        return InjectChange(
            target=_require_str(mapping, "target", field),
            symbol_file=_require_str(mapping, "symbol_file", field),
            hook=_require_str(mapping, "hook", field),
            expected=expected,
            script=_require_str(mapping, "script", field),
            cave=_parse_cave(mapping.get("cave"), f"{field}.cave"),
            reserve=reserve,
            fill=_parse_fill_byte(mapping.get("fill", "00"), f"{field}.fill"),
            symbols=_optional_str(mapping, "symbols", field),
            symbol_component=_optional_str(mapping, "symbol_component", field),
            scratch_register=_optional_str(mapping, "scratch_register", field),
        )
    raise ManifestError(f"{field}.type is unsupported: {kind!r}")


def _from_mapping(data: object) -> ProjectManifest:
    root = _require_mapping(data, "manifest")
    schema_version = root.get("schema_version")
    if schema_version != 1:
        raise ManifestError(f"schema_version must be 1, got {schema_version!r}")
    platform = root.get("platform")
    if platform != "nds":
        raise ManifestError(f"platform must be 'nds', got {platform!r}")

    source_map = _require_mapping(root.get("source"), "source")
    source = SourceConfig(
        rom=_require_str(source_map, "rom", "source"),
        sha256=_parse_sha256(_require_str(source_map, "sha256", "source")),
    )
    output_map = _require_mapping(root.get("output"), "output")
    output = OutputConfig(rom=_require_str(output_map, "rom", "output"))

    raw_tools = root.get("tools", {})
    tools_map = _require_mapping(raw_tools, "tools")
    tools = ToolsConfig(
        armips=_optional_str(tools_map, "armips", "tools"),
        clang=_optional_str(tools_map, "clang", "tools"),
        ld_lld=_optional_str(tools_map, "ld_lld", "tools"),
        llvm_objcopy=_optional_str(tools_map, "llvm_objcopy", "tools"),
    )

    raw_changes = root.get("changes", [])
    if not isinstance(raw_changes, list):
        raise ManifestError("changes must be a list")
    changes = tuple(_parse_change(value, index) for index, value in enumerate(raw_changes))
    return ProjectManifest(1, "nds", source, output, changes, tools)


def _change_to_mapping(change: Change) -> dict:
    if isinstance(change, FileReplaceChange):
        return {"type": change.type, "target": change.target, "source": change.source}
    if isinstance(change, BytePatchChange):
        return {
            "type": change.type,
            "target": change.target,
            "offset": f"0x{change.offset:X}",
            "expected": change.expected.hex(" ").upper(),
            "replacement": change.replacement.hex(" ").upper(),
        }
    if isinstance(change, ArmipsChange):
        result = {"type": change.type, "target": change.target, "script": change.script}
        if change.symbols is not None:
            result["symbols"] = change.symbols
        if change.symbol_file is not None:
            result["symbol_file"] = change.symbol_file
        if change.symbol_component is not None:
            result["symbol_component"] = change.symbol_component
        return result
    if isinstance(change, CInjectChange):
        result = {
            "type": change.type,
            "target": change.target,
            "symbol_file": change.symbol_file,
            "hook": change.hook,
            "expected": change.expected.hex(" ").upper(),
            "cave": change.cave if change.cave == "auto" else f"0x{change.cave:X}",
            "reserve": change.reserve,
            "fill": f"{change.fill:02X}",
        }
        if change.source is not None:
            result["source"] = change.source
        else:
            result["sources"] = list(change.sources)
        if change.symbol_component is not None:
            result["symbol_component"] = change.symbol_component
        if change.scratch_register is not None:
            result["scratch_register"] = change.scratch_register
        return result
    if isinstance(change, InjectChange):
        result = {
            "type": change.type,
            "target": change.target,
            "symbol_file": change.symbol_file,
            "hook": change.hook,
            "expected": change.expected.hex(" ").upper(),
            "script": change.script,
            "cave": change.cave if change.cave == "auto" else f"0x{change.cave:X}",
            "reserve": change.reserve,
            "fill": f"{change.fill:02X}",
        }
        if change.symbols is not None:
            result["symbols"] = change.symbols
        if change.symbol_component is not None:
            result["symbol_component"] = change.symbol_component
        if change.scratch_register is not None:
            result["scratch_register"] = change.scratch_register
        return result
    raise ManifestError(f"Unsupported change object: {type(change).__name__}")


def load_manifest(project_dir: Path) -> ProjectManifest:
    path = Path(project_dir) / "rommod.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"Manifest not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ManifestError(f"Invalid YAML in {path}: {exc}") from exc
    return _from_mapping(data)


def write_manifest(project_dir: Path, manifest: ProjectManifest) -> None:
    root = {
        "schema_version": manifest.schema_version,
        "platform": manifest.platform,
        "source": {"rom": manifest.source.rom, "sha256": manifest.source.sha256},
        "output": {"rom": manifest.output.rom},
        "changes": [_change_to_mapping(change) for change in manifest.changes],
    }
    tool_values = {
        "armips": manifest.tools.armips,
        "clang": manifest.tools.clang,
        "ld_lld": manifest.tools.ld_lld,
        "llvm_objcopy": manifest.tools.llvm_objcopy,
    }
    configured_tools = {key: value for key, value in tool_values.items() if value is not None}
    if configured_tools:
        root["tools"] = configured_tools
    path = Path(project_dir) / "rommod.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(root, sort_keys=False), encoding="utf-8")
