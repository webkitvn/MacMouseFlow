#!/usr/bin/env python3
"""Validate, follow, and export local MacMouseFlow diagnostic bundles."""
from __future__ import annotations
import argparse, json, os, shutil, sys, time
from pathlib import Path

ROOT = Path(os.environ.get("MMF_TRACE_DIR", Path.home() / "Library/Application Support/io.github.webkitvn.macmouseflow/Traces"))

def fail(message): print(f"TRACE_ERROR: {message}", file=sys.stderr); raise SystemExit(2)
def bundles(): return sorted((p for p in ROOT.glob("*") if (p / "manifest.json").is_file()), key=lambda p: p.stat().st_mtime)
def selected(run_id):
    found = [p for p in bundles() if run_id is None or p.name == run_id]
    if not found: fail("trace run not found")
    return found[-1]
def segments(bundle):
    try: return sorted(bundle.glob("trace-*.jsonl"), key=lambda p: int(p.stem.removeprefix("trace-")))
    except ValueError: fail("invalid segment name")
def exact(value, kind): return type(value) is kind
def validate_manifest(value, run):
    if not isinstance(value, dict) or set(value) != {"schema_version", "run_id", "started_monotonic_ns", "clean_shutdown", "drop_count"} or not (exact(value["schema_version"], int) and value["schema_version"] == 1 and exact(value["run_id"], str) and value["run_id"] == run and exact(value["started_monotonic_ns"], int) and value["started_monotonic_ns"] >= 0 and exact(value["clean_shutdown"], bool) and exact(value["drop_count"], int) and value["drop_count"] >= 0): fail("manifest violates trace schema/privacy allowlist")
def manifest(bundle):
    try: value = json.loads((bundle / "manifest.json").read_text())
    except (OSError, json.JSONDecodeError) as exc: fail(f"invalid manifest: {exc}")
    validate_manifest(value, bundle.name); return value
def validate(value, run):
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not exact(value.get("schema_version"), int) or value.get("run_id") != run or not exact(value.get("run_id"), str): fail("record violates trace schema/privacy allowlist")
    if value.get("kind") == "trace.dropped":
        if set(value) != {"schema_version", "run_id", "kind", "drop_count"} or not exact(value.get("drop_count"), int) or value["drop_count"] < 1: fail("record violates trace schema/privacy allowlist")
    elif value.get("kind") == "lifecycle":
        keys = {"schema_version", "run_id", "sequence", "kind", "monotonic_ns", "reason_code"}
        if set(value) != keys or not (exact(value.get("sequence"), int) and value["sequence"] > 0 and exact(value.get("monotonic_ns"), int) and value["monotonic_ns"] >= 0 and value.get("reason_code") in {"tap_unavailable", "disabled_by_timeout", "reenabled", "started", "stopped", "source_unavailable", "writer_failed"}): fail("record violates trace schema/privacy allowlist")
    elif value.get("kind") == "input":
        keys = {"schema_version", "run_id", "sequence", "kind", "monotonic_ns", "granularity", "decision", "native_outcome", "reason_code"}
        if set(value) != keys or not (exact(value.get("sequence"), int) and value["sequence"] > 0 and exact(value.get("monotonic_ns"), int) and value["monotonic_ns"] >= 0 and value.get("granularity") in {"line_based", "pixel_based"} and value.get("decision") in {"preserve", "replace", "engine_unavailable"} and value.get("native_outcome") in {"preserved", "applied"} and value.get("reason_code") in {"not_line_based", "preserve", "replace", "engine_unavailable"}): fail("record violates trace schema/privacy allowlist")
    else: fail("record violates trace schema/privacy allowlist")
    return value
def complete_records(bundle):
    manifest(bundle)
    for path in segments(bundle):
        for line in path.open():
            if not line.endswith("\n"): break
            try: yield validate(json.loads(line), bundle.name)
            except json.JSONDecodeError as exc: fail(str(exc))
def tail(bundle):
    positions = {}
    while True:
        manifest(bundle)
        for path in segments(bundle):
            with path.open() as stream:
                stream.seek(positions.get(path, 0))
                for line in stream:
                    if not line.endswith("\n"): break
                    validate(json.loads(line), bundle.name); print(line, end="", flush=True)
                positions[path] = stream.tell()
        time.sleep(.2)
def main():
    parser = argparse.ArgumentParser(); commands = parser.add_subparsers(dest="command", required=True)
    tail_p = commands.add_parser("tail"); tail_p.add_argument("run_id", nargs="?")
    export = commands.add_parser("export"); export.add_argument("run_id", nargs="?"); export.add_argument("destination", nargs="?")
    args = parser.parse_args(); bundle = selected(getattr(args, "run_id", None))
    if args.command == "tail": tail(bundle); return
    records = list(complete_records(bundle)); destination = Path(args.destination) if args.destination else Path.home() / "Downloads" / "MacMouseFlow-Traces" / bundle.name
    if destination.exists(): shutil.rmtree(destination)
    destination.mkdir(parents=True); shutil.copy2(bundle / "manifest.json", destination / "manifest.json")
    for index, record in enumerate(records):
        with (destination / f"trace-{index}.jsonl").open("w") as out: out.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    print(destination)
if __name__ == "__main__": main()
