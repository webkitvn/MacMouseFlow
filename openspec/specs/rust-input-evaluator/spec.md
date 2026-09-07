# rust-input-evaluator Specification

## Purpose

Defines deterministic platform-neutral evaluation of normalized scroll input into a fail-open Input Decision without inferring physical device identity.

## Requirements

### Requirement: Evaluate normalized input without source inference
The evaluator SHALL accept a normalized `Input Event` with an explicit `Input Source` and `Source Class`, including `Unknown`. It MUST NOT infer Source Class or Device Identity from Scroll Granularity, timestamps, absent identity, or undocumented correlation. Evaluation behavior for this change SHALL be source-independent.

#### Scenario: Unknown source is accepted
- **WHEN** a valid LineBased Scroll Event has Source Class `Unknown`
- **THEN** the evaluator returns the same decision it would return for the same event and configuration with any other accepted Source Class

#### Scenario: Granularity does not classify source
- **WHEN** the evaluator receives a PixelBased Scroll Event with Source Class `Unknown`
- **THEN** it preserves the event without assigning a source class or device identity

### Requirement: Preserve or reverse LineBased scroll deterministically
The evaluator SHALL produce Preserve for LineBased scroll when configuration direction is system/default or both line deltas are zero. When configuration direction is reverse and at least one LineBased delta is nonzero, it SHALL produce Replace with each axis checked-negated as signed 64-bit line deltas; a zero axis remains zero. If either checked negation cannot be represented, it SHALL produce Preserve with an explicit non-success status.

#### Scenario: System direction preserves line deltas
- **WHEN** a LineBased Scroll Event has any signed horizontal and vertical line deltas and the direction is system/default
- **THEN** the evaluator returns Preserve

#### Scenario: Reverse direction negates a one-axis scroll
- **WHEN** a LineBased Scroll Event has one representable nonzero line delta, a zero value on the other axis, and the direction is reverse
- **THEN** the evaluator returns Replace with the nonzero axis negated and the zero axis unchanged

#### Scenario: Both zero axes preserve
- **WHEN** a LineBased Scroll Event has zero horizontal and vertical line deltas and the direction is reverse
- **THEN** the evaluator returns Preserve

#### Scenario: Overflow preserves with failure status
- **WHEN** a LineBased Scroll Event contains the minimum signed 64-bit value on an axis and the direction is reverse
- **THEN** the evaluator returns Preserve with a non-success status rather than producing a wrapped replacement

### Requirement: Preserve PixelBased scroll
The evaluator SHALL produce Preserve for every valid PixelBased Scroll Event regardless of direction configuration or source classification.

#### Scenario: Reverse configuration preserves pixel input
- **WHEN** a PixelBased Scroll Event is evaluated with reverse direction configured
- **THEN** the evaluator returns Preserve with the original pixel input unaffected

### Requirement: Represent decision independently from evaluation status
The public evaluation seam SHALL distinguish an evaluation status from an `Input Decision`. A rejected input or evaluation fault MUST have an explicit non-success status and a Preserve decision; a successful evaluation MUST return its deterministic Preserve or Replace decision.

#### Scenario: Invalid event fails open
- **WHEN** an evaluation request contains an invalid normalized event value
- **THEN** the seam reports a non-success status and initializes or returns Preserve

#### Scenario: Valid preserved event succeeds
- **WHEN** a valid event requires no transformation
- **THEN** the seam reports success and returns Preserve
