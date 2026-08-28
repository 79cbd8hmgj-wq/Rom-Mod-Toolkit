from __future__ import annotations

from pathlib import Path

from rommod.projects.manifest import CInjectChange, load_manifest, write_manifest


def test_c_inject_manifest_accepts_sources_list(tmp_path: Path):
    (tmp_path / "rommod.yaml").write_text(
        """schema_version: 1
platform: nds
source:
  rom: ../game.nds
  sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
output:
  rom: build/output/game.nds
changes:
  - type: c_inject
    target: arm9
    symbol_file: analysis/symbols.json
    hook: HookSite
    expected: "05 06 07 08"
    sources:
      - src/payload.c
      - src/helper.c
    cave: auto
    reserve: 48
""",
        encoding="utf-8",
    )

    manifest = load_manifest(tmp_path)
    change = manifest.changes[0]
    assert isinstance(change, CInjectChange)
    assert change.source is None
    assert change.sources == ("src/payload.c", "src/helper.c")

    write_manifest(tmp_path, manifest)
    assert load_manifest(tmp_path) == manifest
