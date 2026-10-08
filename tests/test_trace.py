import json, os, pathlib, subprocess, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/trace.py"
class TraceTests(unittest.TestCase):
 def trace(self,root,*args):return subprocess.run(["python3",str(SCRIPT),*args],text=True,capture_output=True,env={**os.environ,"MMF_TRACE_DIR":str(root)})
 def bundle(self,root):
  p=pathlib.Path(root)/"run-1";p.mkdir();(p/"manifest.json").write_text(json.dumps({"schema_version":1,"run_id":"run-1","run_start_utc":"2026-01-01T00:00:00Z","started_monotonic_ns":1,"clean_shutdown":True,"drop_count":2,"writer_failed":False}));return p
 def record(self):return {"schema_version":1,"run_id":"run-1","seq":1,"t_ns":2,"level":"trace","component":"native.input","name":"input.pipeline","input_seq":1,"horizontal_lines":3,"vertical_lines":-2,"granularity":"line_based","decision":"replace","native_outcome":"applied","reason_code":"replace","config_revision":None,"extraction_ns":1,"rust_eval_ns":1,"native_apply_ns":1,"total_ns":3}
 def extended_record(self):
  return {**self.record(),"reason_code":"nonneutral_amount_transform","scroll_amount_percent":137,"line_direction":"preserve","decision_horizontal_hundredths":411,"decision_vertical_hundredths":-274}
 def test_configuration_allowlist_and_revision_join(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);operation="12345678-1234-4234-8234-123456789ABC"
   r={"schema_version":1,"run_id":"run-1","seq":1,"t_ns":2,"level":"info","component":"configuration","name":"config.persist","operation_id":operation,"old_config_revision":0,"new_config_revision":1,"line_amount_percent":137,"line_direction":"reverse","enabled":True,"result_code":"persisted"}
   active={**r,"seq":2,"name":"config.activation","result_code":"active"};event={**self.record(),"seq":3,"config_revision":1}
   (b/"trace-0.jsonl").write_text("".join(json.dumps(x)+"\n" for x in [r,active,event]));target=pathlib.Path(root)/"joined";x=self.trace(root,"export","run-1",str(target));self.assertEqual(x.returncode,0,x.stderr)
   for key,value in [("path","/private/config"),("operation_id","not-a-uuid"),("result_code","applied"),("enabled",1),("line_amount_percent",401),("new_config_revision",0),("old_config_revision",True),("line_direction","natural")]:
    (b/"trace-0.jsonl").write_text(json.dumps({**r,key:value})+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"invalid"));self.assertEqual(x.returncode,2,x.stderr)
   for name,result,new in [("config.persist","write_failed",1),("config.activation","unavailable",1),("config.rollback","retained",1)]:
    (b/"trace-0.jsonl").write_text(json.dumps({**r,"name":name,"result_code":result,"new_config_revision":new})+"\n");self.assertEqual(self.trace(root,"export","run-1",str(pathlib.Path(root)/"invalid")).returncode,2)
   for result,enabled in [("disabled",False),("unavailable",True)]:
    valid={**active,"result_code":result,"enabled":enabled,"new_config_revision":None};(b/"trace-0.jsonl").write_text(json.dumps(valid)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/result));self.assertEqual(x.returncode,0,x.stderr)
   invalid={**active,"result_code":"unavailable","enabled":False,"new_config_revision":None};(b/"trace-0.jsonl").write_text(json.dumps(invalid)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"disabled-unavailable"));self.assertEqual(x.returncode,2);self.assertIn("allowlist",x.stderr)
 def test_export_sanitizes_truncated_line(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);r=self.record();(b/"trace-10.jsonl").write_text(json.dumps(r)+"\n{\"truncated\"");target=pathlib.Path(root)/"copy";x=self.trace(root,"export","run-1",str(target))
   self.assertEqual(x.returncode,0,x.stderr);self.assertEqual((target/"trace-0.jsonl").read_text(),json.dumps(r,sort_keys=True,separators=(",",":"))+"\n")
 def test_rejects_wrong_scalar_type(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);r=self.record();r["seq"]="1";(b/"trace-0.jsonl").write_text(json.dumps(r)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"typed"));self.assertEqual(x.returncode,2);self.assertIn("allowlist",x.stderr)
 def test_rejects_duplicate_sequence_across_segments(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);r=self.record();(b/"trace-0.jsonl").write_text(json.dumps(r)+"\n");(b/"trace-1.jsonl").write_text(json.dumps(r)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"ordered"));self.assertEqual(x.returncode,2);self.assertIn("ordering",x.stderr)
 def test_rejects_backward_input_sequence(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);first=self.record();second=self.record();second["seq"]=2;second["input_seq"]=0;(b/"trace-0.jsonl").write_text(json.dumps(first)+"\n"+json.dumps(second)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"ordered"));self.assertEqual(x.returncode,2);self.assertIn("ordering",x.stderr)
 def test_accepts_engine_unavailable_as_preserve_reason(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);r=self.record();r["decision"]="preserve";r["reason_code"]="engine_unavailable";r["native_outcome"]="preserved";(b/"trace-0.jsonl").write_text(json.dumps(r)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"failure"));self.assertEqual(x.returncode,0,x.stderr)
 def test_exports_extended_records_and_rejects_partial_or_contradictory_fields(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);r=self.extended_record();(b/"trace-0.jsonl").write_text(json.dumps(r)+"\n");target=pathlib.Path(root)/"extended";x=self.trace(root,"export","run-1",str(target))
   self.assertEqual(x.returncode,0,x.stderr);self.assertEqual(json.loads((target/"trace-0.jsonl").read_text()),r)
   rejected={**r,"native_outcome":"preserved","reason_code":"native_replace_rejected"};(b/"trace-0.jsonl").write_text(json.dumps(rejected)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"rejected"));self.assertEqual(x.returncode,0,x.stderr)
   pixel={**r,"granularity":"pixel_based","decision":"preserve","native_outcome":"preserved","reason_code":"pixel_preserve","scroll_amount_percent":None,"decision_horizontal_hundredths":None,"decision_vertical_hundredths":None};(b/"trace-0.jsonl").write_text(json.dumps(pixel)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"pixel"));self.assertEqual(x.returncode,0,x.stderr)
   for invalid in [{k:v for k,v in r.items() if k!="horizontal_lines"},{k:v for k,v in r.items() if k!="line_direction"},{**r,"horizontal_lines":[]},{**r,"scroll_amount_percent":True},{**r,"scroll_amount_percent":401},{**r,"decision_horizontal_hundredths":None},{**r,"decision_vertical_hundredths":[]},{**rejected,"reason_code":"nonneutral_amount_transform"},{**pixel,"scroll_amount_percent":137},{**pixel,"decision_horizontal_hundredths":0},{**r,"private":"raw"},{**r,"decision":"preserve","native_outcome":"preserved","reason_code":"neutral_amount_preserve","decision_horizontal_hundredths":None,"decision_vertical_hundredths":None},{**r,"scroll_amount_percent":100,"line_direction":"preserve","reason_code":"reverse_neutral_transform"},{**r,"horizontal_lines":0,"vertical_lines":1,"decision":"preserve","native_outcome":"preserved","reason_code":"zero_input_preserve","decision_horizontal_hundredths":None,"decision_vertical_hundredths":None}]:
    (b/"trace-0.jsonl").write_text(json.dumps(invalid)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"invalid"));self.assertEqual(x.returncode,2);self.assertIn("allowlist",x.stderr)
 def test_rejects_suppress(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);r=self.record();r["decision"]="suppress";(b/"trace-0.jsonl").write_text(json.dumps(r)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"suppress"));self.assertEqual(x.returncode,2)
 def test_rejects_contradictory_decision_tuples(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);r=self.record();r["native_outcome"]="preserved";(b/"trace-0.jsonl").write_text(json.dumps(r)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"replace"));self.assertEqual(x.returncode,2)
   r=self.record();r["reason_code"]="engine_unavailable";(b/"trace-0.jsonl").write_text(json.dumps(r)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"failure"));self.assertEqual(x.returncode,2)
   r=self.record();r["decision"]="preserve";r["native_outcome"]="applied";r["reason_code"]="preserve";(b/"trace-0.jsonl").write_text(json.dumps(r)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"outcome"));self.assertEqual(x.returncode,2)
   r=self.record();r["decision"]="preserve";r["native_outcome"]="preserved";(b/"trace-0.jsonl").write_text(json.dumps(r)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"reason"));self.assertEqual(x.returncode,2)
   r=self.record();r["granularity"]="pixel_based";(b/"trace-0.jsonl").write_text(json.dumps(r)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"pixel"));self.assertEqual(x.returncode,2)
   r=self.record();r["decision"]="preserve";r["native_outcome"]="preserved";r["reason_code"]="not_line_based";(b/"trace-0.jsonl").write_text(json.dumps(r)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"line"));self.assertEqual(x.returncode,2)
 def test_rejects_malformed_run_start_utc(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);m=json.loads((b/"manifest.json").read_text());m["run_start_utc"]="Z";(b/"manifest.json").write_text(json.dumps(m));x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"invalid"));self.assertEqual(x.returncode,2);self.assertIn("allowlist",x.stderr)
 def test_exports_historic_v1_bundle(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);m=json.loads((b/"manifest.json").read_text());del m["run_start_utc"];(b/"manifest.json").write_text(json.dumps(m));r=self.record();r["level"]="debug";r["component"]="input";(b/"trace-0.jsonl").write_text(json.dumps(r)+"\n"+json.dumps({"schema_version":1,"run_id":"run-1","level":"warning","component":"trace","name":"trace.dropped","drop_count":1})+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"historic"));self.assertEqual(x.returncode,0,x.stderr)
 def test_exports_historic_engine_failure(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);m=json.loads((b/"manifest.json").read_text());del m["run_start_utc"];(b/"manifest.json").write_text(json.dumps(m));r=self.record();r["level"]="debug";r["component"]="input";r["decision"]="engine_unavailable";r["native_outcome"]="preserved";r["reason_code"]="engine_unavailable";(b/"trace-0.jsonl").write_text(json.dumps(r)+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"historic"));self.assertEqual(x.returncode,0,x.stderr)
 def test_rejects_historic_record_with_current_manifest(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);(b/"trace-0.jsonl").write_text(json.dumps({"schema_version":1,"run_id":"run-1","level":"warning","component":"trace","name":"trace.dropped","drop_count":1})+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"mixed"));self.assertEqual(x.returncode,2)
 def test_rejects_current_record_with_historic_manifest(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);m=json.loads((b/"manifest.json").read_text());del m["run_start_utc"];(b/"manifest.json").write_text(json.dumps(m));(b/"trace-0.jsonl").write_text(json.dumps(self.record())+"\n");x=self.trace(root,"export","run-1",str(pathlib.Path(root)/"mixed"));self.assertEqual(x.returncode,2)
 def test_accepts_lifecycle_record(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);r={"schema_version":1,"run_id":"run-1","seq":1,"t_ns":2,"level":"info","component":"lifecycle","name":"run.stop"};(b/"trace-0.jsonl").write_text(json.dumps(r)+"\n");d=pathlib.Path(root)/"copy";x=self.trace(root,"export","run-1",str(d));self.assertEqual(x.returncode,0,x.stderr)
 def test_unique_temp_does_not_remove_sibling(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);(b/"trace-0.jsonl").write_text(json.dumps(self.record())+"\n");d=pathlib.Path(root)/"copy";sibling=pathlib.Path(root)/"copy.tmp-existing";sibling.mkdir();(sibling/"keep").write_text("yes");x=self.trace(root,"export","run-1",str(d));self.assertEqual(x.returncode,0,x.stderr);self.assertTrue((sibling/"keep").exists())
 def test_exports_to_missing_nested_parent(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);(b/"trace-0.jsonl").write_text(json.dumps(self.record())+"\n");d=pathlib.Path(root)/"new"/"nested"/"copy";x=self.trace(root,"export","run-1",str(d));self.assertEqual(x.returncode,0,x.stderr);self.assertTrue((d/"manifest.json").exists())
 def test_rejects_existing_export_destination(self):
  with tempfile.TemporaryDirectory() as root:
   b=self.bundle(root);(b/"trace-0.jsonl").write_text(json.dumps(self.record())+"\n");d=pathlib.Path(root)/"copy";d.mkdir();x=self.trace(root,"export","run-1",str(d));self.assertEqual(x.returncode,2);self.assertIn("already exists",x.stderr)
if __name__=="__main__":unittest.main()
