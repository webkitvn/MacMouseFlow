# Version the fractional LineBased Scroll Amount ABI

**Status:** Accepted

## Context

ADR-0001 keeps the native adapter and platform-neutral Rust engine in one process, joined by a narrow fixed-layout C ABI. Its current native application rule uses integer scroll fields only. Issue #117 requires fractional `Scroll Amount` for `LineBased` input without changing that architecture. `PixelBased` input remains preserved.

The app ships Swift and Rust together and has no external ABI consumer. The existing known-good whole-bundle rollback mechanism is the rollback boundary.

## Considered Options

- Keep a whole-line-only ABI and approximate fractional amounts: rejected because it cannot express the required stateless fractional magnitude exactly in Rust/domain and the ABI. Native application may quantize that exact semantic value to 16.16 precision.
- Add v2 beside v1 with capability negotiation or reinterpret v1 data: rejected because there is no independent ABI consumer, and interpreting v1 as v2 risks corrupting the meaning of a known-good bundle.
- Represent amounts with `f64`, residual accumulation, momentum, or smoothing: rejected because they add state or nondeterministic precision where fixed integer hundredths express the required range.
- Apply fractional values through native integer Delta fields alone: rejected because public-API probes show the FixedPt fields retain fractional LineBased values.

## Decision

This ADR is additive to ADR-0001 and narrowly supersedes only Issue #42's integer-field-only native application rule for fractional axes.

- Replace and rename the hot-path ABI as v2; do not keep parallel in-process v1/v2 compatibility, negotiate capabilities, or reinterpret v1 data as v2. Swift and Rust ship as one bundle; rollback selects the existing known-good whole bundle.
- Rust domain output and the v2 C ABI represent each replacement axis as exact signed `i64` hundredths-of-a-line (`100 == 1 line`), not CGEvent 16.16 fixed-point. Input remains signed `i64` whole lines. Valid `Scroll Amount` is integer percent 25...400, with neutral percent 100 preserving the original magnitude. Input `+1 @ 25%`, `+1 @ 50%`, and `+1 @ 137%` yields `+25`, `+50`, and `+137` hundredths respectively.
- Direction reversal and Scroll Amount are orthogonal. Compute multiplication and negation with checked operations; overflow or any evaluation failure returns `EvaluationFailed` and Preserve, retaining the fail-open boundary.
- Preserve `PixelBased` input unchanged. Do not add `f64`, residual state, momentum, smoothing, helpers, IPC, HID takeover, or a process.
- Native application keeps the established integer Delta field path for axes whose resulting hundredths are divisible by 100. Integral Delta is limited by the conservative project policy `[-32768, 32767]`, established by the local public-API boundary probe; this is not a universal Apple platform limit. Fractional axes use only `scrollWheelEventFixedPtDeltaAxis1` (vertical) or `scrollWheelEventFixedPtDeltaAxis2` (horizontal) through the public `CGEventSetDoubleValueField` setter. Convert hundredths to `Double` only at that Swift/Core Graphics setter boundary; domain and ABI values remain exact integers. Native fixed-point readback may differ from the exact hundredths target by an absolute error of at most `1/65536` line. PointDelta and `isContinuous` remain unowned: do not write either.
- Before mutating any replacement axis, native application preflights every axis as a whole decision: integral values must be in `[-3276800, 3276700]` hundredths and fractional values in `[-3276800, 3276799]` hundredths. If any value is out of range, mutate no axis or native field and preserve the original input, including otherwise-valid axes. Representability here means within range, not exact binary encoding of every hundredth; `1.37` is valid within the stated precision. The setter returns `void`; never attempt a write and rely on setter status or readback to detect representability failure.

## Consequences

The callback remains bounded to extraction, one fixed-layout ABI evaluation, and application of its decision; it performs no UI/MainActor work, I/O, synchronous logging, parsing, or unbounded waiting. Failure preserves the original event. Tests continue at established engine, ABI/native-adapter, and live macOS seams; strict latency claims still require the reference-Mac benchmark, not hosted timing.

## Evidence and References

The public-API probe on the reference Mac (macOS 26.6.2) and GitHub macOS-14 gate both passed. Run <https://github.com/webkitvn/MacMouseFlow/actions/runs/36221387128> succeeded on `macos-14-arm64` (macOS 14.8.9), with `allChecksPass=true`. Fractional FixedPt-only writes retained LineBased classification (`isContinuous == 0`, `hasPreciseScrollingDeltas == false`) and matching `NSEvent` scrolling-delta axis/sign mapping. Requested `1.37` read back as `1.3699951171875` (raw `89784`), an error of `0.0000048828125` line, below `1/65536`. The probe wrote no PointDelta field and did not mutate `isContinuous`; fractional cases also showed no observed PointDelta change. Integral Delta writes may cause derived PointDelta changes, so no-write does not imply universal field immutability.

The hosted runner is functional cross-version evidence only, not latency acceptance. These probes establish sampled public-API behavior and native-field precision, not a universal Apple range limit, posted-event/device behavior, or broader compatibility. The local boundary probe supports only the conservative integral Delta policy above. Those implementation checks remain at the established public seams; strict latency acceptance requires reference-Mac evidence.

- ADR-0001 — native adapter/Rust engine boundary
- ADR-0002 — public seam and reference-Mac latency evidence
- `docs/guardrails/registry.yaml`: DG-ARCH-001, DG-REL-001, DG-RT-001, DG-VER-001, and DG-VER-002
