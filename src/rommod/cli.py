"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from rommod.platforms.nds.extract import extract_project
from rommod.platforms.nds.rom import NdsRom
from rommod.projects.build import build_project
from rommod.projects.manifest import load_manifest
from rommod.projects.project import init_project, verify_source


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
    return parser


def _inspect_path(target: Path) -> NdsRom:
    if target.is_dir():
        manifest = load_manifest(target)
        source = verify_source(target, manifest)
        return NdsRom.load(source)
    return NdsRom.load(target)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
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
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
