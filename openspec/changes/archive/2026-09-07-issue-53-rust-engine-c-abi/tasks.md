## 1. Establish the public Rust evaluator contract

- [x] 1.1 Write failing public engine tests for accepted Unknown Source Class, source-independent behavior, LineBased system/reverse decisions including one-axis and both-zero inputs, overflow Preserve with non-success status, PixelBased preservation, and separate status/Preserve fail-open results; verified the tests failed against the scaffold before engine behavior existed.
- [x] 1.2 Implement the minimum platform-neutral engine value types, checked `i64` LineBased evaluator, and `AtomicU32` configuration snapshot without unsafe code or new dependencies; verified the public engine tests pass (`cargo test -p pointer-input-engine --test evaluator`).

## 2. Establish the fixed C ABI contract test-first

- [x] 2.1 Add failing public FFI contract tests for `_v1` version/size/reserved checks, enum validation, null required pointers, initialized Preserve output, valid configuration updates, and status/decision separation; verified the tests failed against the scaffold and now cover invalid event source/granularity plus invalid configuration version/size/reserved while confirming invalid updates leave the active configuration unchanged.
- [x] 2.2 Define the manually maintained C header and matching primitive fixed-width `#[repr(C)]` POD types, opaque engine pointer, `_v1` declarations, status values, layout rules, and caller ownership rules; verified Rust layout/contract tests and C compilation consume the checked-in header. Create requires a null owner variable and rejects a live owner unchanged; the owner uniquely destroys, and non-owning copies may update/evaluate concurrently while owner-retained lifetime holds.
- [x] 2.3 Implement minimal safe conversion and export code with exact layout validation, `catch_unwind`, output-first Preserve initialization, configuration delegation, and pointer-to-handle destruction that nulls before free; verified all Rust FFI contract tests pass (`cargo test -p pointer-input-ffi`), evaluation failure preserves output, and repeated create leaves the live owner unchanged without allocation.
- [x] 2.4 Add a private `cfg(test)` panic latch only if a public export panic path cannot otherwise be demonstrated; verified it is absent from production API and the panic contract test observes non-success status plus Preserve (`cargo test -p pointer-input-ffi`).

## 3. Prove native C interoperability

- [x] 3.1 Add a small C contract program that includes the published header and verifies create/configure/evaluate/destroy, malformed layouts, deterministic one-axis and both-zero LineBased plus PixelBased decisions, status/Preserve failure behavior, and repeated destruction through the same handle variable; verified it compiles, links, and runs against the ABI library (`just test`).
- [x] 3.2 Route the real C compile/link/run contract program through `just test` without adding a new framework or generated bindings; verified `just test` runs both existing checks and the C program on the supported development toolchain.

## 4. Validate and hand off

- [x] 4.1 Run `just check`, `just test`, and the relevant workspace build gate; verified `just check`, `just test` (including C compile/link/run), and `just ci` pass with no product API for source inference, Device Identity, suppression, platform ownership, cross-boundary heap ownership, or latency proof.
- [x] 4.2 Run `openspec validate --all --no-interactive`, map every delta-spec requirement to command/test evidence, and update this task list with completed checkboxes only after observed success; verified validation passes. `evaluator.rs` covers source independence, LineBased/PixelsBased behavior, and status/decision separation; `abi.rs` covers layout, input/config validation, fail-open output, atomic configuration, and lifetime; `abi_contract.c` proves the public C contract; `cargo test --workspace --locked`, `just check`, `just test`, and `just ci` pass with no unresolved STOP condition.
- [x] 4.3 Archive after implementation evidence is complete: synced `c-input-engine-abi` and `rust-input-evaluator` into main specs, validated the sync with `openspec validate --specs`, and moved this change under `openspec/changes/archive/`; archive completion is the final evidence for Issue #53.
