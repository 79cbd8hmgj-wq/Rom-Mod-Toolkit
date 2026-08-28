"""Command-line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from rommod.projects.project import init_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rommod", description="ROM Mod Toolkit")
    subparsers = parser.add_subparsers(dest="command")
    init_parser = subparsers.add_parser("init", help="initialize an NDS mod project")
    init_parser.add_argument("source", type=Path)
    init_parser.add_argument("project", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        manifest = init_project(args.source, args.project)
        print(f"Initialized {args.project} ({manifest.source.sha256})")
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
