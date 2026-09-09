## 1. Native build and public seams

- [x] 1.1 Add the minimal macOS Swift build/test structure for App, Bridge, and Platform at the existing ownership boundaries; verify it targets macOS 14, imports CoreGraphics/AppKit, links the existing C ABI, and runs through `just test`.
- [ ] 1.2 Add red deterministic tests using synthetic public `CGEvent` values for scroll-only scope, lifecycle notifications, LineBased/PixelBased classification, Axis1→vertical and Axis2→horizontal mapping, signed preservation, and Source Class `Unknown`; verify the targeted tests fail for missing behavior without adding a test-only production seam.

## 2. Bounded adapter and ABI integration

- [ ] 2.1 Implement LineBased extraction into exact-layout ABI values, bypass PixelBased and unexpected events unchanged, and keep phase/momentum opaque; verify the deterministic extraction tests pass.
- [ ] 2.2 Integrate the real C ABI/Rust engine with owner-retained lifetime and pre-mutation status/decision validation; verify system/default Preserve, reverse `Axis1 +3`/`Axis2 -2`→`-3`/`+2`, and every ABI/native/engine fault preserve the original event.
- [ ] 2.3 Apply Replace in place by writing only integer DeltaAxis1/2; verify deterministic public-seam tests cover the expected canonical deltas, complete PixelBased preservation, phase/momentum independence, no project assertions about derived FixedPt/PointDelta values, and no partial mutation path.

## 3. Event-tap lifecycle

- [ ] 3.1 Implement permission preflight plus active session `CGEventTap` creation, enablement, run-loop ownership, disablement, and teardown for a normal `scrollWheel` mask; verify startup failure leaves input unaffected and teardown precedes engine destruction.
- [ ] 3.2 Handle `tapDisabledByTimeout` and `tapDisabledByUserInput` as bounded re-enable notifications without engine translation, UI/MainActor work, I/O, synchronous logging, parsing, or unbounded recovery; verify lifecycle tests pass.

## 4. Acceptance evidence

- [ ] 4.1 Add and run the public-API LineBased behavior check using only integer DeltaAxis1/2 setters; verify reversed behavior through `NSEvent(cgEvent:)` on hosted macOS 14 without asserting exact FixedPt/PointDelta values, or STOP if integer setters are insufficient and a project-owned conversion would be required.
- [ ] 4.2 Replace the Issue #42 `just smoke` and `just benchmark` placeholders with the minimum canonical runners, add the macOS 14 deterministic behavior CI gate, and verify `just check`, `just test`, `just ci`, and `openspec validate --all --no-interactive` pass locally.
- [ ] 4.3 Run `just smoke` and `just benchmark` on the reference Mac across 100,000 events; record LineBased replacement, PixelBased preservation, zero `tapDisabledByTimeout`, p99 ≤ 500 µs, p99.9 ≤ 1 ms, and max ≤ 2 ms, otherwise leave strict acceptance `NOT_PROVEN`.
- [ ] 4.4 Map every Issue #42 acceptance criterion to concrete evidence, post the verified handoff to the Issue, and archive only after OpenSpec validation, coherence evidence, deterministic tests, live smoke, and reference-Mac benchmark all pass.
