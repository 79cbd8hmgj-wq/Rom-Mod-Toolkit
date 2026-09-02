# Phase 3 — ROM Mod Developer Experience

## Goal

Reduce the manual loop between an approved modification and a tested ROM while keeping the existing NDS foundation and source-intelligence safety guarantees intact.

## Implementation order

1. **Project scanner** — `rommod scan <project>` detects platform, project type, native build system, toolchain markers, modifiable data systems, and candidate ROM outputs. It writes deterministic discovery metadata to `rommod/project.json` and `rommod/reports/project_scan.json`.
2. **Unified build wrapper** — teach `rommod build` to consume scanner metadata for source/decomp projects while retaining the existing NDS manifest build path.
3. **Smart game-data diffs** — semantic before/after rendering for domain data rather than raw JSON-only review.
4. **Unified validation** — source, ROM, and assembly checks behind one command.
5. **Checkpoints/history** — reproducible snapshots, comparisons, and rollback metadata for iterative balancing.
6. **Emulator workflow** — optional build/launch/save-state-driven test harness after the deterministic developer loop is stable.

## Phase 3.1 scanner contract

The scanner is split into a read-only detector and an explicit report writer so discovery can be reused safely by later commands.

For a Pokémon-style NDS decomp, `rommod scan` should report:

- `platform: nds`
- `project_type: pokemon_decomp`
- `build_system: make` when a Makefile/GNUmakefile is present
- known toolchain markers such as `arm-none-eabi`
- data systems: Pokémon, moves, evolutions, trainers, items, text
- existing `.nds` outputs as project-relative paths

The CLI writes:

- `rommod/project.json` — compact reusable project metadata
- `rommod/reports/project_scan.json` — full deterministic scan report

## Safety rules

- Detection itself is read-only.
- Only `rommod scan` (or an explicit report-writing API call) creates metadata files.
- Paths stored in reports are project-relative where practical.
- Existing low-level NDS projects and source-intelligence commands must remain regression-safe.

## Verification

Use test-first development. Each Phase 3 feature gets a failing behavior test before production code, then the complete suite is run in GitHub Actions on `feature/developer-experience`.