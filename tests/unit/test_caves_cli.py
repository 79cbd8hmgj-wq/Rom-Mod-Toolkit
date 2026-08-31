from __future__ import annotations

from rommod.cli import build_parser


def test_caves_cli_accepts_target_fill_size_and_alignment():
    args = build_parser().parse_args(
        [
            "caves",
            "project",
            "--target",
            "overlay9:3",
            "--min-size",
            "48",
            "--fill",
            "FF",
            "--alignment",
            "8",
        ]
    )

    assert args.command == "caves"
    assert str(args.project) == "project"
    assert args.target == "overlay9:3"
    assert args.min_size == 48
    assert args.fill == "FF"
    assert args.alignment == 8
