## Purpose

Defines the repeatable local development artifact lifecycle for MacMouseFlow without expanding it into public distribution or an updater product.

## ADDED Requirements

### Requirement: Produce a verified local development artifact
The project SHALL provide `just local-build` as the documented command path that, from a clean checkout at the selected revision, runs `just ci`, builds a self-contained `io.github.webkitvn.macmouseflow` macOS development artifact, ad-hoc signs it, and verifies that signature before the artifact is eligible for installation. It SHALL first prove static linkage by running the candidate after moving it outside the checkout with no dependency on the checkout or `target/`; only if that cannot achieve self-containment without a new ABI, toolchain, or architecture MAY it use an embedded dylib with bundle-relative loading and inside-out signing (nested code first, bundle last). The path SHALL target macOS 14 as the product's deployment target and retain Rust 1.98.1 and Xcode 26.6 pins; that deployment target is independent of the build host OS version. This candidate build and signing step SHALL run on the available macOS 26.6.2 reference Mac. It SHALL not require Developer ID, notarization, or automatic quarantine removal.

The project supports macOS 14+ on Apple Silicon (`arm64`) only through v1 (ADR-0006). The Rust FFI release build SHALL target `aarch64-apple-darwin` explicitly rather than the host's default target triple, and the produced artifact's main executable SHALL be a thin `arm64` Mach-O binary, never a Universal Binary. `just local-build` SHALL verify this by inspecting the built executable's architecture directly before the artifact is eligible for signing; it SHALL NOT infer architecture support from a build host's or hosted runner's OS-version label.

#### Scenario: Clean checkout produces an eligible artifact
- **WHEN** the documented path runs from a clean checkout with its required local tools available
- **THEN** `just ci` passes, static-linkage self-containment is proven or the defined embedded-dylib fallback is used, the built executable is verified to be a thin `arm64` binary, and one self-contained, ad-hoc-signed artifact passes signature verification

#### Scenario: Verification or signing fails
- **WHEN** canonical verification, building, signing, or signature verification fails
- **THEN** no newly produced artifact is eligible for installation and any known-good artifact remains available

#### Scenario: Non-arm64 or Universal binary aborts
- **WHEN** the built executable's architecture inspection reports anything other than a thin `arm64` binary, including a Universal Binary containing an `x86_64` slice
- **THEN** the build path aborts before signing, no such artifact becomes eligible for installation, and any known-good artifact remains available

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
The documented path SHALL independently build a candidate via the identical canonical `just local-build` procedure on the repository's existing GitHub-hosted `macos-26` runner declared in `.github/workflows/ci.yml`, then transport that hosted-built artifact — byte-identical, never rebuilt again after this point, and never the physical macOS 26.6.2 reference Mac's own build — to the repository's existing GitHub-hosted `macos-14` runner. It SHALL verify the artifact's SHA-256 digest and ad-hoc signature match before transport and again after transport onto the hosted `macos-14` runner. The hosted macOS 14 runner SHALL exercise install, launch-probe, update, failure rollback, and uninstall lifecycle compatibility for that same hosted-built artifact using the same mechanical criteria as the macOS 26.6.2 reference Mac (bundle identity, expected executable, ad-hoc signature, 5-second exit-0 probe). Hosted macOS 14 evidence SHALL NOT claim TCC/Accessibility permission grants, live `CGEventTap` input capture, or strict latency/benchmark results; those remain properties of the macOS 26.6.2 reference Mac only. This row and the macOS 26.6.2 reference-Mac local lifecycle evidence are independently gathered and SHALL NOT substitute for, nor be described as sharing the provenance of, one another. This row SHALL PASS before the change may archive or close; if the hosted runner or the transported artifact is unavailable or fails compatibility, this row SHALL be recorded `NOT PROVEN` and the change SHALL return to Issue #41 for a lead decision instead of lowering or skipping this acceptance criterion.

Both the hosted `macos-26` build step and the hosted `macos-14` receiving step SHALL assert the artifact's architecture is a thin `arm64` binary by inspecting the binary itself (ADR-0006); the `macos-26`/`macos-14` runner OS-version labels SHALL NOT be treated as an architecture assertion on their own.

#### Scenario: Same artifact transported and verified
- **WHEN** the candidate artifact built by CI on the hosted macOS 26 runner is transported to the hosted macOS 14 runner
- **THEN** its SHA-256 digest, ad-hoc signature, and `arm64` architecture are verified identical before and after transport, and the macOS 14 runner performs no rebuild

#### Scenario: Hosted macOS 14 lifecycle compatibility passes
- **WHEN** the hosted macOS 14 runner installs, launches, updates, rolls back on failure, and uninstalls the transported hosted-built artifact
- **THEN** each step succeeds using the same launch-probe and rollback criteria as the macOS 26.6.2 reference Mac, without exercising TCC/Accessibility permission grants, live `CGEventTap` capture, or latency/benchmark measurement, and without describing this artifact as sharing the physical reference Mac's build provenance

#### Scenario: Hosted macOS 14 unavailable or incompatible
- **WHEN** the hosted macOS 14 runner or the transported artifact is unavailable, incompatible, or fails verification
- **THEN** the macOS 14 lifecycle row is recorded `NOT PROVEN`, the change does not archive or close, and the blocker returns to Issue #41 instead of substituting macOS 26.6.2 reference-Mac evidence or lowering acceptance

### Requirement: Preserve failure safety and pre-v1 boundaries
A failed local install or update SHALL not replace the known-good artifact and SHALL not unexpectedly change runtime configuration. Before mutating an existing active copy in any lifecycle action — install, rollback, or uninstall alike — the path SHALL validate its bundle ID, expected executable, ad-hoc signature, and launch probe; any foreign or malformed active copy, or unexpected or malformed rollback content, SHALL abort without mutation. Lifecycle tooling SHALL own only `LocalShip/` and SHALL not read, parse, migrate, rewrite, delete, or repair runtime configuration. It SHALL prove configuration unchanged by existence, byte length, and SHA-256 before and after; when real configuration is absent, it SHALL use an opaque sentinel outside `LocalShip/` in app-owned Application Support and prove it byte-identical. The local pipeline SHALL not add an updater or installer subsystem, process, helper, daemon, runtime ABI change, or input behavior change. Its only persistent state is exactly one canonical rollback bundle, plus the single bounded terminal recovery bundle below; it SHALL not add any further persistent pipeline state store. It SHALL not add Intel `x86_64` acceptance, Rosetta 2 compatibility handling, Universal Binary packaging, or runtime CPU-architecture detection; the project supports macOS 14+ on Apple Silicon (`arm64`) only through v1 (ADR-0006).

A directory-swap step (install's retain-known-good promotion, or rollback's active-swap) MAY create exactly one pipeline-owned, distinctly-named terminal recovery bundle, and only when both the commit move and the automatic restoration move of that swap fail (a true double filesystem failure), leaving the canonical target genuinely missing. This is not a second rollback slot or version history: the lifecycle path SHALL report its exact path in the structured failure result, SHALL NOT describe the canonical target as preserved in this branch, and SHALL remove the recovery bundle automatically on the next successful lifecycle action rather than retain it.

Relocating the doomed content into the terminal recovery bundle SHALL always be attempted first on a true double filesystem failure. Only if that relocation itself also fails — a true triple filesystem failure — SHALL the lifecycle path stop attempting any further relocation; it SHALL NOT make a fourth attempt at another location, and SHALL NOT relocate or reuse that content again. It SHALL instead report, in the structured failure result, the exact existing pipeline-owned path where the last recoverable known-good content already safely sits (the disposable slot the failed relocation attempt read from, itself never moved or deleted by that attempt), and SHALL NOT describe the canonical target or the canonical terminal recovery bundle as preserved in this branch.

A true triple filesystem failure SHALL place the pipeline into a terminal BLOCKED state, superseding the prior self-cleaning treatment (lead decision, Issue #41; PR #90 review comment #5658378644). The surviving path and its content SHALL NOT be automatically relocated, reused, or cleaned up by this pipeline, ever. Every subsequent automated lifecycle action (`install`, `rollback`, `uninstall`) SHALL detect this BLOCKED state before attempting any mutation and SHALL refuse to proceed, returning a structured failure that names the exact surviving path and states that operator resolution is required, rather than attempting to route around, relocate, or clear it automatically. Only an explicit operator action outside this pipeline clears this state and allows automated lifecycle actions to resume.

#### Scenario: Failed replacement preserves state
- **WHEN** installation fails, the installed executable exits nonzero, terminates by signal, encounters dynamic-loader failure, or does not exit within 5 seconds
- **THEN** the single known-good rollback bundle remains restorable and configuration evidence is unchanged

#### Scenario: Foreign or malformed copy aborts
- **WHEN** an active copy fails identity, executable, ad-hoc-signature, or launch-probe validation, or rollback content is unexpected or malformed, during install, rollback, or uninstall
- **THEN** the lifecycle path aborts without mutating the active artifact, rollback bundle, or runtime configuration

#### Scenario: Double filesystem failure during a directory swap
- **WHEN** a directory-swap step's commit move fails and its automatic restoration move also fails
- **THEN** the canonical target is reported as genuinely missing (never as preserved), the bundle that would otherwise be destroyed is preserved at a single documented, named terminal recovery path reported in the failure result, and that recovery bundle is removed automatically by the next successful lifecycle action

#### Scenario: Triple filesystem failure during a directory swap
- **WHEN** a directory-swap step's commit move fails, its automatic restoration move also fails, and the relocation of the doomed content into the terminal recovery path also fails
- **THEN** the lifecycle path makes no further relocation attempt, reports the exact existing pipeline-owned path where the content already safely sits in the structured failure result, does not describe the canonical target or the canonical terminal recovery bundle as preserved, enters a terminal BLOCKED state, and never automatically relocates, reuses, or cleans up that surviving path

#### Scenario: Automated lifecycle action refuses while a terminal BLOCKED state is outstanding
- **WHEN** a subsequent `install`, `rollback`, or `uninstall` runs while a prior true triple filesystem failure's surviving path has not yet been resolved by an operator
- **THEN** the lifecycle action detects the outstanding BLOCKED state before attempting any mutation, refuses to proceed, and returns a structured failure naming the exact surviving path and stating that operator resolution is required

#### Scenario: Unsupported distribution request
- **WHEN** execution would require Developer ID, notarization, public distribution, automatic quarantine removal, or a new helper, daemon, or process
- **THEN** execution stops for a lead decision instead of extending this capability

#### Scenario: Unsupported architecture request
- **WHEN** execution would require Intel `x86_64` acceptance, Rosetta 2 compatibility handling, Universal Binary packaging, or runtime CPU-architecture detection (ADR-0006)
- **THEN** execution stops for a lead decision instead of extending this capability
