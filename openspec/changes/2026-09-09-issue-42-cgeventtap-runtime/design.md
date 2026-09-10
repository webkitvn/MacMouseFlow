## Context

See `proposal.md` for motivation and the delta specs for observable behavior. At baseline `81826b7b0736fab09f5fb198f62c170d20361c01`, `macos/App`, `macos/Bridge`, and `macos/Platform` are ownership placeholders; the Rust evaluator, fixed-layout C header, opaque engine lifetime, panic containment, and public C contract already exist. Issue #42's resolution localizes the remaining event encoding/mutation policy to the native adapter.

The callback is a realtime-sensitive boundary. Swift/AppKit owns lifecycle, permissions, primitive `CGEvent` extraction/application, and platform I/O outside the callback. Rust owns normalized semantics and `Input Decision`. Failure preserves the original event.

## Goals / Non-Goals

**Goals:**

- Establish the smallest testable Swift package/application structure that owns one session `CGEventTap` and links the existing C ABI.
- Keep the callback bounded and allocation/locking behavior auditable.
- Normalize only documented LineBased integer fields and apply only validated Replace decisions.
- Prove on macOS 14 that canonical integer-field mutation exposes the intended public LineBased reversal without project-owned derived-field conversion.

**Non-Goals:**

- Settings UI, persistence, per-device behavior, Source Class detection, PixelBased transformation, phase/momentum semantics, replacement event posting, observability export, or a new test-only production seam.
- ABI widening, Rust evaluator changes, helper/IPC/HID architecture, or a second runtime path.

## Decisions

### Use a session active-filter tap with a scroll-only normal mask

Create the tap at the session location, at the head insertion point, as an active filter for `scrollWheel`, on one dedicated non-UI thread/run loop. The callback branches first on lifecycle-disabled event types, then on `scrollWheel`, and preserves anything else. The owner creates, enables, disables, removes, and destroys the tap on that run loop before releasing the engine.

Alternative: listen-only cannot apply Replace. HID-entry tap requires broader privilege and violates the chosen topology.

### Separate native extraction/application from tap lifecycle

Keep primitive extraction and decision application as small value-oriented functions in the Platform module, called by the lifecycle callback. The functions operate on established Core Graphics and ABI values; no new protocol is introduced solely for tests. Deterministic tests use synthetic `CGEvent` values at the documented system boundary and the real C ABI/Rust library for the integration path.

Alternative: a bespoke mock protocol would create a test-only seam. A monolithic callback would make fail-open and mutation ordering difficult to prove.

### Normalize LineBased integer axes only

Read `scrollWheelEventIsContinuous`; return PixelBased unchanged. For LineBased, read integer Axis1/Axis2 and map to vertical/horizontal `int64` values without sign normalization. Fill the published event version/size/reserved fields and always use Source Class `Unknown`.

Alternative: FixedPt-first requires a fractional-to-`int64` policy absent from the ABI. PointDelta represents pixels and would require an undefined line-to-pixel conversion.

### Stage replacement validation before canonical mutation

Validate ABI status, decision tag/version/size/reserved fields, and replacement values before the first native setter. Preserve returns immediately. Replace writes only integer Axis1/Axis2. Project code does not write FixedPt, PointDelta, or phase/momentum; Core Graphics owns any derived representation changes and their exact numbers are not correctness values.

Because Core Graphics setters do not expose recoverable failure, tests must establish that all required preconditions are checked before mutation. No branch after the first setter may newly decide to fail open. If implementation discovers a possible post-mutation failure, STOP rather than adding rollback complexity or cloning/reconstructing events without a decision.

Alternative: reconstructing an event risks losing timestamp, flags, source, and opaque metadata. Explicitly synchronizing FixedPt or PointDelta adds hot-path work and forces the project to own undocumented conversion semantics.

### Retain engine ownership across callback delivery

Create the engine and install configuration before enabling the tap. The runtime owner retains the opaque handle for the full period in which callback delivery is possible, disables/removes the tap before destruction, and never destroys concurrently with evaluation. Only ABI Busy during startup follows its existing bounded retry contract; callback evaluation does not retry.

### Keep lifecycle recovery bounded

On `tapDisabledByTimeout` or `tapDisabledByUserInput`, invoke the single native tap re-enable operation and return the original event. Do not log synchronously, rebuild state, parse configuration, or perform unbounded retries in the callback. Observability remains a later dependent slice.

### Gate minimum-target public behavior, not derived values

Add the smallest public-seam check that constructs `.line` events with Core Graphics, mutates only integer Axis1/Axis2, and verifies reversed LineBased behavior through `NSEvent(cgEvent:)`. Run it in hosted CI on macOS 14. FixedPt and PointDelta may be emitted as diagnostics only; never encode incidental platform values as expected literals. The smoke harness configures reverse before enabling its tap. The release benchmark drives the same callback dispatch body with a fixed mixed trace and atomic configuration swaps.

## Risks / Trade-offs

- [Core Graphics may change derived scroll representations when integer fields change] → Own only DeltaAxis1/2; verify public LineBased behavior on macOS 14 and do not assert derived numeric values.
- [Core Graphics object mutation is in-place] → Complete all fallible validation before setters; STOP if a newly discovered failure can occur after mutation.
- [Synthetic events differ from hardware events] → Pair deterministic synthetic tests with live LineBased/PixelBased reference-Mac smoke.
- [Strict latency is noisy and host-specific] → Keep timing out of hosted CI acceptance and use canonical `just benchmark` on the reference Mac.
- [Always-Unknown Source Class leaves future enum variants unused] → Accept this bounded v0.1 policy; add classification only after documented correctness need and a separate decision.

## Migration Plan

1. Add the native Swift build/test structure without changing Rust/C contracts.
2. Implement deterministic extraction, ABI integration, decision application, and lifecycle tests red-to-green.
3. Run the public-API behavior check on hosted macOS 14 before accepting the integer-only mutation policy.
4. Run canonical local checks, then reference-Mac smoke and benchmark.
5. If integer setters cannot expose the intended LineBased reversal on macOS 14, or any other recorded STOP condition occurs, preserve input, stop Issue #42 implementation, and return to planning. Otherwise archive the validated OpenSpec change and close the issue with evidence.

Rollback is removal/disablement of the native event tap; the Rust engine and ABI remain independently usable and original input remains unaffected.
