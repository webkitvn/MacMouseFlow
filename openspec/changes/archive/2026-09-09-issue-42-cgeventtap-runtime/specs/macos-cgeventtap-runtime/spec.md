## Purpose

Defines the macOS session event-tap lifecycle and bounded native adapter that translates supported scroll input through the existing engine ABI while preserving native events on every unsupported or failed path.

## ADDED Requirements

### Requirement: Operate a session scroll event tap safely
The runtime SHALL create an active session event tap whose normal event mask observes only `scrollWheel`. It SHALL manage permission, creation, enablement, disablement, and teardown explicitly. `tapDisabledByTimeout` and `tapDisabledByUserInput` SHALL be handled as lifecycle notifications and MUST NOT be translated into Rust input. The callback MUST perform no UI/MainActor work, disk or network I/O, synchronous logging, configuration parsing, or unbounded blocking, locking, retry, or recovery.

#### Scenario: Runtime starts with permission and a valid tap
- **WHEN** listen permission is available and the session event tap is created successfully
- **THEN** the runtime enables the tap and observes normal `scrollWheel` events

#### Scenario: Runtime startup fails open
- **WHEN** permission is unavailable or event-tap creation or enablement fails
- **THEN** native input remains unaffected and no event is delivered to the engine

#### Scenario: System disables the tap
- **WHEN** the callback receives `tapDisabledByTimeout` or `tapDisabledByUserInput`
- **THEN** the runtime handles it as a bounded lifecycle notification, does not translate it into engine input, and attempts only the defined tap re-enable action

### Requirement: Classify and extract supported scroll input
The adapter SHALL classify a `scrollWheel` event by reading `scrollWheelEventIsContinuous`: zero SHALL map to `LineBased` and nonzero SHALL map to `PixelBased`. For `LineBased`, it SHALL read `scrollWheelEventDeltaAxis1` and `scrollWheelEventDeltaAxis2` using integer accessors, map Axis1 to `vertical_lines` and Axis2 to `horizontal_lines`, preserve each signed value without assigning directional meaning, and emit `POINTER_INPUT_SOURCE_UNKNOWN_V1`. It SHALL populate the existing ABI version, exact size, granularity, and zero reserved fields. It MUST NOT infer Source Class or Device Identity.

#### Scenario: LineBased event is normalized
- **WHEN** a `scrollWheel` event has `scrollWheelEventIsContinuous` equal to zero, Axis1 `+3`, and Axis2 `-2`
- **THEN** the engine receives a valid LineBased event with `vertical_lines=+3`, `horizontal_lines=-2`, and Source Class `Unknown`

#### Scenario: PixelBased event bypasses evaluation
- **WHEN** a `scrollWheel` event has nonzero `scrollWheelEventIsContinuous`
- **THEN** the adapter returns the original event without mutating any scroll representation or phase/momentum field

#### Scenario: Unexpected event is preserved
- **WHEN** the callback receives a normal event outside the supported `scrollWheel` scope
- **THEN** it returns the original event without translating or mutating it

### Requirement: Apply decisions through canonical integer fields only
A successful Preserve decision SHALL return the original native event without mutation. For a successful Replace decision, the adapter SHALL set only integer DeltaAxis1 from `vertical_lines` and DeltaAxis2 from `horizontal_lines`. Project code MUST NOT explicitly set FixedPtDeltaAxis1/2 or PointDeltaAxis1/2, synthesize or post a replacement event stream, or modify phase/momentum fields. Core Graphics MAY update derived native scroll representations as a consequence of the integer setters; their exact values are platform-owned and MUST NOT become project correctness values. Granularity remains determined solely by `scrollWheelEventIsContinuous`.

#### Scenario: Reverse replacement updates canonical line fields
- **WHEN** LineBased Axis1 `+3` and Axis2 `-2` produce a successful Replace decision with vertical `-3` and horizontal `+2`
- **THEN** the adapter writes only DeltaAxis1 as `-3` and DeltaAxis2 as `+2`, returns the same LineBased native event, and makes no project assertion about derived FixedPt or PointDelta numbers

#### Scenario: Preserve leaves all native fields unchanged
- **WHEN** a valid LineBased event produces Preserve under system/default configuration
- **THEN** every native event field remains unchanged

#### Scenario: Opaque phase and momentum remain outside correctness
- **WHEN** a LineBased event contains phase or momentum metadata and produces Replace
- **THEN** the adapter neither reads those fields for eligibility nor explicitly writes them, and tests assign no semantic meaning to their raw values

### Requirement: Fail open across native and engine boundaries
The adapter SHALL treat every native extraction/application fault, missing or invalid engine handle, non-success ABI status, malformed decision, panic status, arithmetic failure, or other processing fault as Preserve. A failed path MUST return the original event without partial native mutation. The engine handle owner SHALL outlive callback use and MUST NOT be destroyed concurrently with evaluation.

#### Scenario: ABI evaluation fails
- **WHEN** the real ABI returns a non-success status or a Preserve decision for a LineBased event
- **THEN** the adapter returns the original native event without mutation

#### Scenario: Replacement cannot be applied completely
- **WHEN** any required native setter or decision validation fails before the replacement is committed
- **THEN** the adapter returns the original event with no partial mutation visible

### Requirement: Validate canonical integer mutation on macOS 14
Before Issue #42 is accepted, hosted CI SHALL run a public-API behavior check on macOS 14 using `.line` events created with `CGEventCreateScrollWheelEvent`. After mutation through only the canonical integer Delta setters, the established native adapter/AppKit seam SHALL expose the intended reversed LineBased behavior. FixedPt and PointDelta MAY be recorded as diagnostics but their exact values MUST NOT be asserted.

#### Scenario: macOS 14 compatibility check passes
- **WHEN** a synthetic `.line` event is reversed through only DeltaAxis1/2 integer setters on macOS 14
- **THEN** the public AppKit seam exposes the intended reversed LineBased behavior without project-owned FixedPt or PointDelta conversion

#### Scenario: macOS 14 compatibility check reaches a STOP condition
- **WHEN** integer setters alone cannot produce the intended public LineBased reversal without project-owned FixedPt or PointDelta conversion, fractional semantics require ABI widening, or another recorded architecture STOP condition occurs
- **THEN** implementation stops and returns to Issue planning without widening the ABI or changing domain semantics inside this change

### Requirement: Prove live reliability and latency on the reference Mac
Issue #42 acceptance SHALL include deterministic public-seam tests, a live `just smoke` run on the reference Mac, and `just benchmark` across 100,000 events. The benchmark SHALL show callback p99 no greater than 500 microseconds, p99.9 no greater than 1 millisecond, maximum no greater than 2 milliseconds, and the live smoke SHALL observe zero `tapDisabledByTimeout` events.

#### Scenario: Reference-Mac gates pass
- **WHEN** the canonical smoke and benchmark commands run on the reference Mac
- **THEN** LineBased direction replacement and PixelBased preservation are observed, no timeout disable occurs, and all stated latency thresholds pass

#### Scenario: Reference-Mac evidence is unavailable
- **WHEN** the canonical live smoke or benchmark has not run on the reference Mac
- **THEN** strict latency and live reliability acceptance remain `NOT_PROVEN`
