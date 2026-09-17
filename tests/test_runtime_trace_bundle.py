import json
import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class RuntimeTraceBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["cargo", "build", "-p", "pointer-input-ffi", "--locked"], cwd=ROOT, check=True)

    def benchmark(self, trace_dir, trace):
        environment = {
            **os.environ,
            "MMF_FFI_PROFILE": "debug",
            "MMF_BENCHMARK_SYNTHETIC": "1",
            "MMF_TRACE_DIR": str(trace_dir),
            "MMF_TRACE": trace,
        }
        return subprocess.run(
            ["swift", "run", "--package-path", "macos", "benchmark"],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_runtime_benchmark_trace_off_and_on_bundle_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            off = self.benchmark(root / "off", "0")
            self.assertEqual(off.returncode, 0, off.stderr)
            self.assertEqual(list((root / "off").glob("*/manifest.json")), [])

            on_root = root / "on"
            on = self.benchmark(on_root, "1")
            self.assertEqual(on.returncode, 0, on.stderr)
            manifests = list(on_root.glob("*/manifest.json"))
            self.assertEqual(len(manifests), 1)
            manifest = json.loads(manifests[0].read_text())
            self.assertTrue(manifest["clean_shutdown"])
            self.assertFalse(manifest["writer_failed"])
            records = [json.loads(line) for path in manifests[0].parent.glob("trace-*.jsonl") for line in path.read_text().splitlines()]
            self.assertIn("run.start", [record["name"] for record in records])
            self.assertIn("run.stop", [record["name"] for record in records])
            self.assertIn("input.pipeline", [record["name"] for record in records])


if __name__ == "__main__":
    unittest.main()
