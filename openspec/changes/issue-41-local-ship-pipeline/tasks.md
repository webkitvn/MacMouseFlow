## 1. Candidate provenance

- [x] 1.1 Add the canonical `just local-build` path that runs `just ci`, retains Rust 1.98.1 and Xcode 26.6 pins, builds `io.github.webkitvn.macmouseflow`, ad-hoc signs it, and verifies its signature on the macOS 26.6.2 reference Mac; verify from a clean checkout.
- [x] 1.2 Prove the static-linkage candidate runs after relocation outside the checkout with no checkout or `target/` dependency; if and only if that fails without ABI/toolchain/architecture change, implement embedded-dylib bundle-relative loading and inside-out signing; verify the selected artifact is self-contained and its executable exits 0 within 5 seconds.

## 2. macOS 26 local lifecycle (reference Mac)

- [x] 2.1 Implement active and rollback handling at `~/Applications/MacMouseFlow.app` and `~/Library/Application Support/io.github.webkitvn.macmouseflow/LocalShip/rollback/MacMouseFlow.app`, retaining exactly one rollback bundle; verify a successful update replaces the active bundle only after candidate launch proof.
- [x] 2.2 Validate active and rollback bundle identity, expected executable, ad-hoc signature, and launch probe before mutation; verify foreign or malformed content aborts without changing active, rollback, or configuration state.
- [x] 2.3 Implement failed-candidate restoration and configuration evidence using existence, byte length, and SHA-256, with an opaque sentinel outside `LocalShip/` when config is absent; verify failure restores the known-good bundle and preserves byte-identical evidence.
- [x] 2.4 Exercise actual clean install and launch on the macOS 26.6.2 reference Mac; verify the installed canonical executable exits 0 within 5 seconds and record signature/install/launch evidence.
- [x] 2.5 Exercise update and failed-update rollback on the macOS 26.6.2 reference Mac; verify one rollback bundle, abort-without-mutation failures, restored known-good launch, and unchanged configuration evidence.
- [x] 2.6 Exercise documented uninstall on the macOS 26.6.2 reference Mac; verify the active artifact is removed and report the remaining documented local state without touching runtime configuration.

## 3. macOS 14 same-artifact lifecycle (hosted compatibility)

- [ ] 3.1 Transport the exact candidate artifact produced in section 1/2 — never rebuilt — to the repository's existing GitHub-hosted `macos-14` runner; verify its SHA-256 digest and ad-hoc signature match before transport and again after transport.
- [ ] 3.2 Exercise install, launch-probe, update, failure rollback, and uninstall lifecycle compatibility for that same artifact on the hosted `macos-14` runner, using the same mechanical criteria as the reference-Mac lifecycle; explicitly exclude TCC/Accessibility permission grants, live `CGEventTap` input capture, and strict latency/benchmark claims from this row.
- [ ] 3.3 Gate: the macOS 14 lifecycle-compatibility row SHALL PASS before this change may archive or close; if the hosted runner or the transported artifact is unavailable or incompatible, mark this row `NOT PROVEN` and return to Issue #41 for a lead decision — never substitute macOS 26 evidence for it and never lower this acceptance criterion.

## 4. Evidence reconciliation / validation / archive handoff

- [ ] 4.1 Run `just ci` from a clean checkout and record its result alongside both the macOS 26 reference-Mac lifecycle evidence and the macOS 14 hosted-compatibility evidence; verify no benchmark or smoke gate is added unless a runtime seam changed.
- [x] 4.2 Run `openspec validate issue-41-local-ship-pipeline --strict --no-interactive`; verify all proposal artifacts are coherent and no locked exclusion has been crossed.
- [x] 4.3 Map each acceptance requirement to its macOS 26 evidence and, separately, its macOS 14 hosted-compatibility evidence; record explicitly that macOS 26 evidence does not substitute for the macOS 14 row; mark any unavailable mandatory evidence `NOT PROVEN`; verify readiness for the mandatory archive workflow without archiving in this task.
