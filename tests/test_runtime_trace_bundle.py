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
            "MMF_BENCHMARK_EVENTS": "64",
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
            stale = on_root / "stale"
            stale.mkdir(parents=True)
            (stale / "manifest.json").write_text(json.dumps({"schema_version": 1, "run_id": "stale", "started_monotonic_ns": 0, "clean_shutdown": True, "drop_count": 0, "writer_failed": False}))
            with (stale / "trace-0.jsonl").open("wb") as trace:
                trace.truncate(64 * 1024 * 1024 - 3_000)
            unrelated = on_root / "keep"
            unrelated.mkdir()
            (unrelated / "manifest.json").write_text(json.dumps({"schema_version": True, "run_id": "keep", "started_monotonic_ns": False, "clean_shutdown": 1, "drop_count": True, "writer_failed": 0}))
            on = self.benchmark(on_root, "1")
            self.assertEqual(on.returncode, 0, on.stderr)
            manifests = [path for path in on_root.glob("*/manifest.json") if path.parent != unrelated]
            self.assertEqual(len(manifests), 1)
            self.assertFalse(stale.exists())
            self.assertTrue(unrelated.exists())
            manifest = json.loads(manifests[0].read_text())
            self.assertGreaterEqual(manifest["started_monotonic_ns"], 0)
            self.assertRegex(manifest["run_start_utc"], r".+Z$")
            self.assertTrue(manifest["clean_shutdown"])
            self.assertFalse(manifest["writer_failed"])
            records = [json.loads(line) for path in manifests[0].parent.glob("trace-*.jsonl") for line in path.read_text().splitlines()]
            self.assertIn("run.start", [record["name"] for record in records])
            self.assertIn("run.stop", [record["name"] for record in records])
            self.assertIn("input.pipeline", [record["name"] for record in records])
            self.assertEqual(next(record for record in records if record["name"] == "run.start")["t_ns"], 0)
            self.assertTrue(all(record["t_ns"] >= 0 for record in records if "t_ns" in record))
            self.assertEqual(next(record for record in records if record["name"] == "input.pipeline")["level"], "trace")
            self.assertEqual(next(record for record in records if record["name"] == "input.pipeline")["component"], "native.input")
            self.assertTrue(all(record["seq"] > 0 and record["t_ns"] >= 0 for record in records))


if __name__ == "__main__":
    unittest.main()
