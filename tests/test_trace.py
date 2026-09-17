import json, os, pathlib, subprocess, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/trace.py"
class TraceTests(unittest.TestCase):
 def trace(self,root,*args):return subprocess.run(["python3",str(SCRIPT),*args],text=True,capture_output=True,env={**os.environ,"MMF_TRACE_DIR":str(root)})
 def bundle(self,root):
  p=pathlib.Path(root)/"run-1";p.mkdir();(p/"manifest.json").write_text(json.dumps({"schema_version":1,"run_id":"run-1","started_monotonic_ns":1,"clean_shutdown":True,"drop_count":2,"writer_failed":False}));return p
 def record(self):return {"schema_version":1,"run_id":"run-1","seq":1,"t_ns":2,"level":"debug","component":"input","name":"input.pipeline","input_seq":1,"horizontal_lines":3,"vertical_lines":-2,"granularity":"line_based","decision":"replace","native_outcome":"applied","reason_code":"replace","config_revision":None,"extraction_ns":1,"rust_eval_ns":1,"native_apply_ns":1,"total_ns":3}
 def test_export_sanitizes_truncated_line(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);r=self.record();(b/"trace-10.jsonl").write_text(json.dumps(r)+"\n{\"truncated\"");target=pathlib.Path(root)/"copy";x=self.trace(root,"export","run-1",str(target))
   self.assertEqual(x.returncode,0,x.stderr);self.assertEqual((target/"trace-0.jsonl").read_text(),json.dumps(r,sort_keys=True,separators=(",",":"))+"\n")
 def test_rejects_wrong_scalar_type(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);r=self.record();r["seq"]="1";(b/"trace-0.jsonl").write_text(json.dumps(r)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"typed"));self.assertEqual(x.returncode,2);self.assertIn("allowlist",x.stderr)
 def test_accepts_lifecycle_record(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);r={"schema_version":1,"run_id":"run-1","seq":1,"t_ns":2,"level":"warning","component":"runtime","name":"run.stop"};(b/"trace-0.jsonl").write_text(json.dumps(r)+"\n");d=pathlib.Path(root)/"copy";x=self.trace(root,"export","run-1",str(d));self.assertEqual(x.returncode,0,x.stderr)
 def test_rejects_existing_export_destination(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);(b/"trace-0.jsonl").write_text(json.dumps(self.record())+"\n");d=pathlib.Path(root)/"copy";d.mkdir();x=self.trace(root,"export","run-1",str(d));self.assertEqual(x.returncode,2);self.assertIn("already exists",x.stderr)
if __name__=="__main__":unittest.main()
