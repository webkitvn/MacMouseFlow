## Context

See `proposal.md` and `specs/local-macos-ship-pipeline/spec.md`. At baseline `cabf05d986bdf9fe95e8ae477495ccd2eea15046`, `just ci` verifies source and `macos/Package.swift` produces a Swift package executable rather than an app bundle. The package declares macOS 14. Existing pins are Rust 1.98.1 and Xcode 26.6. Configuration is native-owned in Application Support and unknown newer configuration is preserved for rollback.

The only available reference Mac for this change runs macOS 26.6.2; no macOS 14 physical or virtual machine is locally reachable. The repository already declares a GitHub-hosted `macos-14` runner in `.github/workflows/ci.yml`. That hosted runner is the sole macOS 14 surface in scope, and it is used only to prove lifecycle compatibility of the exact candidate artifact already built and signed on the macOS 26.6.2 reference Mac — never to rebuild it and never as a substitute for macOS 26 evidence or vice versa.

## Goals / Non-Goals

**Goals:**
- Add one canonical `just local-build` path after `just ci` for an ad-hoc-signed, self-contained local `.app`.
- Make local replacement transactional using exactly one known-good rollback bundle.
- Exercise full artifact lifecycle behavior (install, launch, update, rollback, uninstall) on the macOS 26.6.2 reference Mac without changing runtime behavior.
- Prove the exact same candidate artifact is lifecycle-compatible on the existing GitHub-hosted macOS 14 runner, with integrity verified by SHA-256 and ad-hoc signature before and after transport, as a required, non-substitutable acceptance row distinct from the macOS 26 evidence.

**Non-Goals:**
- Developer ID, hardened runtime, notarization, public distribution, automatic quarantine removal, or a general installer/updater.
- Persistent pipeline state beyond the one rollback bundle; a helper, process, daemon, ABI, input, configuration-semantic, or permission change.

## Decisions

### Canonical build and self-containment proof
`just local-build` begins with `just ci`; it does not duplicate source verification. It produces bundle ID `io.github.webkitvn.macmouseflow`, ad-hoc signs it, and verifies that signature. First, use a static-linkage experiment: move the candidate outside the checkout and prove it runs without dependency on the checkout or `target/`. If static linkage cannot achieve this without a new ABI, toolchain, or architecture, use the embedded-dylib fallback with bundle-relative loading and inside-out signing: nested code first, bundle last.

Alternative: assume the current dynamic library layout works, or add distribution signing. Rejected: neither proves self-containment within the locked local scope.

### Fixed local paths and one rollback bundle
The active bundle is `~/Applications/MacMouseFlow.app`. The pipeline owns exactly one rollback bundle at `~/Library/Application Support/io.github.webkitvn.macmouseflow/LocalShip/rollback/MacMouseFlow.app`. The active copy is update-eligible only when its bundle ID, expected executable, ad-hoc signature, and launch probe validate. Foreign or malformed active copies, and unexpected or malformed rollback content, abort without mutation.

Alternative: select arbitrary install locations or retain multiple history versions. Rejected: it weakens safety or adds unnecessary state.

### M0 launch probe
Execute the installed main executable at its canonical path; success is normal exit status 0 within 5 seconds. Dynamic-loader failure, a signal/crash, nonzero exit, or timeout fails. A resident process is not required because the current app intentionally exits. If that runtime behavior changes, stop and update this criterion before implementation.

Alternative: require a resident GUI process. Rejected: it is incompatible with current M0 behavior.

### Two-host lifecycle evidence: macOS 26 reference Mac and hosted macOS 14 compatibility
The macOS 26.6.2 reference Mac produces the canonical candidate (`just local-build`, ad-hoc signed, signature-verified) and executes the full local lifecycle: install, launch-probe, update, failure rollback, and uninstall. That is macOS 26 local lifecycle evidence. The exact same candidate artifact — not a rebuild — is then transported to the repository's existing GitHub-hosted `macos-14` runner. Before and after transport, its SHA-256 digest and ad-hoc signature are re-verified identical. The hosted runner exercises install, launch-probe, update, rollback, and uninstall lifecycle *compatibility* for that artifact using the same mechanical criteria (bundle identity, expected executable, signature, 5-second exit-0 probe). Hosted macOS 14 evidence never claims TCC/Accessibility permission grants, live `CGEventTap` input capture, or strict latency/benchmark results — those remain properties of the macOS 26.6.2 reference Mac only, consistent with the existing repository rule that strict latency evidence comes from the reference Mac, not hosted CI timing. macOS 26 evidence never substitutes for the macOS 14 row, and the macOS 14 row must PASS before this change may archive or close. If the hosted runner or the transported artifact is unavailable or fails compatibility, the macOS 14 row is recorded `NOT PROVEN` and the change returns to Issue #41 for a lead decision; it does not lower or skip this acceptance criterion.

Alternative: treat macOS 26 reference-Mac evidence as sufficient on its own, or run the full lifecycle (including permission-gated behavior) on the hosted runner. Rejected: the first silently drops the only macOS 14 acceptance surface this change has access to; the second claims guarantees a headless, unattended hosted runner without TCC/Accessibility grants and without live input hardware cannot provide.

### Configuration remains opaque and untouched
Lifecycle tooling owns only `LocalShip/`; it neither reads nor modifies runtime configuration. Record configuration existence, byte length, and SHA-256 before and after lifecycle operations. If real configuration is absent, create an opaque sentinel outside `LocalShip/` in app-owned Application Support and prove it byte-identical.

Alternative: parse, export, or migrate configuration. Rejected: it changes configuration behavior and crosses the locked boundary.

## Risks / Trade-offs

- [Static linkage is unavailable] → use only the settled embedded-dylib fallback; stop if it requires ABI, toolchain, or architecture expansion.
- [A user has a foreign or malformed copy] → abort without mutation rather than attempting repair.
- [Launch proof no longer reflects runtime behavior] → stop and revise this criterion before implementation.
- [Lifecycle proof can leave local artifacts] → uninstall records only documented state and leaves runtime configuration untouched.
- [Hosted macOS 14 runner or artifact-transport compatibility is unavailable] → record the macOS 14 row `NOT PROVEN` and return to Issue #41; never substitute macOS 26 evidence for it and never lower this acceptance criterion to close the change.

## Migration Plan

1. Retain Rust 1.98.1 and Xcode 26.6 pins; run `just ci` from a clean checkout.
2. Implement and prove the static-linkage candidate outside the checkout, or the bounded embedded-dylib fallback.
3. Install at the fixed active path on the macOS 26.6.2 reference Mac; validate pre-existing active/rollback content before every mutation.
4. Exercise update, failure rollback, and uninstall on the reference Mac using the installed executable 5-second probe and configuration evidence.
5. Transport the exact candidate artifact to the existing GitHub-hosted macOS 14 runner; verify SHA-256 and ad-hoc signature match before and after transport, then exercise install/update/rollback/uninstall lifecycle compatibility there; record `NOT PROVEN` and return to Issue #41 if unavailable rather than closing without it.
6. Validate the OpenSpec change and archive only after all acceptance evidence — including a passing macOS 14 row — is available.
