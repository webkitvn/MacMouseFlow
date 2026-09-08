## Context

See `proposal.md` for motivation and the two delta specs for behavioral requirements. At baseline `c668f97664faf29f7b22cd47d1d26b21f56bb14f`, `rust/engine` and `rust/ffi` are intentionally empty ownership-boundary crates: Rust currently owns no product behavior and no C ABI exists. `Justfile` already makes `just test` the canonical Rust test entry point.

This implementation slice is constrained by `AGENTS.md`, `CONTEXT.md`, ADR 0001, ADR 0002, and active guardrails. The native adapter will own platform event extraction/application later; this slice accepts only normalized platform-neutral values. The scoped issue is #53, owned by `webkitvn`; its closed blockers are #47, #64, #74, and #79.

## Goals / Non-Goals

**Goals:**
- Define the smallest public Rust evaluator that owns platform-neutral scroll semantics.
- Establish an inspectable, fixed-layout, versioned C contract that native code can compile against without generated bindings or cross-boundary allocation.
- Make malformed normal inputs and evaluator faults fail open as Preserve with an explicit status.
- Test vertical behavior only through the public Rust and C seams, including a real C caller.

**Non-Goals:**
- Native `CGEventTap`, Accessibility, UI, persistence, source/device matching, physical `Device Identity`, IPC/helper/HID, suppression behavior, production panic-injection API, or release integration.
- General ABI extensibility beyond reserved fields and `_v1`; do not create a generic FFI framework.

## Decisions

### Keep evaluation types platform-neutral and source-independent

The engine will expose normalized input values: an input kind/tag, explicit source-class tag (including Unknown), scroll granularity, signed `i64` line deltas, configuration direction, and an `Input Decision` tag/payload. It will accept Unknown and deliberately avoid identity fields or classification logic.

The minimum v0.1 behavior is:
- System/default direction: Preserve.
- Reverse + LineBased + at least one nonzero delta: checked-negate both `i64` axes (retaining a zero axis) and return Replace.
- Reverse + both zero axes: Preserve.
- Reverse + a negation overflow: Preserve with a non-success status.
- PixelBased: Preserve regardless of configuration.

This keeps Scroll Granularity from becoming source evidence and gives the later native adapter a deterministic no-op result for unsupported input. Alternatives rejected: per-source rules (not in scope), device inference (prohibited), float deltas (unnecessary and less exact for this line-based contract), and suppression (not authorized).

### Use direct Rust value types and one opaque engine

`rust/engine` will hold the evaluator types and one engine storing its direction configuration as `AtomicU32`. Updates validate then atomically store a compact configuration encoding; each evaluation atomically loads one value. No trait, callback, provider, or test-only seam is needed.

The engine crate retains `#![forbid(unsafe_code)]`; unsafe pointer handling stays in `rust/ffi`. Alternatives rejected: lock-based mutable configuration (wider hot-path blocking risk), heap-owned config snapshots (unneeded allocation), or a configuration framework (YAGNI).

### Publish manual `_v1` C declarations with exact layout checks

`rust/ffi` will export explicitly named `_v1` functions and manually maintain a C header alongside them. Every C-visible input/output uses primitive fixed-width `#[repr(C)]` POD structs with documented `version`, `size`, and reserved fields. Exact version/size and all-zero reserved checks prevent accidental compatibility claims. Rust conversion functions validate fields before producing engine values.

The header is a checked contract, not generated output. Alternatives rejected: generated bindings (extra toolchain/process), C strings or heap data (ownership complexity), Rust enum layout across C (unstable representation), and accepting larger structures (would silently imply forward compatibility this slice does not provide).

### Separate status from initialized fail-open decision

An evaluation export validates its output pointer first. If it is non-null, it writes Preserve before reading any other request field. It returns a C status code separately from the decision. All exports use `catch_unwind`; any captured panic becomes a non-success status. A private `cfg(test)` panic latch is permitted only if required to prove this behavior; it must not introduce a production fault-control API or dependency.

The output initialization gives native integration a safe default even if request conversion or evaluation fails. Alternatives rejected: encoding failure as suppression, relying on caller initialization, crossing unwinds into C, or exposing a production test hook.

### Define narrow ownership rules for engine handles

Create returns one uniquely-owned opaque handle variable. Non-owning copies may evaluate or update configuration concurrently while the owner keeps the allocation live; destroy takes only the owner pointer-to-handle, writes null before freeing, and treats an already-null owner variable as a no-op. The header documents concurrent destruction, use-after-destroy, and stale/fabricated handles as caller violations. No registry, reference count, magic tag, or concurrent-handle scheme is added.

This supports normal C cleanup without pretending arbitrary invalid pointers can be made safe. Alternatives rejected: refcounted ownership (unnecessary), global handle registry (hot-path/state complexity), and a non-nulling destroy API (invites repeat cleanup bugs).

### Prove public seams in a test-first vertical sequence

Implementation begins with failing Rust public-seam behavior tests, then the minimum engine code, then failing ABI conversion/lifetime/fail-open tests, then the ABI implementation, then a C source program compiled, linked, and run through `just test`. The C test proves the checked-in header, symbol linkage, and actual caller behavior together. It uses the platform C compiler already available to the Rust/macOS toolchain; no test framework or generated binding is added.

## Risks / Trade-offs

- [A hand-maintained header diverges from Rust declarations] → The C compile/link/run test uses the checked-in header and every exported `_v1` operation it needs.
- [Exact size rejects future callers] → That is intentional ABI safety; future expansion requires new `_vN` symbols and structs.
- [Atomic config load races an update] → A single complete `u32` snapshot is acceptable; an evaluation observes either whole state, never a partial state.
- [Panic testing could leak a test control surface] → Keep any trigger private under `cfg(test)` and omit it unless `catch_unwind` cannot otherwise be covered.
- [C test is toolchain-sensitive] → Route it only through canonical `just test`, report unavailable compiler support as missing evidence, and do not substitute a simulated binding test.
- [Hot-path budget is not proven by deterministic tests] → Do not claim latency acceptance; reference-Mac benchmark evidence belongs to the later canonical environment.

## Migration Plan

1. Add the engine and ABI as new, unconsumed seams; no production caller exists at baseline.
2. Run `just check`, `just test` (including the C contract test), and the relevant build command after implementation.
3. A later native-runtime change adopts only the published `_v1` header and symbols. It preserves native input whenever the ABI status is non-success or decision is Preserve.
4. Rollback is removal/reversion of this unconsumed slice. Once a native caller ships, retain `_v1` unchanged and add a separately specified `_vN` for any incompatible extension.

## Superseding panic-containment evidence

This archive records the original Issue #53 implementation evidence. Its `catch_unwind` claim does not supersede the live process-wide panic-hook and caught-payload policy resolved by Issue #82. That policy, ADR 0005, and its public-ABI evidence are the canonical completion evidence for callback-originated Rust panic containment.

## STOP Conditions

STOP implementation and return to the Issue/Wayfinder decision process if any of the following becomes necessary:
- A behavior beyond Preserve/Replace reverse line scrolling, including suppression, scaling, per-source selection, source inference, or physical Device Identity.
- A C layout compatibility rule other than exact `_v1` version/size/reserved validation, a non-POD value, or cross-boundary heap ownership.
- A platform API, `CGEventTap`, Accessibility, UI, persistence, helper/IPC/HID, or release integration change.
- A lock, allocation, blocking operation, parsing, I/O, or logging on the intended input evaluation path.
- A new public fault-injection API, dependency, trait/adapter/mock, or other test seam solely to make tests pass.
- Any conflict between this change and newer Issue #53 decisions, source-of-truth documents, active guardrails, or a material architecture/product/security/privacy decision not settled here.
