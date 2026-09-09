## MODIFIED Requirements

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

## ADDED Requirements

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
