## Why

The repository verifies source but does not yet produce a self-contained local macOS development artifact or prove its lifecycle. M0 needs one repeatable clean-checkout path that preserves a known-good artifact and runtime configuration when install or update fails.

## What Changes

- Add a canonical local pipeline from clean checkout through `just ci`, build, ad-hoc signing, artifact verification, and a documented local lifecycle.
- Define actual install, launch, update, rollback, and uninstall evidence for the artifact on the available macOS 26.6.2 reference Mac. Separately, define a same-artifact lifecycle-compatibility row that builds a candidate via the identical canonical `just local-build` procedure on the repository's existing GitHub-hosted `macos-26` runner, then transports that exact hosted-built artifact unmodified to the existing GitHub-hosted `macos-14` runner. These two rows are independently gathered and neither substitutes for nor claims the provenance of the other (lead decision, Issue #41): the reference-Mac row proves the procedure on real end-user hardware, and the hosted row proves the same procedure's artifact is lifecycle-compatible with macOS 14 on GitHub's infrastructure. The macOS 14 row must pass before archive.
- Keep the prior known-good artifact available until a replacement has installed and launched successfully; preserve runtime configuration on failed install or update.
- Add no distribution service, installer/updater subsystem, process, helper, daemon, runtime ABI, or input-spec change. Persistent pipeline state is limited to exactly one canonical rollback bundle, plus a single, bounded, pipeline-owned named terminal recovery bundle that MAY exist only immediately after a true double filesystem failure during a directory swap; it is reported explicitly and removed automatically by the next successful lifecycle action, never retained as version history (lead decision, Issue #41). Relocation into that terminal recovery bundle is always attempted first; only if that relocation itself also fails (a true triple filesystem failure) does the pipeline stop moving the content further and enter a terminal BLOCKED state (lead decision, Issue #41; PR #90 review comment #5658378644, superseding the prior self-cleaning treatment): it reports the exact existing pipeline-owned surviving path, never automatically relocates, reuses, or cleans that path up, and every subsequent automated lifecycle action refuses to proceed until an operator resolves it manually — this is never a new slot, never a license to keep chasing further fallback paths, and never a condition this pipeline clears by itself.
- Make the architecture support boundary explicit end to end (ADR-0006; PR #90 review comment, user-approved): the produced artifact is a thin `arm64` binary — never a Universal Binary — the Rust FFI release build targets `aarch64-apple-darwin` explicitly, and every verification surface (local `just local-build`, and both the hosted `macos-26` and `macos-14` rows) asserts the built or verified binary is exactly `arm64` by inspecting the binary itself, never by inferring architecture from a GitHub-hosted runner's OS-version label. No runtime CPU-architecture detection, Intel `x86_64` acceptance path, Rosetta 2 compatibility work, or Universal Binary packaging is in scope; macOS 14+ on Apple Silicon only is the supported boundary through v1.
- Exclude Developer ID, notarization, public distribution, and automatic quarantine removal before v1.

## Capabilities

### New Capabilities
- `local-macos-ship-pipeline`: A repeatable, ad-hoc-signed local macOS development artifact and its verified install/update/rollback/uninstall lifecycle.

### Modified Capabilities
- None.

## Impact

Expected implementation is limited to existing canonical command routing, macOS package/build inputs, and repository documentation or verification surfaces necessary to produce and exercise the local artifact. `just ci` remains the source-verification gate. Existing Rust C ABI, input runtime behavior, configuration format and ownership, and one-process topology are unchanged. No macOS 14 physical or virtual machine is locally available, and CI cannot reach the physical reference Mac's build output; the only macOS 14 surface in scope is the existing GitHub-hosted `macos-14` runner already declared in `.github/workflows/ci.yml`, fed by an independent build on the existing GitHub-hosted `macos-26` runner, used for artifact-transport lifecycle compatibility only. The reference Mac and both hosted runners happen to run Apple Silicon hardware today, but that is an incidental infrastructure fact, not the basis for the architecture claim (ADR-0006): the Rust FFI release build explicitly targets `aarch64-apple-darwin`, and local build/candidate packaging and both hosted CI rows explicitly assert the produced or verified binary's architecture via binary inspection, independent of and never inferred from the runner's OS-version label.

Bound to GitHub Issue #41, baseline `cabf05d986bdf9fe95e8ae477495ccd2eea15046`; upstream context: #11, #4, #15, #7, and #49.
