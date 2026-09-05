"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from rommod.dev.build import build_source_project
from rommod.dev.checkpoints import compare_checkpoints, create_checkpoint, restore_checkpoint
from rommod.discovery.scanner import scan_project, write_scan_reports
from rommod.domains.pokemon.analysis import analyze_repository
from rommod.domains.pokemon.diff import diff_repositories
from rommod.domains.pokemon.ledger import apply_ledger, load_ledger, plan_ledger
from rommod.domains.pokemon.loader import load_repository_index
from rommod.domains.pokemon.validation import validate_repository
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

    scan_parser = subparsers.add_parser("scan", help="discover an existing ROM modification project")
    scan_parser.add_argument("root", type=Path)

    init_parser = subparsers.add_parser("init", help="initialize an NDS mod project")
    init_parser.add_argument("source", type=Path)
    init_parser.add_argument("project", type=Path)

    inspect_parser = subparsers.add_parser("inspect", help="inspect an NDS ROM or project")
    inspect_parser.add_argument("target", type=Path)

    extract_parser = subparsers.add_parser("extract", help="extract an NDS project snapshot")
    extract_parser.add_argument("project", type=Path)

    build_cmd = subparsers.add_parser("build", help="build an NDS mod or discovered source project")
    build_cmd.add_argument("project", type=Path)

    validate_cmd = subparsers.add_parser(
        "validate",
        help="validate a source project or structurally verify a manifest NDS project",
    )
    validate_cmd.add_argument("target", type=Path)

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

    checkpoint_cmd = subparsers.add_parser("checkpoint", help="snapshot source data and build metadata")
    checkpoint_cmd.add_argument("name")
    checkpoint_cmd.add_argument("--root", type=Path, default=Path("."))

    compare_cmd = subparsers.add_parser("compare", help="compare two developer checkpoints semantically")
    compare_cmd.add_argument("before", type=Path)
    compare_cmd.add_argument("after", type=Path)

    restore_cmd = subparsers.add_parser("restore", help="restore a verified developer checkpoint")
    restore_cmd.add_argument("checkpoint", type=Path)
    restore_cmd.add_argument("--root", type=Path, default=Path("."))

    source_analyze_cmd = subparsers.add_parser(
        "source-analyze",
        help="analyze a source repository for semantic modification opportunities",
    )
    source_analyze_cmd.add_argument("root", type=Path)
    source_analyze_cmd.add_argument("--domain", choices=("pokemon",), default="pokemon")

    source_diff_cmd = subparsers.add_parser(
        "source-diff",
        help="compare two source repositories semantically",
    )
    source_diff_cmd.add_argument("before", type=Path)
    source_diff_cmd.add_argument("after", type=Path)
    source_diff_cmd.add_argument("--domain", choices=("pokemon",), default="pokemon")

    source_ledger_cmd = subparsers.add_parser(
        "source-ledger",
        help="validate or apply an approved source-edit ledger",
    )
    source_ledger_cmd.add_argument("root", type=Path)
    source_ledger_cmd.add_argument("ledger", type=Path)
    source_ledger_cmd.add_argument(
        "--apply",
        action="store_true",
        help="write validated changes; without this flag the command is read-only",
    )
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


def _source_analysis_payload(root: Path, domain: str) -> dict[str, object]:
    if domain != "pokemon":
        raise RomModError(f"unsupported source-analysis domain: {domain}")

    index = load_repository_index(root)
    findings: list[dict[str, object]] = []
    for finding in analyze_repository(index):
        item = asdict(finding)
        source_path = item.get("source_path")
        if source_path is not None:
            item["source_path"] = str(source_path)
        findings.append(item)

    return {
        "domain": domain,
        "root": str(index.root),
        "species_count": len(index.species),
        "move_count": len(index.moves),
        "evolution_count": len(index.evolutions),
        "warnings": list(index.warnings),
        "findings": findings,
    }


def _source_ledger_payload(root: Path, ledger_path: Path, *, apply: bool) -> dict[str, object]:
    ledger = load_ledger(ledger_path)
    plan = apply_ledger(root, ledger) if apply else plan_ledger(root, ledger)
    files: list[dict[str, object]] = []
    for planned_file in plan.files:
        changes = []
        for change in planned_file.changes:
            changes.append(
                {
                    "species": change.species,
                    "operation": change.operation,
                    "before": list(change.before) if change.before is not None else None,
                    "after": list(change.after) if change.after is not None else None,
                }
            )
        files.append(
            {
                "source_path": str(planned_file.source_path),
                "source_sha256": planned_file.source_sha256,
                "result_sha256": planned_file.result_sha256,
                "changes": changes,
            }
        )
    return {
        "domain": ledger.domain,
        "root": str(root.resolve()),
        "ledger": str(ledger_path),
        "applied": plan.applied,
        "file_count": len(plan.files),
        "files": files,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "scan":
            report = scan_project(args.root)
            write_scan_reports(report)
            print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
            return 0
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
            if (args.project / "rommod.yaml").is_file():
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
            else:
                result = build_source_project(args.project)
                print(
                    json.dumps(
                        {
                            "mode": "source",
                            "build_system": result.build_system,
                            "command": list(result.command),
                            "outputs": list(result.outputs),
                            "report": str(result.report_path),
                        },
                        indent=2,
                        sort_keys=True,
                    )
                )
            return 0
        if args.command == "validate":
            if (args.target / "rommod.yaml").is_file():
                report = verify_project(args.target)
                print(json.dumps(asdict(report), indent=2, sort_keys=True))
                return 0
            report = validate_repository(args.target)
            print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
            return 0 if report.valid else 1
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
        if args.command == "checkpoint":
            result = create_checkpoint(args.root, args.name)
            print(
                json.dumps(
                    {"directory": str(result.directory), "file_count": result.file_count},
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "compare":
            print(json.dumps(compare_checkpoints(args.before, args.after).to_dict(), indent=2, sort_keys=True))
            return 0
        if args.command == "restore":
            result = restore_checkpoint(args.root, args.checkpoint)
            print(
                json.dumps(
                    {"checkpoint": str(result.checkpoint), "restored_files": result.restored_files},
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "source-analyze":
            print(json.dumps(_source_analysis_payload(args.root, args.domain), indent=2, sort_keys=True))
            return 0
        if args.command == "source-diff":
            if args.domain != "pokemon":
                raise RomModError(f"unsupported source-diff domain: {args.domain}")
            print(
                json.dumps(
                    diff_repositories(args.before, args.after).to_dict(),
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "source-ledger":
            print(
                json.dumps(
                    _source_ledger_payload(args.root, args.ledger, apply=args.apply),
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
