# Own Rust panic handling at the FFI process boundary

For M0 and v0.1, `pointer-input-ffi` installs one process-global Rust panic hook before allocating an engine or enabling input delivery. It owns that policy for the process lifetime and does not ordinarily restore it during engine destruction. The installed hook suppresses work only while a const-initialized thread-local marker identifies the dynamic extent of FFI input evaluation; outside that extent, it delegates to the captured prior hook so unrelated application panics retain their prior behavior.

The FFI crate requires `panic = "unwind"`. During marked evaluation, a panic hook returns without stderr output, backtrace generation, formatting, allocation, logging, or diagnostic enqueue. TLS access uses non-panicking lookup: unavailable TLS is treated as unmarked and delegates to the prior hook, while evaluation-scope entry failure returns the existing fail-open `Panic` status with Preserve. Caught payload disposal occurs inside a second `catch_unwind`; if disposal panics, the secondary payload is intentionally retained with `mem::forget` so neither panic escapes the ABI. If hook installation fails, creation returns a non-success status with a null owner and native input delivery must not begin.

Hook installation uses three synchronized states: uninstalled, installing, and installed. One creator installs outside the state lock. Concurrent creation may wait outside input evaluation for installation to finish; prior-hook-reentrant creation on the installing thread returns non-success with a null owner rather than waiting. A failed attempt returns to uninstalled so a later creation can retry, and a successful attempt publishes installed exactly once.

## Considered Options

- Keep Rust's default hook: rejected because it can synchronously write or generate a backtrace before `catch_unwind` returns.
- Replace or take the hook per event: rejected because it mutates process-global state on the hot path and races.
- Silence all process panics: rejected because unrelated application panics lose their existing diagnostics.
- Register native input threads through a new C ABI: rejected because a dynamic evaluation marker identifies the actual call without widening the ABI or taking platform ownership.
- Use `panic = "abort"` or abort on payload-drop panic: rejected because neither can return the accepted fail-open ABI result.
- Restore the hook on engine destruction: rejected because it is unsafe with multiple handles or later hook owners and is unnecessary in the selected process-lifetime topology.

## Consequences

The native adapter retains lifecycle and input-delivery ownership; Rust owns only its process-level panic policy at the FFI boundary. Existing private `cfg(test)` injection remains an internal test driver, with assertions through the public ABI and no production fault-control API. Public ABI tests serialize process-global hook manipulation, restore their test-owned prior hook after the test, and demonstrate hook suppression, non-input delegation, payload-drop containment, and fail-open startup/evaluation behavior. Strict hot-path latency remains unproven until the canonical reference-Mac benchmark runs.
