# Keep hot-path tests at public seams and separate CI regression gates from absolute latency gates

For the input hot path, verify behavior through the Rust engine seam, the fixed-layout C ABI/native adapter seam, and a live macOS smoke seam rather than testing internal collaborators. CI must always enforce deterministic behavior/reliability and catch large performance regressions, while absolute latency is checked on a reference Mac because hosted-runner timing is noisy; the project budget is p99 ≤ 100 µs for the C ABI + Rust evaluation path and p99 ≤ 500 µs / p99.9 ≤ 1 ms for the full event-tap callback path, with no sample above 2 ms in the reference benchmark. These numbers are internal engineering budgets, not Apple API guarantees.

## Consequences

Mocks/fakes are allowed only at macOS/system boundaries. A release benchmark uses a warmed release build and a fixed synthetic trace; any event-tap timeout is a release blocker until explained. If later hardware or behavior shows these budgets are either needlessly strict or insufficient, change them through a new decision rather than silently weakening tests.
