# NDS Foundation Execution

Implementation is performed on the isolated `feature/nds-foundation` integration branch. The original Phase-1 foundation is specified by `2026-08-28-nds-modification-foundation.md` plus its address-mapping addendum.

The NDS-first follow-up implementation has now extended that foundation through the coding and distribution milestones required for practical ROM modification:

- component-aware analysis symbol import;
- sandboxed armips patches;
- guarded ARM hooks;
- short and explicit-scratch long Thumb hooks;
- guarded trailing-fill code-cave selection;
- freestanding C injection from ARM and Thumb hook sites;
- ARM-to-Thumb interworking for analyzed Thumb functions;
- multi-source C compilation;
- shared project-contained C include directories;
- validated C preprocessor definitions;
- verified BPS/IPS/xdelta patch generation through the platform-neutral patching layer.

Detailed completion records are stored in the dated plan documents, including:

- `2026-08-31-nds-c-includes.md`;
- `2026-08-31-nds-c-defines.md`;
- `2026-08-31-nds-patch-distribution.md`.

The integration rule remains: feature slices must complete their TDD red-to-green cycle, pass the complete real-toolchain CI suite, and only then fast-forward `feature/nds-foundation`.

Broader arbitrary free-space discovery, Keystone, Unicorn, NitroFS create/delete operations, emulator-driven behavioral validation, and PSP support remain explicit later work rather than blockers for the completed NDS extraction → modification → rebuild → verification → distribution path.
