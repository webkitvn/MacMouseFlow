<!-- GENERATED FROM registry.yaml; DO NOT EDIT. -->

# Design Guardrails

Read `registry.yaml` for the machine-readable canonical registry. Canonical sources own each guardrail's meaning.

## DG-DOM-001 — Preserve Input Source Semantics

- **Status:** active
- **Scope:** domain_context / pointer_input_source_semantics
- **Triggers:** domain_semantics, source_inference, device_classification
- **Required next action:** Preserve Unknown or semantic uncertainty, or obtain a canonical decision before implementing identity capability.
- **Canonical sources:**
  - `context`: CONTEXT.md
  - `adr`: docs/adr/0001-native-adapter-rust-engine-boundary.md

## DG-ARCH-001 — Preserve Native/Rust Architecture Boundary

- **Status:** active
- **Scope:** architecture_boundary / native_rust_hot_path_abi
- **Triggers:** architecture_boundary, new_abstraction, process_topology, ffi_abi, platform_ownership
- **Required next action:** Revert to the current boundary or open a superseding decision and ADR before continuing.
- **Canonical sources:**
  - `adr`: docs/adr/0001-native-adapter-rust-engine-boundary.md
  - `repository_contract`: AGENTS.md

## DG-RT-001 — Keep the Input Callback Bounded and Non-Blocking

- **Status:** active
- **Scope:** architecture_boundary / input_callback_and_diagnostics_producer
- **Triggers:** hot_path, callback, logging, locking, allocation, io, diagnostics
- **Required next action:** Move work outside the callback or use a bounded non-blocking path; supersede the decision to change the invariant.
- **Canonical sources:**
  - `adr`: docs/adr/0001-native-adapter-rust-engine-boundary.md
  - `adr`: docs/adr/0003-bounded-structured-observability-pipeline.md
  - `repository_contract`: AGENTS.md

## DG-REL-001 — Preserve Original Input on Bridge/Engine Failure

- **Status:** active
- **Scope:** architecture_boundary / native_rust_failure_path
- **Triggers:** bridge_failure, engine_failure, error_mapping, input_decision, live_input_path
- **Required next action:** Restore fail-open behavior and demonstrate it at an established public seam.
- **Canonical sources:**
  - `adr`: docs/adr/0001-native-adapter-rust-engine-boundary.md
  - `repository_contract`: AGENTS.md

## DG-VER-001 — Seam-Gated TDD

- **Status:** active
- **Scope:** workflow_surface / production_tests_and_test_supporting_abstractions
- **Triggers:** tests, mock_fake, new_test_seam, dependency_injection, new_interface_abstraction
- **Required next action:** Find established-seam evidence or stop production TDD for research, prototype, or a canonical decision.
- **Canonical sources:**
  - `issue_resolution`: https://github.com/webkitvn/MacMouseFlow/issues/56
  - `adr`: docs/adr/0002-hot-path-test-seams-and-latency-budget.md
  - `repository_contract`: AGENTS.md

## DG-VER-002 — Require Correct Latency Evidence

- **Status:** active
- **Scope:** workflow_surface / hot_path_latency_acceptance_and_release_evidence
- **Triggers:** performance_claim, latency_budget, benchmark, release_evidence, hot_path
- **Required next action:** Run the relevant canonical benchmark or smoke command in the required environment, or open a decision to change the contract.
- **Canonical sources:**
  - `adr`: docs/adr/0002-hot-path-test-seams-and-latency-budget.md
  - `issue_resolution`: https://github.com/webkitvn/MacMouseFlow/issues/58

## DG-SOT-001 — Preserve Canonical Project Truth Routing

- **Status:** active
- **Scope:** workflow_surface / agent_cold_start_planning_state_and_verification_routing
- **Triggers:** cold_start, planning_mutation, tracker_relationship, agents_md, verification_wiring, canonical_source_change
- **Required next action:** Route the information to its canonical owner, remove competing authority, and reconcile drift before acceptance.
- **Canonical sources:**
  - `repository_contract`: AGENTS.md
  - `issue_resolution`: https://github.com/webkitvn/MacMouseFlow/issues/57
  - `issue_resolution`: https://github.com/webkitvn/MacMouseFlow/issues/60
  - `issue_resolution`: https://github.com/webkitvn/MacMouseFlow/issues/58

## DG-PROV-001 — Prohibit Source-Derived Expression from Repo X

- **Status:** active
- **Scope:** repo_wide / repo_x_source_inspection_and_influenced_artifacts
- **Triggers:** external_reference, repo_x, source_inspection, implementation_influenced_by_reference, public_artifact_provenance
- **Required next action:** Remove and independently derive the expression, or open an explicit reuse and provenance decision.
- **Canonical sources:**
  - `issue_resolution`: https://github.com/webkitvn/MacMouseFlow/issues/21
  - `issue_resolution`: https://github.com/webkitvn/MacMouseFlow/issues/60
  - `repository_contract`: AGENTS.md

## DG-PROV-002 — Require Independent Project Rationale for Repo X Influence

- **Status:** active
- **Scope:** workflow_surface / research_design_implementation_provenance
- **Triggers:** external_reference, repo_x_observation, reference_pattern, best_practice_claim, reference_influenced_design
- **Required next action:** Record independent project rationale and evidence, or keep the observation as a candidate rather than a decision.
- **Canonical sources:**
  - `issue_resolution`: https://github.com/webkitvn/MacMouseFlow/issues/21
  - `issue_resolution`: https://github.com/webkitvn/MacMouseFlow/issues/60
