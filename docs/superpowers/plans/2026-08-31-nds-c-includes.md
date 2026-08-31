# NDS C Include Directory Support

## Completed behavior

`type: c_inject` changes may declare project-relative include directories shared by every C translation unit:

```yaml
changes:
  - type: c_inject
    target: arm9
    symbol_file: analysis/symbols.json
    hook: BattleDamage
    expected: "05 06 07 08"
    sources:
      - src/payload.c
      - src/helper.c
    include_dirs:
      - include
      - src/common
    cave: auto
    reserve: 64
```

The manifest parser preserves the ordered `include_dirs` list. Each path is resolved through the project-containment guard, must exist, and must be a directory. Escapes outside the project and missing/non-directory include paths fail the build before compilation.

The compiler passes every validated include directory to every C translation unit using a separate `-I <path>` argument. Multi-source projects therefore share the same header search path without relying on the caller's working directory or global compiler environment.

`reports/build.json` preserves the declared include-directory list on each `c_inject` change so builds remain auditable and reproducible.

## Verification

Coverage includes:

- manifest round-trip and validation;
- project-containment and directory checks;
- multi-source compilation against a shared header;
- end-to-end NDS build and build-report preservation;
- the complete regression suite with real armips, Clang, LLD, and llvm-objcopy in GitHub Actions.

The reporting regression was completed by commit `f1e643aa40c8a6c4040ee9f7579e8f94722b77e4`, whose `NDS toolkit verification` workflow completed successfully on 2026-08-31.
