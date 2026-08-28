# NDS Multi-Source C Injection

## Status

Implemented on top of the NDS Thumb-C hook and ARM↔Thumb interworking foundation.

## Manifest contract

Legacy single-source projects remain valid with `source:`. Larger mods can instead declare ordered translation units with `sources:`:

```yaml
changes:
  - type: c_inject
    target: arm9
    symbol_file: analysis/symbols.json
    hook: BattleHook
    expected: "05 06 07 08"
    sources:
      - src/payload.c
      - src/battle_math.c
      - src/helpers.c
    cave: auto
    reserve: 96
```

A `c_inject` mutation must provide exactly one of `source` or `sources`. `sources` must be a non-empty ordered list of project-contained paths.

## Build behavior

Each translation unit is independently compiled for ARM946E-S in freestanding ARM mode, then linked in manifest order. Exactly one linked `rommod_payload` entry is required. Supporting C functions can live in any declared unit.

The same restrictions remain in force:

- no standard library;
- no writable `.data` or `.bss`;
- final linked payload must fit in the declared cave reserve after the selected ARM/Thumb bridge;
- project path containment applies to every source;
- unresolved or duplicate C symbols fail at link time;
- validated imported Thumb game functions still use explicit ARM→Thumb veneers;
- ARM, short-Thumb, and explicit-scratch long-Thumb hook entry modes remain supported;
- writes remain bounded to the guarded hook and reserved cave.

`reports/build.json` preserves `source` for legacy projects and the ordered `sources` list for multi-source projects.

## Verification

The original multi-source slice reached 106/106 passing tests. The reconciled branch additionally retains the newer Thumb→ARM C hook-entry tests and is verified by the repository-wide NDS CI workflow before integration into `feature/nds-foundation`.
