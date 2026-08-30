#!/usr/bin/env python3

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    def test_scaffold_toolchain_and_command_surface_match_contract(self):
        required_paths = [
            "rust/engine/README.md",
            "rust/ffi/README.md",
            "macos/App/README.md",
            "macos/Platform/README.md",
            "macos/Bridge/README.md",
            "tests/contract/README.md",
            "rust-toolchain.toml",
            ".xcode-version",
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


if __name__ == "__main__":
    unittest.main()
