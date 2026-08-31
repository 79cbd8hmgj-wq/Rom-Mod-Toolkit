# NDS Free-Space Discovery

## Scope

This slice adds read-only discovery of aligned fill-byte runs in Nintendo DS code targets. It completes the planned free-space-discovery link between symbol/function analysis and the existing guarded injection/hook pipeline without weakening the injection safety model.

Supported targets are:

- `arm9`
- `arm7`
- `overlay9:<id>`
- `overlay7:<id>`

## CLI

```bash
rommod caves PROJECT --target arm9 --min-size 32 --fill 00 --alignment 4
```

The command verifies the project manifest and source-ROM SHA-256 before loading the configured source ROM. It then scans only the selected target and emits JSON containing the target RAM base, target size, scan parameters, and candidate ranges.

Each candidate records:

- target-relative file `offset`;
- runtime CPU `address`;
- usable aligned `size`;
- scanned `fill` byte;
- whether the run is `trailing` at the end of the target.

Alignment is applied in CPU-address space. A maximal fill run is trimmed forward to the first aligned address, and it is reported only if the remaining usable range still satisfies `--min-size`.

## Safety boundary

A discovered fill run is a **candidate**, not proof that the bytes are unused or executable-safe. Discovery is read-only and never mutates the ROM.

The existing `cave: auto` behavior for `inject` and `c_inject` remains intentionally unchanged: it selects only the target's trailing fill run. Internal candidates found by `rommod caves` are never consumed automatically. To use one, the author must explicitly choose its CPU address as the manifest `cave` value; the existing injection guard then still verifies the complete reserved range contains the declared fill byte and confines writes to the hook/cave ranges.

## TDD and verification

The slice was developed red-to-green:

- unit tests first required aligned internal/trailing run discovery and invalid-configuration rejection;
- a CLI parser test required the `caves` command contract;
- an integration test required source-locked ARM9 discovery with file-offset-to-CPU-address mapping;
- the red run failed because `rommod.platforms.nds.free_space` did not yet exist;
- production code then added the scanner, project discovery wrapper, and CLI routing.

GitHub Actions run `33422794842` verified commit `a7ca6e6141081db06966ea8ebab06ae3cdf6474a` on Ubuntu 24.04. The workflow built/resolved armips, Flips, xdelta3, Clang, LLD, and llvm-objcopy, compiled all Python sources, and completed the full suite with **129 passed**.
