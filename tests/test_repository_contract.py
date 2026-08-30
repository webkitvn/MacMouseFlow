#!/usr/bin/env python3

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    def test_scaffold_toolchain_and_command_surface_match_contract(self):
        required_paths = [
            "Cargo.toml",
            "Cargo.lock",
            "rust/engine/Cargo.toml",
            "rust/engine/src/lib.rs",
            "rust/ffi/Cargo.toml",
            "rust/ffi/src/lib.rs",
            "macos/App/README.md",
            "macos/Platform/README.md",
            "macos/Bridge/README.md",
            "tests/contract/README.md",
            "rust-toolchain.toml",
            ".xcode-version",
            ".githooks/pre-commit",
            ".githooks/pre-push",
            ".github/workflows/ci.yml",
            ".github/pull_request_template.md",
            ".github/ISSUE_TEMPLATE/bug_report.yml",
        ]
        missing = [path for path in required_paths if not (ROOT / path).exists()]
        self.assertEqual(missing, [], f"missing scaffold paths: {missing}")

        rust_toolchain = (ROOT / "rust-toolchain.toml").read_text()
        self.assertIn('channel = "1.98.0"', rust_toolchain)
        self.assertIn('"rustfmt"', rust_toolchain)
        self.assertIn('"clippy"', rust_toolchain)
        self.assertEqual((ROOT / ".xcode-version").read_text().strip(), "16.4")

        justfile = (ROOT / "Justfile").read_text()
        for recipe in [
            "fmt:",
            "build:",
            "check:",
            "test:",
            "ci:",
            "benchmark:",
            "smoke:",
            "hooks-install:",
            "trace-tail:",
            "trace-export",
            "frontier:",
            "next:",
        ]:
            self.assertIn(recipe, justfile, f"missing canonical recipe {recipe}")

    def test_hooks_and_ci_route_through_canonical_commands(self):
        self.assertEqual(
            (ROOT / ".githooks/pre-commit").read_text(),
            "#!/bin/sh\nexec just check\n",
        )
        self.assertEqual(
            (ROOT / ".githooks/pre-push").read_text(),
            "#!/bin/sh\nexec just test\n",
        )

        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("just ci", workflow)
        self.assertIn("ci-gate", workflow)
        self.assertIn("macos-15", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertNotIn("cargo test", workflow)
        self.assertNotIn("cargo clippy", workflow)
        self.assertNotIn("paths-ignore", workflow)

    def test_readme_routes_humans_and_agents_to_agents_rulebook(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("AGENTS.md", readme)
        self.assertNotIn("current milestone", readme.lower())
        self.assertNotIn("current frontier", readme.lower())


if __name__ == "__main__":
    unittest.main()
