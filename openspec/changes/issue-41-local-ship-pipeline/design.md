## Context

See `proposal.md` and `specs/local-macos-ship-pipeline/spec.md`. At baseline `cabf05d986bdf9fe95e8ae477495ccd2eea15046`, `just ci` verifies source and `macos/Package.swift` produces a Swift package executable rather than an app bundle. The package declares macOS 14. Existing pins are Rust 1.98.1 and Xcode 26.6. Configuration is native-owned in Application Support and unknown newer configuration is preserved for rollback.

The only available reference Mac for this change runs macOS 26.6.2; no macOS 14 physical or virtual machine is locally reachable, and CI cannot reach that physical machine's build output. The repository already declares GitHub-hosted `macos-26` and `macos-14` runners in `.github/workflows/ci.yml`. Those hosted runners are the sole macOS 14 acceptance surface in scope: the hosted `macos-26` runner independently builds a candidate via the identical canonical `just local-build` procedure, and that hosted-built artifact — never rebuilt again after this point, and never the physical reference Mac's own build — is transported unmodified to the hosted `macos-14` runner. This hosted-to-hosted chain is a separate, non-substitutable evidence row from the macOS 26.6.2 reference-Mac lifecycle evidence (lead decision, Issue #41): neither row stands in for the other, and neither claims to be the other's provenance.

The pipeline's persistent state is exactly one canonical rollback bundle, plus one bounded exception: a pipeline-owned, named terminal recovery bundle that MAY exist temporarily, and only immediately after a true double filesystem failure during a directory swap (see "Bounded terminal recovery bundle on double filesystem failure" below; lead decision, Issue #41).

MacMouseFlow supports macOS 14+ on Apple Silicon (`arm64`) only through v1; Intel `x86_64`, Rosetta 2 translation, and Universal Binary distribution are explicitly unsupported and deferred (ADR-0006; PR #90 review comment, https://github.com/webkitvn/MacMouseFlow/pull/90#issuecomment-5658089402, user-approved). The reference Mac and both existing hosted `macos-26`/`macos-14` runners happen to run Apple Silicon hardware today, but a runner's OS-version label is not itself an architecture assertion; this change must make the `arm64`-only boundary explicit in the build and verification path itself rather than rely on that incidental infrastructure fact (see "Apple Silicon (arm64)-only artifact and verification" below).

## Goals / Non-Goals

**Goals:**
- Add one canonical `just local-build` path after `just ci` for an ad-hoc-signed, self-contained local `.app`.
- Make local replacement transactional using exactly one known-good rollback bundle.
- Exercise full artifact lifecycle behavior (install, launch, update, rollback, uninstall) on the macOS 26.6.2 reference Mac without changing runtime behavior.
- Prove that a candidate built via the same canonical `just local-build` procedure on the existing GitHub-hosted `macos-26` runner is lifecycle-compatible, byte-identical and unmodified, on the existing GitHub-hosted `macos-14` runner, with integrity verified by SHA-256 and ad-hoc signature before and after transport, as a required, non-substitutable acceptance row distinct from — and never claiming the provenance of — the macOS 26.6.2 reference-Mac evidence.
- Make the `arm64`-only architecture boundary explicit in the build and verification path itself (ADR-0006): the Rust FFI release build targets `aarch64-apple-darwin`, the produced local artifact is a thin `arm64` binary, and local build/candidate packaging and both hosted CI rows assert that architecture by inspecting the binary, never by inferring it from a runner's OS-version label.

**Non-Goals:**
- Developer ID, hardened runtime, notarization, public distribution, automatic quarantine removal, or a general installer/updater.
- Persistent pipeline state beyond the one canonical rollback bundle and the single, bounded, self-cleaning terminal recovery bundle permitted only after a true double filesystem failure (see "Bounded terminal recovery bundle on double filesystem failure"); a helper, process, daemon, ABI, input, configuration-semantic, or permission change.
- Intel `x86_64` support, Rosetta 2 compatibility work, Universal Binary (fat) packaging, or any runtime CPU-architecture detection (ADR-0006); these are explicitly deferred past v1, not merely untested.

## Decisions

### Canonical build and self-containment proof
`just local-build` begins with `just ci`; it does not duplicate source verification. It produces bundle ID `io.github.webkitvn.macmouseflow`, ad-hoc signs it, and verifies that signature. First, use a static-linkage experiment: move the candidate outside the checkout and prove it runs without dependency on the checkout or `target/`. If static linkage cannot achieve this without a new ABI, toolchain, or architecture, use the embedded-dylib fallback with bundle-relative loading and inside-out signing: nested code first, bundle last.

Alternative: assume the current dynamic library layout works, or add distribution signing. Rejected: neither proves self-containment within the locked local scope.

### Fixed local paths and one rollback bundle
The active bundle is `~/Applications/MacMouseFlow.app`. The pipeline owns exactly one canonical rollback bundle at `~/Library/Application Support/io.github.webkitvn.macmouseflow/LocalShip/rollback/MacMouseFlow.app`, plus the single bounded terminal recovery bundle described below. The active copy is validated (bundle ID, expected executable, ad-hoc signature, and launch probe) before every mutation that would touch it — install, rollback, and uninstall alike — not install alone. Foreign or malformed active copies, and unexpected or malformed rollback content, abort without mutation.

Alternative: select arbitrary install locations or retain multiple history versions. Rejected: it weakens safety or adds unnecessary state.

### Bounded terminal recovery bundle on double filesystem failure
The pipeline's only persistent version-history state is the one canonical rollback bundle above. A directory-swap step (install's retain-known-good promotion, or rollback's active-swap) that suffers a true double filesystem failure — the commit move fails *and* the automatic restoration move also fails, leaving the canonical target genuinely missing — MAY create exactly one pipeline-owned, distinctly-named terminal recovery bundle holding the bundle that would otherwise be destroyed. This is not a second rollback slot or version history: it exists only in this fault branch, its path is reported explicitly in the structured failure result (which never claims the canonical target was preserved in this branch), and it is removed automatically by the next successful lifecycle action (install, rollback, or uninstall) rather than retained. Outside this true double-failure branch, no such bundle is ever created, and the single-canonical-rollback-bundle invariant holds exactly as before.

Alternative: never allow a second slot under any circumstance and delete the last recoverable copy on a double failure. Rejected (lead decision, Issue #41): silently destroying a user's only remaining working bundle on a rare filesystem fault is worse than a bounded, self-cleaning, explicitly-reported exception. Alternative: retain the recovery bundle indefinitely as manual-recovery history. Rejected: that is exactly the unbounded persistent state this change excludes; the next successful lifecycle action must clear it.

### M0 launch probe
Execute the installed main executable at its canonical path; success is normal exit status 0 within 5 seconds. Dynamic-loader failure, a signal/crash, nonzero exit, or timeout fails. A resident process is not required because the current app intentionally exits. If that runtime behavior changes, stop and update this criterion before implementation.

Alternative: require a resident GUI process. Rejected: it is incompatible with current M0 behavior.

### Two independent evidence rows: macOS 26.6.2 reference Mac, and hosted macOS 26-to-macOS 14 compatibility
Two evidence rows exist, independently gathered, and neither substitutes for nor claims the provenance of the other (lead decision, Issue #41):

1. **macOS 26.6.2 reference-Mac lifecycle evidence.** The physical macOS 26.6.2 reference Mac produces its own candidate (`just local-build`, ad-hoc signed, signature-verified) and executes the full local lifecycle — install, launch-probe, update, failure rollback, uninstall — on that same physical machine. This proves the canonical build/lifecycle procedure works on real, non-hosted end-user hardware.
2. **Hosted macOS 26-to-macOS 14 same-artifact compatibility evidence.** The repository's existing GitHub-hosted `macos-26` runner independently builds a candidate via the identical canonical `just local-build` procedure. That hosted-built artifact — never the physical reference Mac's build, and never rebuilt again after this point — is transported unmodified to the repository's existing GitHub-hosted `macos-14` runner. Before and after transport, its SHA-256 digest and ad-hoc signature are re-verified identical. The hosted `macos-14` runner then exercises install, launch-probe, update, rollback, and uninstall lifecycle *compatibility* for that artifact using the same mechanical criteria (bundle identity, expected executable, signature, 5-second exit-0 probe).

Hosted macOS 14 evidence never claims TCC/Accessibility permission grants, live `CGEventTap` input capture, or strict latency/benchmark results — those remain properties of the macOS 26.6.2 reference-Mac row only, consistent with the existing repository rule that strict latency evidence comes from the reference Mac, not hosted CI timing. The macOS 14 row must PASS before this change may archive or close. If the hosted runner or the transported artifact is unavailable or fails compatibility, the macOS 14 row is recorded `NOT PROVEN` and the change returns to Issue #41 for a lead decision; it does not lower or skip this acceptance criterion.

Alternative: claim the macOS 14 row proves the physical reference Mac's own build is compatible with macOS 14. Rejected (lead decision, Issue #41): CI cannot reach the physical machine's build output without a new artifact-transport mechanism, which is out of scope; the hosted-to-hosted chain is the truthful claim this change can make. Alternative: treat macOS 26.6.2 reference-Mac evidence as sufficient on its own, or run the full lifecycle (including permission-gated behavior) on the hosted runner. Rejected: the first silently drops the only macOS 14 acceptance surface this change has access to; the second claims guarantees a headless, unattended hosted runner without TCC/Accessibility grants and without live input hardware cannot provide.

### Apple Silicon (arm64)-only artifact and verification
MacMouseFlow supports macOS 14+ on Apple Silicon (`arm64`) only through v1 (ADR-0006; PR #90 review comment, user-approved). The Rust FFI release build used by `just local-build` explicitly targets `aarch64-apple-darwin` rather than the host's default target triple. The produced local artifact is a thin `arm64` Mach-O binary — never a Universal Binary (fat `arm64`+`x86_64`) — and `just local-build` verifies this by inspecting the built executable's architecture directly (e.g. `lipo -archs` or `file`) before it is eligible for ad-hoc signing. Both the hosted `macos-26` candidate-build row and the hosted `macos-14` lifecycle-compatibility row perform the same direct binary-architecture inspection on the artifact they build or receive; a GitHub-hosted runner's OS-version label (`macos-26`, `macos-14`) is incidental infrastructure, not an architecture assertion, and MUST NOT be treated as one. No runtime CPU-architecture detection, Intel `x86_64` acceptance path, Rosetta 2 compatibility handling, or Universal Binary packaging is added anywhere in this pipeline.

Alternative: infer architecture support from the GitHub-hosted runner's OS-version label, or from Xcode/Swift's default host-triple build behavior. Rejected (ADR-0006): a runner label is an infrastructure fact that could change independently of this project's support decision, and a default host-triple build silently tracks whatever architecture the build machine happens to be, neither of which is a truthful, durable assertion of the `arm64`-only support boundary. Alternative: build and ship a Universal Binary so the question is moot. Rejected (ADR-0006, PR #90): doubles the build/signing/verification surface for a v1 that has no committed Intel user base.

### Configuration remains opaque and untouched
Lifecycle tooling owns only `LocalShip/`; it neither reads nor modifies runtime configuration. Record configuration existence, byte length, and SHA-256 before and after lifecycle operations. If real configuration is absent, create an opaque sentinel outside `LocalShip/` in app-owned Application Support and prove it byte-identical.

Alternative: parse, export, or migrate configuration. Rejected: it changes configuration behavior and crosses the locked boundary.

## Risks / Trade-offs

- [Static linkage is unavailable] → use only the settled embedded-dylib fallback; stop if it requires ABI, toolchain, or architecture expansion.
- [A user has a foreign or malformed copy] → abort without mutation rather than attempting repair.
- [Launch proof no longer reflects runtime behavior] → stop and revise this criterion before implementation.
- [Lifecycle proof can leave local artifacts] → uninstall records only documented state and leaves runtime configuration untouched.
- [Hosted macOS 14 runner or artifact-transport compatibility is unavailable] → record the macOS 14 row `NOT PROVEN` and return to Issue #41; never substitute macOS 26.6.2 reference-Mac evidence for it, never claim the transported artifact's provenance is the physical reference Mac, and never lower this acceptance criterion to close the change.
- [A directory-swap step suffers a true double filesystem failure] → preserve the bounded terminal recovery bundle at its documented, named path, report it explicitly in the structured failure result without claiming the canonical target was preserved, and remove it automatically on the next successful lifecycle action; never retain it as version history.
- [A GitHub-hosted runner's architecture changes, or a build tool's default target triple silently drifts to a non-`arm64` architecture] → this pipeline's own explicit binary-architecture inspection catches it and aborts, rather than trusting the runner label or the toolchain default; never accept, translate, or silently widen to a non-`arm64` artifact (ADR-0006).

## Migration Plan

1. Retain Rust 1.98.1 and Xcode 26.6 pins; run `just ci` from a clean checkout.
2. Implement and prove the static-linkage candidate outside the checkout, or the bounded embedded-dylib fallback; the Rust FFI release build targets `aarch64-apple-darwin` explicitly, and the produced artifact's architecture is verified to be a thin `arm64` binary by direct inspection before it is eligible for signing (ADR-0006).
3. Install at the fixed active path on the macOS 26.6.2 reference Mac; validate pre-existing active/rollback content before every mutation that touches it (install, rollback, and uninstall alike).
4. Exercise update, failure rollback, and uninstall on the reference Mac using the installed executable 5-second probe and configuration evidence; implement the bounded terminal recovery bundle exception for true double filesystem failures during a directory swap, self-cleaning on the next successful lifecycle action.
5. On the existing GitHub-hosted `macos-26` runner, independently build a candidate via the identical canonical `just local-build` procedure, asserting the built artifact's architecture directly rather than inferring it from the runner label; transport that hosted-built artifact — never the physical reference Mac's build — unmodified to the existing GitHub-hosted `macos-14` runner; verify SHA-256, ad-hoc signature, and architecture match before and after transport, then exercise install/update/rollback/uninstall lifecycle compatibility there; record `NOT PROVEN` and return to Issue #41 if unavailable rather than closing without it.
6. Validate the OpenSpec change and archive only after all acceptance evidence — including a passing macOS 14 row and the `arm64`-only architecture assertions — is available.
