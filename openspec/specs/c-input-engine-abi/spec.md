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
Before evaluating a request, the ABI SHALL initialize a non-null output to Preserve. Every exported operation SHALL catch any Rust panic so no panic crosses the C boundary. During the dynamic extent of input evaluation, the process panic hook SHALL perform no synchronous stderr output, backtrace generation, formatting, allocation, logging, or diagnostic enqueue. An evaluation panic or other evaluation failure SHALL return a non-success status while leaving the output as Preserve.

#### Scenario: Rejected event initializes Preserve
- **WHEN** a non-null output accompanies an invalid event request
- **THEN** the ABI returns invalid argument and the output contains Preserve

#### Scenario: Evaluation panic preserves input
- **WHEN** evaluation panics during an exported evaluation call
- **THEN** the call returns a non-success status, the caller observes Preserve, and the hook performs no callback-path output or diagnostics

#### Scenario: Non-input panic retains prior behavior
- **WHEN** a panic occurs outside the dynamic extent of input evaluation after the policy is installed
- **THEN** the previously installed process hook receives the panic

#### Scenario: Panic payload disposal is contained
- **WHEN** disposal of a caught evaluation panic payload panics
- **THEN** no primary or secondary panic crosses the ABI and the evaluation result remains non-success with Preserve

### Requirement: Provide opaque engine lifetime with owner-retained concurrent use
The ABI SHALL create an opaque engine allocation only through an initially null owner handle variable; a non-null owner variable MUST return invalid argument unchanged without allocating or overwriting its live handle. Its destruction operation SHALL receive a pointer to that owner variable, set it to null before releasing the allocation, and accept a null owner variable as an idempotent no-op. Copied non-owning handle values MAY call configuration update and evaluation concurrently while the owner guarantees the allocation remains live. Callers MUST NOT destroy concurrently, use after destruction, or use stale or fabricated handles; those are contract violations.

#### Scenario: Live owner cannot be replaced
- **WHEN** a caller creates an engine and then calls create again through the same live owner variable
- **THEN** the second call returns invalid argument, leaves the owner variable unchanged, and the original engine remains destroyable

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

### Requirement: Install a process-lifetime panic policy before engine delivery
The ABI SHALL install its process-wide panic policy once during successful engine creation before engine allocation or input delivery. Installation SHALL use one-time state: a create invoked from a panicking thread while uninstalled SHALL return Panic with a null owner before changing state, and a later normal create may install; one creator may otherwise install, every additional creator while installation is in progress SHALL promptly return Busy with a null owner without waiting. Busy is the only status the bounded integration helper automatically retries; a caller that received Busy may retry after the in-progress installer succeeds or fails. Installation panics or failures SHALL return Panic with a null owner and reset state to uninstalled, after which a caller may make a separate later creation. The ABI SHALL retain ownership of the installed policy for the process lifetime and MUST NOT ordinarily restore or replace it during engine destruction or mutate it per input event.

#### Scenario: Panicking creation before installation is rejected
- **WHEN** a prior panic hook invokes creation while policy state is uninstalled
- **THEN** creation returns Panic with a null owner before changing state, and a later normal creation may install the policy

#### Scenario: First successful creation installs policy
- **WHEN** creation receives a valid null owner variable and no policy is installed
- **THEN** the ABI installs the policy before allocating and returning the engine handle

#### Scenario: Policy installation failure fails startup safely
- **WHEN** installation panics or otherwise fails during creation
- **THEN** creation returns Panic, leaves the owner variable null, resets installation state to uninstalled, and native input delivery does not start; a caller may make a separate later creation

#### Scenario: Creation is Busy during installation
- **WHEN** any additional creation occurs while policy installation is in progress
- **THEN** it promptly returns Busy with a null owner without waiting; the bounded integration helper automatically retries only Busy, and its caller may retry after the installer succeeds or fails

#### Scenario: TLS is unavailable during a non-input panic
- **WHEN** the panic hook cannot access its thread-local evaluation marker
- **THEN** it delegates to the captured previous hook rather than panicking or suppressing the unrelated panic

#### Scenario: Engine destruction retains policy
- **WHEN** an engine is destroyed after successful policy installation
- **THEN** destruction releases the engine while the process panic policy remains installed

### Requirement: Require unwind-capable panic containment
The FFI crate SHALL compile with an unwind-capable panic strategy. It MUST reject an abort panic strategy at compile time because aborting cannot return the ABI's fail-open Panic status and Preserve decision. The existing private test-only panic injection MAY remain solely to exercise the established public ABI and MUST NOT become a production fault-control interface.

#### Scenario: Unsupported panic strategy is rejected
- **WHEN** the FFI crate is compiled with an abort panic strategy
- **THEN** compilation fails before an ABI artifact is produced

#### Scenario: Test injection remains private
- **WHEN** public ABI tests inject an evaluation panic through the existing test-only facility
- **THEN** the test observes the selected hook policy and Panic plus Preserve without exposing a production C symbol or fault-control API

### Requirement: Prove the C contract from a C caller
The repository SHALL compile, link, and run a C program against the published header and ABI library through the canonical `just test` command. The C contract test SHALL cover engine lifetime, fixed-layout validation, deterministic evaluation including one-axis reverse LineBased input, and fail-open status/decision separation.

#### Scenario: Canonical test runs native C contract
- **WHEN** `just test` runs on a supported development environment
- **THEN** it includes a successful compile, link, and execution of the C ABI contract program
