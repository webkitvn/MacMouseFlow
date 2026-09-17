#!/usr/bin/env python3
"""Validate, follow, and export local MacMouseFlow diagnostic bundles."""
from __future__ import annotations
import argparse, json, os, shutil, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("MMF_TRACE_DIR", Path.home() / "Library/Application Support/io.github.webkitvn.macmouseflow/Traces"))
def fail(m): print(f"TRACE_ERROR: {m}", file=sys.stderr); raise SystemExit(2)
def exact(v,t): return type(v) is t
def bundles(): return sorted((p for p in ROOT.glob("*") if (p / "manifest.json").is_file()), key=lambda p:p.stat().st_mtime)
def selected(r):
 p=[x for x in bundles() if r is None or x.name==r]
 if not p: fail("trace run not found")
 return p[-1]
def segments(b):
 try:return sorted(b.glob("trace-*.jsonl"),key=lambda p:int(p.stem[6:]))
 except ValueError:fail("invalid segment name")
def manifest(b):
 try:v=json.loads((b/"manifest.json").read_text())
 except (OSError,json.JSONDecodeError) as e:fail(f"invalid manifest: {e}")
 if not isinstance(v,dict) or set(v)!={"schema_version","run_id","started_monotonic_ns","clean_shutdown","drop_count","writer_failed"} or not(exact(v["schema_version"],int) and v["schema_version"]==1 and exact(v["run_id"],str) and v["run_id"]==b.name and exact(v["started_monotonic_ns"],int) and v["started_monotonic_ns"]>=0 and exact(v["clean_shutdown"],bool) and exact(v["writer_failed"],bool) and exact(v["drop_count"],int) and v["drop_count"]>=0):fail("manifest violates trace schema/privacy allowlist")
def validate(v,run):
 if not isinstance(v,dict) or v.get("schema_version")!=1 or not exact(v.get("schema_version"),int) or v.get("run_id")!=run or not exact(v.get("run_id"),str):fail("record violates trace schema/privacy allowlist")
 if v.get("name") in {"run.start","run.stop","tap.failure","source.failure","tap.timeout","tap.reenabled","writer_failed"}:
  if set(v)!={"schema_version","run_id","seq","t_ns","level","component","name"} or not(exact(v.get("seq"),int) and v["seq"]>0 and exact(v.get("t_ns"),int) and v["t_ns"]>=0 and v["level"]=="warning" and v["component"]=="runtime"):fail("record violates trace schema/privacy allowlist")
 elif v.get("name")=="trace.dropped":
  if set(v)!={"schema_version","run_id","level","component","name","drop_count"} or v["level"]!="warning" or v["component"]!="trace" or not exact(v.get("drop_count"),int) or v["drop_count"]<1:fail("record violates trace schema/privacy allowlist")
 elif v.get("name")=="input.pipeline":
  keys={"schema_version","run_id","seq","t_ns","level","component","name","input_seq","horizontal_lines","vertical_lines","granularity","decision","native_outcome","reason_code","config_revision","extraction_ns","rust_eval_ns","native_apply_ns","total_ns"}
  if set(v)!=keys or not(all(exact(v[k],int) and v[k]>=0 for k in {"seq","t_ns","input_seq","extraction_ns","rust_eval_ns","native_apply_ns","total_ns"}) and exact(v["horizontal_lines"],int) and exact(v["vertical_lines"],int) and v["level"]=="debug" and v["component"]=="input" and v["granularity"] in {"line_based","pixel_based"} and v["decision"] in {"preserve","replace","engine_unavailable"} and v["native_outcome"] in {"preserved","applied"} and v["reason_code"] in {"not_line_based","preserve","replace","engine_unavailable"} and v["config_revision"] is None):fail("record violates trace schema/privacy allowlist")
 else:fail("record violates trace schema/privacy allowlist")
 return v
def records(b):
 manifest(b)
 for p in segments(b):
  with p.open() as f:
   while line:=f.readline():
    if not line.endswith("\n"):break
    try:yield validate(json.loads(line),b.name)
    except json.JSONDecodeError:fail("invalid completed JSONL record")
def tail(b):
 offsets={}
 while True:
  manifest(b)
  for p in segments(b):
   with p.open() as f:
    f.seek(offsets.get(p,0))
    while True:
     offset=f.tell(); line=f.readline()
     if not line:break
     if not line.endswith("\n"): f.seek(offset); break
     try:validate(json.loads(line),b.name)
     except json.JSONDecodeError:fail("invalid completed JSONL record")
     print(line,end="",flush=True)
    offsets[p]=f.tell()
  time.sleep(.2)
def main():
 a=argparse.ArgumentParser(); s=a.add_subparsers(dest="cmd",required=True); t=s.add_parser("tail");t.add_argument("run_id",nargs="?");e=s.add_parser("export");e.add_argument("run_id",nargs="?");e.add_argument("destination",nargs="?");x=a.parse_args();b=selected(getattr(x,"run_id",None))
 if x.cmd=="tail":tail(b);return
 d=Path(x.destination) if x.destination else Path.home()/"Downloads"/"MacMouseFlow-Traces"/b.name
 if d.exists():fail("export destination already exists")
 d.parent.mkdir(parents=True,exist_ok=True)
 tmp=Path(tempfile.mkdtemp(prefix=d.name+".tmp-",dir=d.parent))
 shutil.copy2(b/"manifest.json",tmp/"manifest.json")
 out=None;i=0;size=0
 try:
  for r in records(b):
   line=json.dumps(r,sort_keys=True,separators=(",",":"))+"\n"
   if out is None or size+len(line)>1048576:
    if out:out.close()
    out=(tmp/f"trace-{i}.jsonl").open("w");i+=1;size=0
   out.write(line);size+=len(line)
  if out:out.close()
  tmp.replace(d)
 except BaseException:
  if out:out.close()
  shutil.rmtree(tmp,ignore_errors=True)
  raise
 print(d)
if __name__=="__main__":main()
