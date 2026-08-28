# NDS ARM Hook Injection Implementation Plan

> **For agentic workers:** Execute task-by-task with TDD and fresh verification.

**Goal:** Add safe symbol-aware ARM hook injection using deterministic trailing code caves and real armips assembly.

**Architecture:** `InjectChange` resolves one named ARM symbol in a component-aware analysis symbol file, verifies exact hook bytes, selects either an explicit cave CPU address or a deterministic aligned cave inside trailing fill bytes, and runs a toolkit-generated armips wrapper that writes only a 4-byte ARM branch at the hook plus a bounded payload/return sequence inside the reserved cave. The adapter rejects any write outside those two allowed regions.

**Constraints:**
- ARM mode only in this slice; Thumb hooks fail closed.
- Hook overwrite is exactly one 4-byte ARM branch and requires exact expected bytes.
- Auto caves are selected only from trailing repeated fill bytes, never arbitrary internal zero runs.
- Cave reserve is explicit, 4-byte aligned, and guarded against overlap with the hook.
- User payload fragments cannot own files, select architecture/mode, or reposition assembly with `.org`/`.orga`.
- Imported symbols remain component-aware and address/offset validated.
- armips runs against a copied target under `build/work/`; source ROM is never writable by armips.
- Diff validation rejects writes outside the hook and cave reserve.
- Optional symbol output is materialized only after rebuilt-ROM validation.

### Task 1: Manifest + cave primitives
- [x] Add failing `InjectChange` YAML round-trip/validation tests.
- [x] Add failing deterministic trailing-cave tests.
- [x] Implement strict manifest parsing and cave discovery.
- [x] Run focused and full tests.

### Task 2: Symbol-aware ARM injector
- [x] Add failing real-armips ARM9 hook integration test.
- [x] Resolve exactly one named ARM symbol and validate target mapping/expected hook bytes.
- [x] Generate hook → payload → return armips wrapper.
- [x] Reject writes outside hook/cave and target resizing.
- [x] Run focused and full tests.

### Task 3: Build/report integration
- [x] Add `InjectChange` to ordered build mutations and touched-target verification.
- [x] Defer symbol output until post-rebuild validation.
- [x] Record resolved hook/cave metadata in build report.
- [x] Verify failed injection writes no configured ROM output.

### Task 4: Documentation + smoke
- [x] Document symbol file, payload contract, cave selection, and ARM-only limitation.
- [x] Run compileall, full pytest with real armips, and manual injected-ROM smoke verification.
