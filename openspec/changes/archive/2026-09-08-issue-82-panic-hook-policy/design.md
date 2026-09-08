## Context

See `proposal.md` and the modified C ABI requirement. At baseline `6e35f1edcaf63e70a7c0b1ec954e470927439b64`, each FFI export catches unwinding panics and evaluation initializes Preserve first, but Rust's default process hook runs before the catch boundary. The existing `cfg(test)` evaluation latch already proves Panic plus Preserve through the public ABI; it remains allowed by Issue #82's resolution.

The policy must retain the existing single-process native/Rust boundary, callback fail-open behavior, fixed-layout ABI, public-seam testing, and no synchronous callback logging/I/O. Issue #82 is the live decision and blocking dependency for Issue #53/PR #81.

## Goals / Non-Goals

**Goals:**
- Make callback-originated panic handling silent and fail-open before `catch_unwind` returns.
- Preserve prior process panic behavior outside input evaluation.
- Prevent a caught payload's destructor from escaping the C boundary.
- Establish durable decision and guardrail provenance without changing existing invariants.

**Non-Goals:**
- New C ABI symbols, runtime fault-control APIs, native thread registration, hook restoration during ordinary teardown, helper/IPC, per-event global-hook mutation, or rich hot-path diagnostics.
- A strict latency pass: the reference-Mac benchmark remains required evidence and is not produced by this change.

## Decisions

### Install once before engine allocation

The FFI crate owns a single process-global panic hook. Creation uses synchronized uninstalled/installing/installed state: one creator installs outside the installation-state lock before allocating an engine or allowing native input delivery; every additional creator during installation fails open with a null owner without waiting; installation failure returns to uninstalled for a later retry; and success publishes installed exactly once for the process lifetime. It captures the prior hook and intentionally leaves the installed policy in place through ordinary engine destruction.

This removes default-hook work from the callback path without holding a lock across `take_hook`, `set_hook`, or a panic path. Alternatives rejected: default hook (may synchronously output), per-event `set_hook`/`take_hook` (global race and hot-path mutation), restore-on-destroy (unsafe with multiple handles/later hook owners), and a native registration symbol (unnecessary ABI expansion).

### Classify only evaluation's dynamic extent with TLS

A private const-initialized thread-local Boolean is set around the dynamic extent of the evaluation export and cleared on every exit path. Scope entry and marker restoration use non-panicking access: an unavailable marker fails evaluation open as Panic plus Preserve, while an unavailable marker in the hook is treated as unmarked and delegates to the captured previous hook. The installed hook reads it on the panicking thread: marked evaluation returns immediately; unmarked panics delegate to the captured previous hook.

This is narrower than process-wide silence and avoids platform thread-affinity assumptions. Alternatives rejected: silencing all panics (loses unrelated diagnostics), inferring native input threads (platform ownership leakage), or callback-provided flags/new ABI parameters (wider contract).

### Preserve ABI fail-open result and contain payload disposal

The callback diagnostic remains existing `Panic` status plus already initialized Preserve output. Each caught panic payload is dropped inside a second `catch_unwind`; if that destructor panics, the secondary payload is retained with `mem::forget` so it cannot be dropped again. Each pathological secondary payload is intentionally retained for that occurrence; repeated occurrences may retain additional payloads.

Alternatives rejected: letting either payload drop outside containment (can unwind over C), aborting (cannot fulfill fail-open result), or diagnosing synchronously inside the callback (violates hot-path constraints).

### Require unwind-capable compilation and test public ABI

The FFI crate adds a compile-time guard rejecting `panic = "abort"`. Existing private `cfg(test)` injection remains internal and is used only to drive assertions through existing public ABI calls. Public-ABI tests cover hook suppression for evaluation panic, prior-hook delegation for unrelated panic, Panic plus Preserve, startup installation failure/null owner, retry and exactly-once success, overlapping creator failure, policy persistence after destruction, and payload-drop containment. No new mock, trait, test seam, or production API is introduced.

### Record ADR and only additive guardrail provenance

Create ADR 0005 recording this process-lifetime policy. Add it as a canonical source to active guardrails whose runtime/reliability invariants it directly implements (expected DG-RT-001 and DG-REL-001); only add DG-VER-001 if the canonical linkage specifically concerns its established public ABI evidence. Do not change a guardrail's invariant, trigger, enforcement, waiver, or lifecycle.

After implementation, reconcile Issue #53's archived evidence to mark its historic completion claim superseded by the live #82 blocker/policy evidence, without reopening or rewriting the accepted behavioral specification.

## Risks / Trade-offs

- [Another library installs a hook later] → The policy intentionally owns its hook for this process lifetime; detect only through behavior/tests where feasible, do not invent hook-chaining management.
- [TLS clear is skipped on panic] → Use RAII scope cleanup around evaluation dynamic extent and test panic paths through the ABI.
- [Payload drop panics] → Nest disposal containment and retain only the secondary caught payload.
- [Startup hook installation fails] → Return non-success with null owner and leave native delivery disabled.
- [Hook work affects latency] → Suppression path must perform only TLS lookup/branch; strict reference-Mac latency remains NOT_PROVEN until benchmark evidence exists.

## Migration Plan

1. Add ADR 0005 and minimal canonical-source pointers, without changing guardrail rules.
2. Add compile guard and process-lifetime hook installation before engine allocation.
3. Add TLS-scoped evaluation classification, nested caught-payload disposal, and public ABI tests.
4. Run `just check`, `just test`, `just ci`, `openspec validate --all --no-interactive`, and the reference-Mac benchmark when available.
5. Reconcile archived Issue #53 evidence after the live policy and verification are established; rollback before input delivery by failing creation with a null owner. Do not restore the process hook during ordinary destruction.

## STOP Conditions

STOP implementation and return to Issue/Wayfinder decision if any requirement arises for:
- a new C symbol, native input-thread registration, production fault API, helper/IPC, per-event hook change, or hook restoration protocol;
- a panic strategy other than selected unwind containment, or payload behavior needing unbounded retention/retry;
- synchronous hook-path output, formatting, allocation, logging, diagnostics, blocking, or I/O;
- a guardrail invariant weakening, waiver, or lifecycle change rather than an additive canonical-source link;
- an interpretation conflicting with newer Issue #82/53 decisions or requiring strict latency acceptance without reference-Mac evidence.
