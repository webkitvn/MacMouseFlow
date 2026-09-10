## Why

Issue #42 must materialize the native macOS input path that connects the established C ABI to a real session `CGEventTap`. Without it, the Rust evaluator cannot receive live scroll input and bridge or native failures cannot yet be proven to preserve the original event.

## What Changes

- Add a macOS session event-tap runtime on a dedicated non-UI run loop/thread with explicit permission, creation, enablement, disablement, and teardown behavior.
- Translate LineBased native scroll events from integer Axis1/Axis2 fields into vertical/horizontal signed line steps with `source_class=Unknown`, invoke the Rust engine through the existing ABI, and apply successful decisions to the native event.
- On Replace, write only the canonical integer line fields. Never explicitly write FixedPt or PointDelta; Core Graphics owns any derived native representation changes.
- Preserve the original event for unexpected input, pixel-based scroll, unavailable permission, tap failure, ABI/engine failure, panic status, or processing fault.
- Re-enable the tap after system timeout/user-input disable notifications without performing UI, disk/network I/O, synchronous logging, config parsing, or unbounded blocking/locking in the callback.
- Add deterministic tests through the native adapter boundary, reverse-configured canonical live smoke, and release-build reference-Mac real-event-tap callback latency evidence; synthetic timing is diagnostic only.

## Capabilities

### New Capabilities
- `macos-cgeventtap-runtime`: Session event-tap lifecycle, native scroll extraction/application, callback safety, timeout recovery, and fail-open behavior.

### Modified Capabilities
- `c-input-engine-abi`: Require the native caller to use the established ABI status/decision contract so every bridge failure preserves the original event.

## Impact

- Affects `macos/App`, `macos/Bridge`, and `macos/Platform`, which currently contain only ownership placeholders.
- Uses the existing header and exports in `rust/ffi/include/pointer_input_ffi.h` and `rust/ffi/src/lib.rs`; no new process, IPC, HID takeover, production fault-control seam, or cross-boundary heap ownership is introduced.
- Extends deterministic native/ABI integration coverage and makes `just smoke` and `just benchmark` meaningful for Issue #42 acceptance.
- Requires a macOS 14 hosted-CI public-API compatibility check; strict live reliability and latency remain reference-Mac evidence.
- Bound to Issue #42, its translation resolution and amendment comment `5598663408`, parent epic #49, baseline `81826b7b0736fab09f5fb198f62c170d20361c01`, closed dependencies #53 and #47, ADRs 0001-0005, and active guardrails DG-DOM-001, DG-ARCH-001, DG-RT-001, DG-REL-001, DG-VER-001, DG-VER-002, DG-SOT-001, DG-PROV-001, and DG-PROV-002.
