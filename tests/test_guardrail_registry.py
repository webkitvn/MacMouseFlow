#!/usr/bin/env python3

import copy
import pathlib
import unittest

from scripts import guardrail_registry


ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs/guardrails/registry.yaml"
README = ROOT / "docs/guardrails/README.md"
AGENTS = ROOT / "AGENTS.md"

FROZEN = {
    "DG-DOM-001": ("domain_semantic_integrity", "hard_prohibition", "domain_context", "pointer_input_source_semantics", ("domain_semantics", "source_inference", "device_classification"), ("D2", "D4", "D5"), "forbidden"),
    "DG-ARCH-001": ("architecture_boundary_integrity", "hard_prohibition", "architecture_boundary", "native_rust_hot_path_abi", ("architecture_boundary", "new_abstraction", "process_topology", "ffi_abi", "platform_ownership"), ("D1", "D4", "D5"), "forbidden"),
    "DG-RT-001": ("real_time_reliability_safety", "hard_prohibition", "architecture_boundary", "input_callback_and_diagnostics_producer", ("hot_path", "callback", "logging", "locking", "allocation", "io", "diagnostics"), ("D1", "D3", "D4", "D5"), "forbidden"),
    "DG-REL-001": ("real_time_reliability_safety", "hard_prohibition", "architecture_boundary", "native_rust_failure_path", ("bridge_failure", "engine_failure", "error_mapping", "input_decision", "live_input_path"), ("D2", "D3", "D4"), "forbidden"),
    "DG-VER-001": ("verification_test_evidence_integrity", "conditional_prohibition", "workflow_surface", "production_tests_and_test_supporting_abstractions", ("tests", "mock_fake", "new_test_seam", "dependency_injection", "new_interface_abstraction"), ("D4", "D5"), "forbidden"),
    "DG-VER-002": ("verification_test_evidence_integrity", "evidence_required_invariant", "workflow_surface", "hot_path_latency_acceptance_and_release_evidence", ("performance_claim", "latency_budget", "benchmark", "release_evidence", "hot_path"), ("D3", "D5"), "decision_backed_bounded"),
    "DG-SOT-001": ("agent_source_of_truth_planning_integrity", "hard_prohibition", "workflow_surface", "agent_cold_start_planning_state_and_verification_routing", ("cold_start", "planning_mutation", "tracker_relationship", "agents_md", "verification_wiring", "canonical_source_change"), ("D1", "D4", "D5"), "forbidden"),
    "DG-PROV-001": ("external_reference_provenance_integrity", "hard_prohibition", "repo_wide", "repo_x_source_inspection_and_influenced_artifacts", ("external_reference", "repo_x", "source_inspection", "implementation_influenced_by_reference", "public_artifact_provenance"), ("D4", "D5"), "forbidden"),
    "DG-PROV-002": ("external_reference_provenance_integrity", "evidence_required_invariant", "workflow_surface", "research_design_implementation_provenance", ("external_reference", "repo_x_observation", "reference_pattern", "best_practice_claim", "reference_influenced_design"), ("D4", "D5"), "forbidden"),
}


class GuardrailRegistryTests(unittest.TestCase):
    def registry_text(self): return REGISTRY.read_text()

    def data(self, text=None): return guardrail_registry.parse_yaml(text or self.registry_text())

    def assert_invalid_fixture(self, old, new):
        with self.assertRaises(ValueError):
            guardrail_registry.validate(self.data(self.registry_text().replace(old, new, 1)), ROOT)

    def test_initial_ids_are_required_but_successors_and_tombstones_are_allowed(self):
        data = self.data()
        original = data["guardrails"][0]
        original["status"] = "superseded"
        original["lifecycle"]["last_transition"]["to"] = "superseded"
        original["lifecycle"]["superseded_by"] = "DG-DOM-010"
        successor = copy.deepcopy(original)
        successor["id"] = "DG-DOM-010"
        successor["status"] = "active"
        successor["lifecycle"]["last_transition"]["to"] = "active"
        successor["lifecycle"]["superseded_by"] = None
        data["guardrails"].append(successor)
        guardrail_registry.validate(data, ROOT)
        data["guardrails"] = data["guardrails"][1:]
        with self.assertRaises(ValueError):
            guardrail_registry.validate(data, ROOT)

    def test_canonical_registry_has_exact_frozen_metadata(self):
        data = guardrail_registry.validate(self.data(), ROOT)
        actual = {
            record["id"]: (record["family"], record["semantic_form"], record["scope"]["kind"], record["scope"]["area"], tuple(record["triggers"]), tuple(record["detector"]["evidence_classes"]), record["waiver"]["policy"])
            for record in data["guardrails"]
        }
        self.assertEqual({identifier: actual[identifier] for identifier in FROZEN}, FROZEN)
        for record in data["guardrails"]:
            self.assertTrue(record["canonical_sources"])
            self.assertTrue(record["enforcement"]["allowed_actions"])
            self.assertTrue(record["enforcement"]["canonical_surfaces"])

    def test_invalid_enum_duplicate_id_and_missing_pointer_fail(self):
        self.assert_invalid_fixture("family: domain_semantic_integrity", "family: invented_family")
        self.assert_invalid_fixture("id: DG-ARCH-001", "id: DG-DOM-001")
        self.assert_invalid_fixture("ref: CONTEXT.md", "ref: docs/missing.md")

    def test_rejects_missing_nested_collections_and_unknown_fields(self):
        self.assert_invalid_fixture("      evidence_classes:\n        - D2", "      evidence: D2")
        self.assert_invalid_fixture("      allowed_actions:\n        - fail", "      actions:\n        - fail")
        self.assert_invalid_fixture("    status: active", "    status: active\n    unexpected: value")

    def test_rejects_malformed_urls_and_invalid_lifecycle(self):
        self.assert_invalid_fixture("https://github.com/webkitvn/MacMouseFlow/issues/61", "https://")
        self.assert_invalid_fixture("to: active", "to: retired")

    def test_rejects_duplicate_yaml_keys_and_ambiguous_yaml(self):
        self.assert_invalid_fixture("    title: Preserve Input Source Semantics", "    title: Preserve Input Source Semantics\n    title: duplicate")
        self.assert_invalid_fixture("schema_version: 1", "schema_version: &version 1")
        self.assert_invalid_fixture("schema_version: 1", "schema_version: 1 # comment")
        self.assert_invalid_fixture("schema_version: 1", "schema_version: [a, b]")
        self.assert_invalid_fixture("schema_version: 1", "schema_version: {a: b}")
        self.assert_invalid_fixture("schema_version: 1", "schema_version: true")
        self.assert_invalid_fixture("schema_version: 1", "schema_version: ~")
        self.assert_invalid_fixture("schema_version: 1", "schema_version: 1.0")
        self.assert_invalid_fixture("schema_version: 1", "schema_version: 1.")
        self.assert_invalid_fixture("schema_version: 1", "schema_version: -1.")
        self.assert_invalid_fixture("schema_version: 1", "schema_version: 0xFF")
        self.assert_invalid_fixture("schema_version: 1", "schema_version: -0xFF")
        self.assert_invalid_fixture("schema_version: 1", "schema_version: 0o77")
        self.assert_invalid_fixture("schema_version: 1", "schema_version: +0o77")
        self.assert_invalid_fixture("title: Preserve Input Source Semantics", 'title: "a\\nb"')
        self.assert_invalid_fixture("title: Preserve Input Source Semantics", "title: 'it''s'")
        self.assert_invalid_fixture("title: Preserve Input Source Semantics", 'title: "ordinary"')
        self.assert_invalid_fixture("      Scroll Granularity, timestamps, and undocumented correlation do not prove Source Class or physical Device Identity.", "      Scroll Granularity, timestamps, and undocumented correlation do not prove Source Class or physical Device Identity.\n\n      This blank folded line is unsupported.")
        self.assert_invalid_fixture("      Scroll Granularity, timestamps, and undocumented correlation do not prove Source Class or physical Device Identity.", "      Scroll Granularity, timestamps, and undocumented correlation do not prove Source Class or physical Device Identity.\n      # folded content is unsupported")
        self.assert_invalid_fixture("      Scroll Granularity, timestamps, and undocumented correlation do not prove Source Class or physical Device Identity.", "      first\n        second\n      third")

    def test_uniform_folded_blocks_parse_and_schema_version_is_integer(self):
        data = self.data()
        self.assertEqual(data["schema_version"], 1)
        data["schema_version"] = True
        with self.assertRaises(ValueError):
            guardrail_registry.validate(data, ROOT)
        data["schema_version"] = 1
        self.assertEqual(data["guardrails"][0]["invariant_summary"], "Scroll Granularity, timestamps, and undocumented correlation do not prove Source Class or physical Device Identity.")

    def test_hard_prohibition_cannot_use_bounded_waiver(self):
        self.assert_invalid_fixture("      policy: forbidden\n      records: []", "      policy: decision_backed_bounded\n      records: []")

    def test_superseded_guardrail_requires_another_known_id(self):
        data = self.data()
        record = data["guardrails"][0]
        record["status"] = "superseded"
        record["lifecycle"]["last_transition"]["to"] = "superseded"
        record["lifecycle"]["superseded_by"] = record["id"]
        with self.assertRaises(ValueError):
            guardrail_registry.validate(data, ROOT)
        record["lifecycle"]["superseded_by"] = "DG-UNKNOWN-999"
        with self.assertRaises(ValueError):
            guardrail_registry.validate(data, ROOT)
        record["lifecycle"]["superseded_by"] = "DG-ARCH-001"
        guardrail_registry.validate(data, ROOT)

    def test_textual_bounded_waiver_with_https_evidence_parses_and_validates(self):
        text = self.registry_text().replace(
            "      policy: decision_backed_bounded\n      records: []",
            """      policy: decision_backed_bounded
      records:
        - id: bounded-example
          scope: exact scope
          decision: https://github.com/webkitvn/MacMouseFlow/issues/61
          rationale: test fixture
          evidence:
            - https://github.com/webkitvn/MacMouseFlow/issues/61
          expires:
            kind: condition
            value: condition-pointer
          remediation: remove waiver""",
        )
        guardrail_registry.validate(self.data(text), ROOT)

    def test_textual_waiver_evidence_rejects_malformed_url(self):
        text = self.registry_text().replace(
            "      policy: decision_backed_bounded\n      records: []",
            """      policy: decision_backed_bounded
      records:
        - id: bounded-example
          scope: exact scope
          decision: https://github.com/webkitvn/MacMouseFlow/issues/61
          rationale: test fixture
          evidence:
            - https://
          expires:
            kind: condition
            value: condition-pointer
          remediation: remove waiver""",
        )
        with self.assertRaises(ValueError):
            guardrail_registry.validate(self.data(text), ROOT)

    def test_generated_readme_drift_uses_checker_logic_without_mutation(self):
        data = guardrail_registry.validate(self.data(), ROOT)
        expected = guardrail_registry.render(data)
        check = README.read_text()
        guardrail_registry.check_readme(check, expected)
        with self.assertRaises(ValueError):
            guardrail_registry.check_readme(check + "drift\n", expected)

    def test_cli_has_no_alternate_registry_path(self):
        with self.assertRaises(SystemExit):
            guardrail_registry.main(["--registry", "fixture.yaml"])

    def test_cold_start_routes_agents_to_active_scoped_canonical_source(self):
        data = guardrail_registry.validate(self.data(), ROOT)
        self.assertIn("docs/guardrails/registry.yaml", AGENTS.read_text())
        matches = [
            item for item in data["guardrails"]
            if item["status"] == "active"
            and item["scope"]["kind"] == "architecture_boundary"
            and item["scope"]["area"] == "input_callback_and_diagnostics_producer"
            and "hot_path" in item["triggers"]
        ]
        self.assertEqual(len(matches), 1)
        sources = [source["ref"] for source in matches[0]["canonical_sources"]]
        self.assertIn("docs/adr/0001-native-adapter-rust-engine-boundary.md", sources)
        self.assertTrue((ROOT / "docs/adr/0001-native-adapter-rust-engine-boundary.md").is_file())


if __name__ == "__main__": unittest.main()
