## Why

Issue #53 needs the first deterministic, platform-neutral input-evaluation contract before the native runtime can call Rust safely. The current crates deliberately contain only ownership-boundary scaffolds, so this change establishes the fixed C seam and fail-open semantics required by the accepted M0-S2 slice.

## What Changes

- Add a platform-neutral Rust input evaluator for `Input Event`, explicit `Input Source`/`Source Class`, `Scroll Configuration`, and `Input Decision`.
- Add deterministic scroll behavior: `LineBased` input preserves when both signed `i64` axes are zero; otherwise reverse direction checked-negates both axes (retaining a zero axis); `PixelBased` input always preserves.
- Add a narrow, versioned `_v1` C ABI with manually maintained C header, fixed-width `#[repr(C)]` POD values, opaque engine ownership, validation, explicit status, and fail-open output initialization.
- Add public-seam Rust unit/property tests and an actual C compile/link/run contract test, all run by `just test`.
- Document ABI caller obligations and the implementation STOP conditions needed to prevent ownership, identity-inference, runtime-topology, or semantics drift.

## Capabilities

### New Capabilities
- `rust-input-evaluator`: Platform-neutral evaluation of normalized input and scroll configuration into an `Input Decision`.
- `c-input-engine-abi`: Versioned fixed-layout C ABI for creating, configuring, evaluating, and destroying the Rust input engine.

### Modified Capabilities
- None.

## Impact

- Affected crates: `rust/engine` and `rust/ffi`; a manually maintained public C header and minimal C contract-test harness will be added during implementation.
- No new dependency, platform adapter, process boundary, persistence, UI, physical `Device Identity`, IPC, HID, or release integration is introduced.
- Bound to GitHub Issue #53, owned by `webkitvn`, on baseline `c668f97664faf29f7b22cd47d1d26b21f56bb14f`; closed blockers are #47, #64, #74, and #79.
- Implementation must preserve the native/Rust ownership boundary and fail-open requirements in `AGENTS.md`, `CONTEXT.md`, ADRs 0001/0002, and active guardrails DG-DOM-001, DG-ARCH-001, DG-REL-001, and DG-VER-001.
