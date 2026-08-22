# Keep hot-path tracing bounded and drain structured diagnostics asynchronously

For M0 and v0.1, observability uses a project-owned structured trace pipeline: the input callback may only build a compact preallocated record and attempt a non-blocking enqueue into a bounded buffer; overflow drops diagnostics rather than delaying input. Work outside the callback serializes versioned JSON Lines into bounded rotating files and mirrors only low-volume lifecycle, warning, error, and fault events to macOS Unified Logging. Each run and input can be correlated across native → Rust → returned `Input Decision` without making observability metadata part of domain semantics, and the canonical diagnostic workflow is exposed through `just trace-tail` and `just trace-export`.

## Considered Options

- Unified Logging only: rejected as the sole diagnostic source because the project needs a stable machine-readable trace artifact spanning native and Rust with project-owned schema and correlation.
- A general telemetry/export framework from M0: rejected because a single-process local dogfood app does not yet justify exporter, networking, or telemetry-stack complexity.
- Direct JSON serialization or file logging in the input callback: rejected because it violates the established latency and fail-open constraints.

## Consequences

Detailed dev/dogfood tracing is compiled in and can be enabled without adding temporary instrumentation. The hot path performs no disk or network I/O, no synchronous logging, no unbounded allocation, and no blocking on observability; trace loss is represented explicitly by drop counters. Persisted diagnostics use an allowlisted schema that excludes raw platform event objects and user-sensitive dynamic content. The detailed trace store is size-bounded and rotating, while low-volume Unified Logging remains available for Console/system diagnosis and crash-adjacent context. Trace-on performance is part of the existing reference-Mac callback latency gate rather than a separate relaxed path.
