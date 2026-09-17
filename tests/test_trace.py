import json, os, pathlib, subprocess, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/trace.py"

class TraceTests(unittest.TestCase):
    def trace(self, root, *args): return subprocess.run(["python3", str(SCRIPT), *args], text=True, capture_output=True, env={**os.environ, "MMF_TRACE_DIR": str(root)})
    def bundle(self, root):
        path = pathlib.Path(root) / "run-1"; path.mkdir()
        (path / "manifest.json").write_text(json.dumps({"schema_version": 1, "run_id": "run-1", "started_monotonic_ns": 1, "clean_shutdown": True, "drop_count": 2}))
        return path
    def test_export_copies_valid_bundle_and_ignores_truncated_final_line(self):
        with tempfile.TemporaryDirectory() as root:
            bundle = self.bundle(root)
            record = {"schema_version": 1, "run_id": "run-1", "sequence": 1, "kind": "input", "monotonic_ns": 2, "granularity": "line_based", "decision": "replace", "native_outcome": "applied", "reason_code": "replace"}
            (bundle / "trace-10.jsonl").write_text(json.dumps(record) + "\n{\"truncated\"")
            target = pathlib.Path(root) / "copy"; result = self.trace(root, "export", "run-1", str(target))
            self.assertEqual(result.returncode, 0, result.stderr); self.assertEqual(json.loads((target / "manifest.json").read_text())["drop_count"], 2)
            self.assertEqual((target / "trace-0.jsonl").read_text(), json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    def test_rejects_sensitive_field(self):
        with tempfile.TemporaryDirectory() as root:
            bundle = self.bundle(root)
            (bundle / "trace-0.jsonl").write_text(json.dumps({"schema_version": 1, "run_id": "run-1", "kind": "input", "coordinates": [1,2]}) + "\n")
            result = self.trace(root, "export", "run-1")
            self.assertEqual(result.returncode, 2); self.assertIn("allowlist", result.stderr)

    def test_rejects_wrong_scalar_type(self):
        with tempfile.TemporaryDirectory() as root:
            bundle = self.bundle(root)
            record = {"schema_version": 1, "run_id": "run-1", "sequence": "1", "kind": "input", "monotonic_ns": 2, "granularity": "line_based", "decision": "replace", "native_outcome": "applied", "reason_code": "replace"}
            (bundle / "trace-0.jsonl").write_text(json.dumps(record) + "\n")
            result = self.trace(root, "export", "run-1")
            self.assertEqual(result.returncode, 2); self.assertIn("allowlist", result.stderr)
if __name__ == "__main__": unittest.main()
