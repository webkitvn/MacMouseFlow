# Keep platform adapters native and the input engine in Rust

For M0 and v0.1, run a single macOS app process: Swift/AppKit owns application lifecycle, permissions, `CGEventTap` lifecycle and translation between platform events and a narrow C ABI, while Rust owns platform-neutral normalization, scroll semantics, configuration evaluation and `Input Decision`. Do not add a helper/XPC process or HID seize/virtual-device path for v0.1; the first dogfood slice transforms documented line-based scroll input and preserves pixel-based continuous scroll by default rather than pretending that public `CGEvent` data provides physical device identity.

## Considered Options

- Put `CGEventTap` ownership directly in Rust: rejected for v0.1 because it expands platform binding/unsafe surface without evidence that one bounded FFI call per event is the latency bottleneck.
- Split input handling into a helper or service process: rejected for M0/v0.1 because it adds IPC, lifecycle, permission and pre-v1 signing complexity before a capability requires process isolation.
- Use per-device HID seize and re-emission: rejected for v0.1 because correct takeover would substantially widen compatibility and fail-safe work; revisit when a later release truly requires physical-device correctness.

## Consequences

The event callback must run off the UI thread, perform only bounded extraction/FFI/application of the returned decision, and fail open by preserving the original event on bridge or engine failure. The FFI hot path uses fixed-layout value data with no cross-boundary heap ownership; configuration updates, persistence and logging stay outside the callback. Test/benchmark work must measure the per-event bridge cost, and any future move to Rust-owned capture, a helper process or HID-level takeover requires a new decision rather than an implicit refactor.
