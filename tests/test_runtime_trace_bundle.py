import json
import os
import pathlib
import subprocess
import tempfile
import shutil
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

    def test_configuration_activation_input_and_backoff_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            library = root / "platform.dylib"
            subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-dynamiclib", str(ROOT / "tests/fixtures/configuration_trace_platform.c"), "-framework", "ApplicationServices", "-o", str(library)], check=True)
            subprocess.run(["swift", "build", "--build-tests", "--package-path", "macos"], cwd=ROOT, env={**os.environ, "MMF_FFI_PROFILE": "debug"}, check=True, capture_output=True)
            binary_path = subprocess.check_output(["swift", "build", "--show-bin-path", "--package-path", "macos"], cwd=ROOT, text=True).strip()
            binary = pathlib.Path(binary_path) / "MacMouseFlowPackageTests.xctest/Contents/MacOS/MacMouseFlowPackageTests"
            for failure in [False, True]:
                fixture = root / ("backoff" if failure else "active")
                fixture.mkdir()
                env = {**os.environ, "DYLD_INSERT_LIBRARIES": str(library), "MMF_TEST_CONFIGURATION_TRACE_ROOT": str(fixture), "MMF_TEST_NATIVE_OUTPUT": str(fixture / "native.txt"), "MMF_TRACE": "0"}
                if failure:
                    env["MMF_TEST_TAP_FAILURE"] = "1"
                result = subprocess.run([str(pathlib.Path(subprocess.check_output(["xcode-select", "-p"], text=True).strip()) / "usr/bin/xctest"), "-XCTest", "PlatformTests.InputRuntimeTests/testProductionConfigurationActivationAndInputBundle", str(binary.parents[2])], env=env, cwd=ROOT, text=True, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("Executed 1 test", result.stdout + result.stderr)
                manifests = list((fixture / "traces").glob("*/manifest.json"))
                self.assertEqual(len(manifests), 1)
                manifest = json.loads(manifests[0].read_text())
                self.assertTrue(manifest["clean_shutdown"])
                self.assertEqual(manifest["drop_count"], 0)
                run = manifests[0].parent
                export = fixture / "export"
                result = subprocess.run(["python3", str(ROOT / "scripts/trace.py"), "export", run.name, str(export)], env={**os.environ, "MMF_TRACE_DIR": str(fixture / "traces")}, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                evidence = os.environ.get("MMF_TEST_CONFIGURATION_TRACE_EVIDENCE")
                if evidence:
                    destination = pathlib.Path(evidence) / fixture.name
                    shutil.copytree(fixture, destination)
                records = sorted([json.loads(line) for path in export.glob("trace-*.jsonl") for line in path.read_text().splitlines()], key=lambda record: record["seq"])
                persisted = next(r for r in records if r.get("result_code") == "persisted")
                self.assertEqual((persisted["old_config_revision"], persisted["new_config_revision"], persisted["line_amount_percent"]), (0, 1, 25))
                activation = next(r for r in records if r["name"] == "config.activation" and r["operation_id"] == persisted["operation_id"])
                self.assertEqual(activation["result_code"], "unavailable" if failure else "active")
                if failure:
                    self.assertIsNone(activation["new_config_revision"])
                    self.assertFalse(any(r["name"] == "input.pipeline" for r in records))
                    self.assertEqual((fixture / "native.txt").read_text(), "tap_creation_failed\n")
                    continue
                loaded = next(r for r in records if r["name"] == "config.load")
                self.assertTrue(any(r["name"] == "config.activation" and r["operation_id"] == loaded["operation_id"] and r["new_config_revision"] == 0 for r in records))
                inputs = [r for r in records if r["name"] == "input.pipeline"]
                self.assertEqual({r["config_revision"] for r in inputs}, {0, 1})
                self.assertTrue(all(r["horizontal_lines"] == 100 and r["vertical_lines"] == 100 and r["native_outcome"] == "applied" for r in inputs))
                native = [tuple(map(int, line.split())) for line in (fixture / "native.txt").read_text().splitlines()]
                self.assertEqual(len(native), len(inputs))
                self.assertEqual(native, [(-13700, -13700) if r["config_revision"] == 0 else (-2500, -2500) for r in inputs])
                failures = [r for r in records if r.get("result_code") in {"validation_rejected", "write_failed"}]
                self.assertEqual({r["result_code"] for r in failures}, {"validation_rejected", "write_failed"})
                for rejected in failures:
                    self.assertIsNone(rejected["new_config_revision"])
                    self.assertTrue(any(r["name"] == "config.rollback" and r["operation_id"] == rejected["operation_id"] and r["new_config_revision"] == 1 for r in records))
                self.assertEqual(inputs[-1]["config_revision"], 1)

    def test_runtime_benchmark_trace_off_and_on_bundle_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            off = self.benchmark(root / "off", "0")
            self.assertEqual(off.returncode, 0, off.stderr)
            self.assertEqual(list((root / "off").glob("*/manifest.json")), [])

            on_root = root / "on"
            stale = on_root / "stale"
            stale.mkdir(parents=True)
            (stale / "manifest.json").write_text(json.dumps({"schema_version": 1, "run_id": "stale", "started_monotonic_ns": 0, "clean_shutdown": True, "drop_count": 0}))
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
