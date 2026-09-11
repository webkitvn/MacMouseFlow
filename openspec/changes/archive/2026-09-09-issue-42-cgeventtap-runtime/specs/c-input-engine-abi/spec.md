## ADDED Requirements

### Requirement: Native adapter consumes the status and decision contract fail-open
A native input adapter calling the ABI SHALL construct an exact-layout event with explicit granularity, Source Class `Unknown`, and zero reserved fields. It SHALL treat every non-success status, Preserve decision, malformed decision, or unavailable engine as Preserve of the original native event. It MUST validate a successful Replace decision completely before mutating the native event and MUST NOT expose a production fault-control interface solely for adapter tests.

#### Scenario: Valid normalized event reaches the real ABI
- **WHEN** the native adapter submits an exact-layout LineBased event with Source Class `Unknown`
- **THEN** the ABI evaluates it with the current atomic configuration and returns status independently from Preserve or Replace

#### Scenario: Non-success status preserves native input
- **WHEN** the ABI returns InvalidArgument, EvaluationFailed, Panic, Busy, or any other non-success status during adapter processing
- **THEN** the native adapter returns the original native event without mutation

#### Scenario: Malformed replacement preserves native input
- **WHEN** an ABI result claims Replace but fails native-side decision validation
- **THEN** the native adapter returns the original native event without partial mutation
