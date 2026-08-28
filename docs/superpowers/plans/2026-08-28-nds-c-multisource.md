# NDS Multi-Source C Injection

## Status

Implemented and verified on `feature/nds-c-multisource`.

## Goal

Allow one `c_inject` mutation to compile and link multiple freestanding ARM C translation units while preserving the existing single-source workflow and all bounded-write guarantees.

## Manifest contract

Legacy single-source projects remain valid:

```yaml
changes:
  - type: c_inject
    target: arm9
    symbol_file: analysis/symbols.json
    hook: HookSite
    expected: "05 06 07 08"
    source: src/payload.c
    cave: auto
    reserve: 48
```

A multi-source project uses `sources`:

```yaml
changes:
  - type: c_inject
    target: arm9
    symbol_file: analysis/symbols.json
    hook: HookSite
    expected: "05 06 07 08"
    sources:
      - src/payload.c
      - src/helper.c
      - src/battle_math.c
    cave: auto
    reserve: 64
```

A C injection must declare **exactly one** of `source` or `sources`. Supplying both or neither fails manifest validation. `sources` must be a non-empty list of non-empty project-relative paths.

## Compilation and linking

Every declared C source is resolved inside the mod project and compiled independently with the same NDS ARM946E-S freestanding flags. Object files are named deterministically (`payload_000.o`, `payload_001.o`, and so on) and linked in manifest order.

Exactly one linked `rommod_payload` entry point is still required. Supporting functions may live in any listed translation unit. Normal unresolved or duplicate C symbols are rejected by LLD rather than silently tolerated.

The existing constraints remain unchanged:

- ARM mode (`-marm`) for the current C injector;
- no standard library;
- no writable `.data`;
- no `.bss`;
- code and read-only constants must fit inside the declared cave capacity;
- generated ARM-to-Thumb veneers remain available for validated imported Thumb game symbols;
- source ROMs are never passed to Clang, LLD, llvm-objcopy, or armips.

## Rebuild safety

Multi-source compilation does not weaken the injection boundary. The generated payload is still inserted only inside the declared code-cave reserve, the guarded hook bytes must match exactly, target size may not change, and any write outside the hook/cave ranges aborts the build.

## Reporting

`reports/build.json` preserves the authoring form. Legacy changes record `source`; multi-source changes record the ordered `sources` list. Compiler/linker/assembler versions and resolved paths continue to be recorded.

## Verification

Clean Ubuntu CI builds armips from source, installs Clang/LLD/LLVM, runs `compileall`, and executes the complete synthetic-ROM suite. The verified milestone is:

```text
106 passed
```

Coverage includes manifest exclusivity, manifest round-trip, multi-translation-unit compilation/linking, end-to-end ROM injection, and build-report preservation of the source list.
