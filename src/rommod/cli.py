"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from rommod.errors import BuildError, RomModError
from rommod.patching.distribution import create_project_patch
from rommod.platforms.nds.extract import extract_project
from rommod.platforms.nds.free_space import discover_project_caves
from rommod.platforms.nds.rom import NdsRom
from rommod.platforms.nds.validation import verify_project, verify_rom
from rommod.projects.build import build_project
from rommod.projects.manifest import load_manifest
from rommod.projects.project import init_project, verify_source


_HEX = set("0123456789abcdef")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rommod", description="ROM Mod Toolkit")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="initialize an NDS mod project")
    init_parser.add_argument("source", type=Path)
    init_parser.add_argument("project", type=Path)

    inspect_parser = subparsers.add_parser("inspect", help="inspect an NDS ROM or project")
    inspect_parser.add_argument("target", type=Path)

    extract_parser = subparsers.add_parser("extract", help="extract an NDS project snapshot")
    extract_parser.add_argument("project", type=Path)

    build_cmd = subparsers.add_parser("build", help="build an NDS mod project")
    build_cmd.add_argument("project", type=Path)

    verify_cmd = subparsers.add_parser("verify", help="verify an NDS ROM or project output")
    verify_cmd.add_argument("target", type=Path)

    caves_cmd = subparsers.add_parser(
        "caves",
        help="discover aligned fill-run candidates in an NDS code target",
    )
    caves_cmd.add_argument("project", type=Path)
    caves_cmd.add_argument("--target", required=True)
    caves_cmd.add_argument("--min-size", type=int, default=32)
    caves_cmd.add_argument("--fill", default="00")
    caves_cmd.add_argument("--alignment", type=int, default=4)

    patch_cmd = subparsers.add_parser("patch", help="build and create a verified distributable patch")
    patch_cmd.add_argument("project", type=Path)
    patch_cmd.add_argument("--format", choices=("bps", "ips", "xdelta"), required=True)
    patch_cmd.add_argument("--output", type=Path)
    return parser


def _inspect_path(target: Path) -> NdsRom:
    if target.is_dir():
        manifest = load_manifest(target)
        source = verify_source(target, manifest)
        return NdsRom.load(source)
    return NdsRom.load(target)


def _parse_fill_byte(value: str) -> int:
    compact = value.strip().lower().removeprefix("0x")
    if len(compact) != 2 or any(ch not in _HEX for ch in compact):
        raise BuildError("--fill must be one hexadecimal byte")
    return int(compact, 16)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            manifest = init_project(args.source, args.project)
            print(f"Initialized {args.project} ({manifest.source.sha256})")
            return 0
        if args.command == "inspect":
            print(json.dumps(asdict(_inspect_path(args.target).metadata()), indent=2, sort_keys=True))
            return 0
        if args.command == "extract":
            print(json.dumps(extract_project(args.project), indent=2, sort_keys=True))
            return 0
        if args.command == "build":
            result = build_project(args.project)
            print(
                json.dumps(
                    {
                        "output": str(result.output_path),
                        "report": str(result.report_path),
                        "sha256": result.output_sha256,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "verify":
            report = verify_project(args.target) if args.target.is_dir() else verify_rom(args.target)
            print(json.dumps(asdict(report), indent=2, sort_keys=True))
            return 0
        if args.command == "caves":
            report = discover_project_caves(
                args.project,
                args.target,
                min_size=args.min_size,
                fill=_parse_fill_byte(args.fill),
                alignment=args.alignment,
            )
            print(json.dumps(asdict(report), indent=2, sort_keys=True))
            return 0
        if args.command == "patch":
            result = create_project_patch(args.project, args.format, args.output)
            print(
                json.dumps(
                    {
                        "format": result.patch_format,
                        "output": str(result.output_path),
                        "patch_sha256": result.patch_sha256,
                        "report": str(result.report_path),
                        "source_sha256": result.source_sha256,
                        "target_sha256": result.target_sha256,
                        "verified": result.verified,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        parser.print_help()
        return 0
    except RomModError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
