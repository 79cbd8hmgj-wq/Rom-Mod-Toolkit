from __future__ import annotations

from rommod.cli import build_parser


def test_patch_cli_accepts_format_and_output():
    args = build_parser().parse_args([
        "patch",
        "mod-project",
        "--format",
        "bps",
        "--output",
        "dist/mod.bps",
    ])
    assert args.command == "patch"
    assert str(args.project) == "mod-project"
    assert args.format == "bps"
    assert str(args.output) == "dist/mod.bps"
