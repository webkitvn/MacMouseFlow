# Support macOS 14+ on Apple Silicon (arm64) only through v1

For v0.x through v1, MacMouseFlow supports macOS 14+ on Apple Silicon (`arm64`) only. Intel `x86_64`, Rosetta 2 translation, and Universal Binary (`arm64`+`x86_64` fat binary) distribution are explicitly unsupported and deferred past v1, not merely untested (PR #90 review comment, https://github.com/webkitvn/MacMouseFlow/pull/90#issuecomment-5658089402; user-approved). No production artifact, build path, or hosted CI row may accept, silently tolerate, or claim compatibility with a non-`arm64` binary; a GitHub-hosted runner's OS-version label (`macos-26`, `macos-14`) is not itself an architecture assertion and must not be treated as one.

## Considered Options

- Ship a Universal Binary (`arm64` + `x86_64`) so both architectures work out of the box. Rejected: doubles the build, signing, and hosted-CI verification surface for a v1 that has no committed Intel user base; a future decision can revisit this if Intel demand materializes.
- Accept Intel via Rosetta 2 translation without a native `x86_64` slice. Rejected: silently running translated, unverified behavior under a fail-open `CGEventTap` adapter is an untested correctness and support risk this project has not evaluated, and an honest claim would need its own verification lane anyway.

## Consequences

Every build, packaging, and verification path — local `just local-build`, the Rust FFI release artifact, and both hosted `macos-26` and `macos-14` GitHub Actions rows — must assert the produced or verified binary is exactly `arm64` by inspecting the binary itself, never by inferring architecture from a runner label. No runtime CPU-architecture detection, Intel acceptance path, Rosetta compatibility work, or Universal Binary packaging may be added before a future decision revisits this boundary. Reversing this decision later (adding Intel or Universal support) is a substantial, independently-scoped effort, not a quick config flip, which is why it is recorded here rather than left implicit.
