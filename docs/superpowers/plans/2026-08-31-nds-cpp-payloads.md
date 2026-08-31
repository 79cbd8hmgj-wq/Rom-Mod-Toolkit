# NDS Freestanding C++ Payload Plan

## Goal

Extend the existing `c_inject` pipeline to compile small freestanding C++ payloads without duplicating hook, symbol, interworking, cave, or reporting logic.

## Contract

- `language` accepts `auto`, `c`, or `cpp` and defaults to `auto`.
- Explicit `cpp` forces Clang C++ parsing even for extensionless source paths.
- C++ payloads remain freestanding and disable exceptions, RTTI, thread-safe local-static initialization, and `__cxa_atexit` registration.
- The required entry point remains the unmangled symbol `rommod_payload`; C++ authors expose it with `extern "C"`.
- Existing writable `.data` / `.bss`, capacity, symbol, hook, cave, and bounded-write guards remain unchanged.
- The chosen language is preserved in build reports for reproducibility.

## Verification

The TDD slice covers manifest parsing/roundtrip, invalid-language rejection, real ARM-targeting Clang compilation of C++ templates from a non-C++ extension, exception-runtime rejection, and a full synthetic-NDS build/report path.
