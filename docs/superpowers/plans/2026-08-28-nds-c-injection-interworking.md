# NDS C Injection and Thumb Interworking Plan

**Goal:** Compile small freestanding ARM C payloads for NDS code caves and allow those payloads to call validated ARM and Thumb game functions from the component-aware analysis symbol map without unsafe implicit state changes.

## Implemented architecture

- `type: c_inject` uses a guarded ARM hook and the existing source-ROM/hash/rebuild safety model.
- An 8-byte ARM wrapper in the reserved cave calls `rommod_payload` with `BL` and branches back to `hook + 4`.
- Clang targets `arm-none-eabi`, `arm946e-s`, ARM mode, freestanding/no-runtime code.
- LLD links the image at the selected cave address; llvm-objcopy extracts the executable `.text` image.
- Writable `.data`, `.bss`, and COMMON storage are rejected.
- The linked image must fit completely inside the declared cave reserve.
- ARM and neutral/data analysis symbols are supplied as validated absolute linker symbols.
- Thumb game functions are never linked as raw odd/even absolute addresses. Instead, the toolkit generates ARM veneer object sections.
- Each Thumb veneer uses the AAPCS call-scratch register `r12/ip`:

```asm
ldr r12, [pc, #0]
bx  r12
.word thumb_address | 1
```

- Each veneer is emitted into its own `.text.__rommod_thumb_<name>` section.
- LLD uses `--gc-sections`, so veneers that the C payload does not reference are discarded.
- Build reports record C payload address/size, compiler tool versions, and whether Thumb interworking was linked.

## Safety constraints

- `c_inject` currently begins at an ARM hook symbol only.
- Hook bytes are guarded by the manifest's exact `expected` bytes.
- Auto caves use only the aligned trailing run of the declared fill byte.
- The hook and cave may not overlap.
- armips may only modify the guarded hook and declared cave ranges.
- Compiler, linker, assembler, size, expected-byte, symbol-map, or bounded-write failures abort before the configured ROM output is written.
- Imported symbol addresses must agree with their component-relative offsets and target mapping.

## Verification sequence

1. RED integration test proved the pre-interworking implementation failed with `undefined symbol: ThumbHelper` after all real tools were successfully installed/built.
2. Generated veneer-object implementation added explicit ARM→Thumb state switching.
3. Focused real-toolchain GitHub Actions test passed using freshly built armips plus Clang/LLD/llvm-objcopy.
4. Existing C tests were made environment/PATH portable.
5. Final gate runs `compileall` plus the complete pytest suite on GitHub Actions.

## Deferred follow-ups

- Direct `c_inject` entry from Thumb hook sites.
- User-authored multi-object/multi-source C builds.
- C++ runtime/linking policy.
- Broader declared free-space management.
- Emulator-driven behavioral validation.
