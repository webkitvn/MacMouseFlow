## Purpose

Defines the repeatable local development artifact lifecycle for MacMouseFlow without expanding it into public distribution or an updater product.

## ADDED Requirements

### Requirement: Produce a verified local development artifact
The project SHALL provide `just local-build` as the documented command path that, from a clean checkout at the selected revision, runs `just ci`, builds a self-contained `io.github.webkitvn.macmouseflow` macOS development artifact, ad-hoc signs it, and verifies that signature before the artifact is eligible for installation. It SHALL first prove static linkage by running the candidate after moving it outside the checkout with no dependency on the checkout or `target/`; only if that cannot achieve self-containment without a new ABI, toolchain, or architecture MAY it use an embedded dylib with bundle-relative loading and inside-out signing (nested code first, bundle last). The path SHALL target macOS 14 as the product's deployment target and retain Rust 1.98.1 and Xcode 26.6 pins; that deployment target is independent of the build host OS version. This candidate build and signing step SHALL run on the available macOS 26.6.2 reference Mac. It SHALL not require Developer ID, notarization, or automatic quarantine removal.

#### Scenario: Clean checkout produces an eligible artifact
- **WHEN** the documented path runs from a clean checkout with its required local tools available
- **THEN** `just ci` passes, static-linkage self-containment is proven or the defined embedded-dylib fallback is used, and one self-contained, ad-hoc-signed artifact passes signature verification

#### Scenario: Verification or signing fails
- **WHEN** canonical verification, building, signing, or signature verification fails
- **THEN** no newly produced artifact is eligible for installation and any known-good artifact remains available

### Requirement: Exercise the local artifact lifecycle
The documented path SHALL exercise actual installation, launch, update, rollback, and uninstall of the local artifact on the macOS 26.6.2 reference Mac rather than only inspect command text. Its active installation SHALL be `~/Applications/MacMouseFlow.app`; its single pipeline-owned rollback bundle SHALL be `~/Library/Application Support/io.github.webkitvn.macmouseflow/LocalShip/rollback/MacMouseFlow.app`. It SHALL report evidence for each completed lifecycle action. This macOS 26 evidence proves the pipeline's own mechanics; it SHALL NOT be treated as macOS 14 acceptance evidence.

#### Scenario: Install and launch
- **WHEN** an eligible artifact is installed through the documented local path
- **THEN** its main executable at the canonical installed path exits with status 0 within 5 seconds

#### Scenario: Update and rollback
- **WHEN** a known-good installed artifact is replaced by a newly eligible artifact
- **THEN** the path retains exactly one known-good rollback bundle until the replacement installs and its main executable exits 0 within 5 seconds, and restores that bundle when replacement installation or launch fails

#### Scenario: Uninstall
- **WHEN** the documented local uninstall path runs
- **THEN** it removes the installed local artifact and reports the documented remaining local state

### Requirement: Prove same-artifact lifecycle compatibility on hosted macOS 14
The documented path SHALL transport the exact candidate artifact produced and signed on the macOS 26.6.2 reference Mac — byte-identical, never rebuilt — to the repository's existing GitHub-hosted `macos-14` runner declared in `.github/workflows/ci.yml`. It SHALL verify the artifact's SHA-256 digest and ad-hoc signature match before transport and again after transport onto the hosted runner. The hosted macOS 14 runner SHALL exercise install, launch-probe, update, failure rollback, and uninstall lifecycle compatibility for that same artifact using the same mechanical criteria as the macOS 26 reference Mac (bundle identity, expected executable, ad-hoc signature, 5-second exit-0 probe). Hosted macOS 14 evidence SHALL NOT claim TCC/Accessibility permission grants, live `CGEventTap` input capture, or strict latency/benchmark results; those remain properties of the macOS 26.6.2 reference Mac only. macOS 26 local lifecycle evidence SHALL NOT substitute for this macOS 14 row. This row SHALL PASS before the change may archive or close; if the hosted runner or the transported artifact is unavailable or fails compatibility, this row SHALL be recorded `NOT PROVEN` and the change SHALL return to Issue #41 for a lead decision instead of lowering or skipping this acceptance criterion.

#### Scenario: Same artifact transported and verified
- **WHEN** the candidate artifact from the macOS 26 reference Mac is transported to the hosted macOS 14 runner
- **THEN** its SHA-256 digest and ad-hoc signature are verified identical before and after transport, and the runner performs no rebuild

#### Scenario: Hosted macOS 14 lifecycle compatibility passes
- **WHEN** the hosted macOS 14 runner installs, launches, updates, rolls back on failure, and uninstalls the transported artifact
- **THEN** each step succeeds using the same launch-probe and rollback criteria as the macOS 26 reference Mac, without exercising TCC/Accessibility permission grants, live `CGEventTap` capture, or latency/benchmark measurement

#### Scenario: Hosted macOS 14 unavailable or incompatible
- **WHEN** the hosted macOS 14 runner or the transported artifact is unavailable, incompatible, or fails verification
- **THEN** the macOS 14 lifecycle row is recorded `NOT PROVEN`, the change does not archive or close, and the blocker returns to Issue #41 instead of substituting macOS 26 evidence or lowering acceptance

### Requirement: Preserve failure safety and pre-v1 boundaries
A failed local install or update SHALL not replace the known-good artifact and SHALL not unexpectedly change runtime configuration. Before replacing an existing active copy, the path SHALL validate its bundle ID, expected executable, ad-hoc signature, and launch probe; any foreign or malformed active copy, or unexpected or malformed rollback content, SHALL abort without mutation. Lifecycle tooling SHALL own only `LocalShip/` and SHALL not read, parse, migrate, rewrite, delete, or repair runtime configuration. It SHALL prove configuration unchanged by existence, byte length, and SHA-256 before and after; when real configuration is absent, it SHALL use an opaque sentinel outside `LocalShip/` in app-owned Application Support and prove it byte-identical. The local pipeline SHALL not add an updater or installer subsystem, persistent pipeline state store, process, helper, daemon, runtime ABI change, or input behavior change.

#### Scenario: Failed replacement preserves state
- **WHEN** installation fails, the installed executable exits nonzero, terminates by signal, encounters dynamic-loader failure, or does not exit within 5 seconds
- **THEN** the single known-good rollback bundle remains restorable and configuration evidence is unchanged

#### Scenario: Foreign or malformed copy aborts
- **WHEN** an active copy fails identity, executable, ad-hoc-signature, or launch-probe validation, or rollback content is unexpected or malformed
- **THEN** the lifecycle path aborts without mutating the active artifact, rollback bundle, or runtime configuration

#### Scenario: Unsupported distribution request
- **WHEN** execution would require Developer ID, notarization, public distribution, automatic quarantine removal, or a new helper, daemon, or process
- **THEN** execution stops for a lead decision instead of extending this capability
