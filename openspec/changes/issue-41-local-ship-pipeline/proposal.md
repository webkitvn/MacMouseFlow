## Why

The repository verifies source but does not yet produce a self-contained local macOS development artifact or prove its lifecycle. M0 needs one repeatable clean-checkout path that preserves a known-good artifact and runtime configuration when install or update fails.

## What Changes

- Add a canonical local pipeline from clean checkout through `just ci`, build, ad-hoc signing, artifact verification, and a documented local lifecycle.
- Define actual install, launch, update, rollback, and uninstall evidence for the artifact on the available macOS 26.6.2 reference Mac, plus a same-artifact lifecycle-compatibility row for the exact candidate on the repository's existing GitHub-hosted `macos-14` runner; the macOS 26 row never substitutes for the macOS 14 row, and the macOS 14 row must pass before archive.
- Keep the prior known-good artifact available until a replacement has installed and launched successfully; preserve runtime configuration on failed install or update.
- Add no distribution service, installer/updater subsystem, persistent pipeline state, process, helper, daemon, runtime ABI, or input-spec change.
- Exclude Developer ID, notarization, public distribution, and automatic quarantine removal before v1.

## Capabilities

### New Capabilities
- `local-macos-ship-pipeline`: A repeatable, ad-hoc-signed local macOS development artifact and its verified install/update/rollback/uninstall lifecycle.

### Modified Capabilities
- None.

## Impact

Expected implementation is limited to existing canonical command routing, macOS package/build inputs, and repository documentation or verification surfaces necessary to produce and exercise the local artifact. `just ci` remains the source-verification gate. Existing Rust C ABI, input runtime behavior, configuration format and ownership, and one-process topology are unchanged. No macOS 14 physical or virtual machine is locally available; the only macOS 14 surface in scope is the existing GitHub-hosted `macos-14` runner already declared in `.github/workflows/ci.yml`, used for artifact-transport lifecycle compatibility only.

Bound to GitHub Issue #41, baseline `cabf05d986bdf9fe95e8ae477495ccd2eea15046`; upstream context: #11, #4, #15, #7, and #49.
