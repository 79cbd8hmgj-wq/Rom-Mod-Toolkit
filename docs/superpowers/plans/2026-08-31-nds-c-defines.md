# NDS C Preprocessor Define Support

## Completed behavior

`type: c_inject` changes may declare an ordered list of C preprocessor definitions:

```yaml
changes:
  - type: c_inject
    target: arm9
    symbol_file: analysis/symbols.json
    hook: BattleDamage
    expected: "05 06 07 08"
    source: src/battle_damage.c
    defines:
      - ROMMOD_FEATURE=1
      - GAME_REGION_US
    cave: auto
    reserve: 64
```

Each entry must begin with a valid C macro identifier and may optionally contain `=value`. Control characters and malformed macro names fail closed during manifest parsing and are checked again at the compiler boundary.

Every validated definition is passed to every C translation unit as an individual Clang `-D` argument. The arguments are passed directly as subprocess argv values rather than through a shell.

The ordered list is preserved by manifest round-tripping and in `reports/build.json`, making configuration visible in reproducible build metadata.

## Verification

The TDD red state was observed in GitHub Actions before production support was added. Commit `4b8e67df50af26eb9b5f6ca878262cbdbbb2895b` then completed the clean `NDS toolkit verification` workflow successfully on 2026-08-31, including Python byte-compilation and the complete pytest suite with real armips, Clang, LLD, and llvm-objcopy.
