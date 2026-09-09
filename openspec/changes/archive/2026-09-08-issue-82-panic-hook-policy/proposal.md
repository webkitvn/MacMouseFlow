## Why

Issue #82 resolves the remaining merge blocker for Issue #53: Rust invokes its process-wide panic hook before `catch_unwind`, so the default hook can violate the input callback's no-synchronous-I/O contract even when the ABI returns fail-open `Panic` plus Preserve. The current ABI also needs a containment rule for a caught panic payload whose destructor panics.

## What Changes

- Install one Rust-FFI-owned process-global panic hook during successful engine creation, before allocation or input delivery; retain it for the process lifetime and delegate non-input panics to the captured previous hook.
- Suppress hook work only during the private thread-local dynamic extent of ABI evaluation; retain existing `Panic` status plus Preserve output as the callback diagnostic.
- Enforce `panic = "unwind"`, contain primary and secondary panic-payload disposal, and fail startup with a null owner when hook installation fails.
- Add ADR 0005, targeted guardrail canonical-source pointers where applicable, public-ABI regression coverage, and reconcile the historical Issue #53 OpenSpec evidence after the policy is implemented.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `c-input-engine-abi`: Define process-wide Rust panic-hook policy, callback panic containment, startup failure, and public-ABI verification requirements for the existing C input engine ABI.

## Impact

- Affected implementation: `rust/ffi`, its existing public ABI tests, FFI crate compile configuration, and an implementation-specific ADR under `docs/adr/`.
- Affected governance: canonical-source links for active runtime/reliability guardrails only where the ADR adds direct applicable evidence; invariants remain unchanged.
- Historical evidence to reconcile after implementation: `openspec/changes/archive/2026-09-07-issue-53-rust-engine-c-abi/`.
- Bound to Issue #82, owned by `webkitvn`, at baseline `6e35f1edcaf63e70a7c0b1ec954e470927439b64`. It unblocks Issue #53 only once the selected policy and evidence are applied.
- No new C symbols, production fault-control API, helper/IPC, per-event global-hook mutation, or strict latency claim is authorized.
