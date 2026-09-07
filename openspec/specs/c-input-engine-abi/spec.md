# c-input-engine-abi Specification

## Purpose

Defines a stable narrow C boundary for the Rust input evaluator so native callers can validate, configure, evaluate, and release an opaque engine safely.

## Requirements

### Requirement: Publish a versioned fixed-layout C contract
The integration boundary SHALL publish manually maintained C declarations and versioned `_v1` symbols. Every cross-boundary value SHALL use a fixed-layout POD contract with primitive fixed-width fields, a version field, a size field, and reserved fields. A request is valid only when its version and size exactly match the published contract and all reserved fields are zero.

#### Scenario: Exact-layout request is accepted
- **WHEN** a caller supplies a request with the published `_v1` version, exact size, and zero reserved fields
- **THEN** the ABI accepts the layout subject to its semantic field validation

#### Scenario: Incompatible layout is rejected
- **WHEN** a caller supplies an unsupported version, a non-exact size, or a nonzero reserved field
- **THEN** the ABI returns invalid argument and does not silently reinterpret the request

### Requirement: Validate input and configuration at the ABI boundary
The ABI SHALL reject null required input pointers, null configuration pointers, malformed enum/tag values, and invalid fixed-layout values with an explicit non-success status. Validation failure MUST preserve the original input semantics and MUST NOT infer missing source information. A fabricated, stale, use-after-destroy, or concurrently destroyed opaque handle is a caller contract violation rather than an ABI value the implementation is required to validate safely.

#### Scenario: Null evaluation output is rejected
- **WHEN** an evaluation call receives a null output pointer
- **THEN** it returns invalid argument without dereferencing the output pointer

#### Scenario: Invalid configuration is rejected
- **WHEN** a caller submits a configuration with an unsupported value
- **THEN** the ABI returns invalid argument and leaves the engine's active configuration unchanged

### Requirement: Fail open on evaluation and export faults
Before evaluating a request, the ABI SHALL initialize a non-null output to Preserve. Every exported operation SHALL catch any Rust panic so no panic crosses the C boundary. An evaluation panic or other evaluation failure SHALL return a non-success status while leaving the output as Preserve.

#### Scenario: Rejected event initializes Preserve
- **WHEN** a non-null output accompanies an invalid event request
- **THEN** the ABI returns invalid argument and the output contains Preserve

#### Scenario: Evaluation panic preserves input
- **WHEN** evaluation panics during an exported evaluation call
- **THEN** the call returns a non-success status and the caller observes Preserve rather than suppression or a fabricated replacement

### Requirement: Provide opaque engine lifetime with owner-retained concurrent use
The ABI SHALL create an opaque engine allocation with one uniquely owned handle variable. Its destruction operation SHALL receive a pointer to that owner variable, set it to null before releasing the allocation, and accept a null owner variable as an idempotent no-op. Copied non-owning handle values MAY call configuration update and evaluation concurrently while the owner guarantees the allocation remains live. Callers MUST NOT destroy concurrently, use after destruction, or use stale or fabricated handles; those are contract violations.

#### Scenario: Repeat destruction through the same variable is safe
- **WHEN** a caller destroys an engine through a valid pointer-to-handle and then repeats destruction through that same variable
- **THEN** the first call nulls the variable and the repeat call is a no-op

#### Scenario: Non-owning handle use remains live-owner bounded
- **WHEN** a caller copies a handle value and the owner keeps the allocation live
- **THEN** the copied value may evaluate or update configuration concurrently but may not destroy the allocation

#### Scenario: Stale copied handle is prohibited
- **WHEN** a caller retains a copied handle after the owner destroys the allocation
- **THEN** the contract identifies a later use or destruction through that copied value as a caller violation rather than supported behavior

### Requirement: Apply configuration through an atomic evaluator snapshot
A successful configuration update SHALL replace the evaluator's active configuration atomically. Each evaluation SHALL observe one complete configuration value rather than a partially updated configuration.

#### Scenario: Valid update affects a later evaluation
- **WHEN** a caller successfully applies reverse direction configuration
- **THEN** a subsequent valid LineBased evaluation observes either the prior complete configuration or the reverse complete configuration, never a partial value

### Requirement: Prove the C contract from a C caller
The repository SHALL compile, link, and run a C program against the published header and ABI library through the canonical `just test` command. The C contract test SHALL cover engine lifetime, fixed-layout validation, deterministic evaluation including one-axis reverse LineBased input, and fail-open status/decision separation.

#### Scenario: Canonical test runs native C contract
- **WHEN** `just test` runs on a supported development environment
- **THEN** it includes a successful compile, link, and execution of the C ABI contract program
