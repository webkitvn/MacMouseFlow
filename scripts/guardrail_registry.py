#!/usr/bin/env python3
"""Validate and render the repository's deliberately small YAML guardrail registry."""

import argparse
import pathlib
import re
import sys
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs/guardrails/registry.yaml"
README = ROOT / "docs/guardrails/README.md"

FAMILIES = {"domain_semantic_integrity", "architecture_boundary_integrity", "real_time_reliability_safety", "verification_test_evidence_integrity", "agent_source_of_truth_planning_integrity", "external_reference_provenance_integrity"}
SEMANTIC_FORMS = {"hard_prohibition", "conditional_prohibition", "evidence_required_invariant"}
STATUSES = {"active", "superseded", "retired"}
SCOPE_KINDS = {"repo_wide", "domain_context", "architecture_boundary", "workflow_surface"}
SOURCE_KINDS = {"context", "adr", "issue_resolution", "repository_contract", "code_contract", "test_contract", "research_evidence"}
EVIDENCE_CLASSES = {"D1", "D2", "D3", "D4", "D5"}
ACTIONS = {"notice", "warn", "request_changes", "fail", "stop_and_decide"}
SURFACES = {"just_check", "just_test", "just_ci", "just_benchmark", "just_smoke", "semantic_review", "decision_escalation"}
WAIVER_POLICIES = {"forbidden", "decision_backed_bounded"}
INITIAL_IDS = {"DG-DOM-001", "DG-ARCH-001", "DG-RT-001", "DG-REL-001", "DG-VER-001", "DG-VER-002", "DG-SOT-001", "DG-PROV-001", "DG-PROV-002"}


def scalar(value):
    value = value.strip()
    if value == "null": return None
    if value == "[]": return []
    if value.startswith(("&", "*", "!", "|", ">")) or value in {"{}", "true", "false"}:
        raise ValueError(f"unsupported YAML scalar {value!r}")
    if value[:1] in {"'", '"'}:
        if len(value) < 2 or value[-1] != value[0]: raise ValueError("unterminated quoted scalar")
        return value[1:-1]
    return value


def parse_yaml(text):
    """Parse only mappings, lists, plain scalars, `[]`, `null`, and folded `>-` text."""
    raw_lines = text.splitlines()
    for index, raw in enumerate(raw_lines):
        if raw.strip() == "":
            following = next((line for line in raw_lines[index + 1:] if line.strip()), "")
            following_indent = len(following) - len(following.lstrip())
            for previous in reversed(raw_lines[:index]):
                if not previous.strip(): continue
                previous_indent = len(previous) - len(previous.lstrip())
                if previous_indent < following_indent:
                    if previous.strip().endswith(">-"):
                        raise ValueError(f"line {index + 1}: blank folded-block lines are unsupported")
                    break
        elif raw.lstrip().startswith("#"):
            indent = len(raw) - len(raw.lstrip())
            for previous in reversed(raw_lines[:index]):
                if not previous.strip(): continue
                if len(previous) - len(previous.lstrip()) < indent:
                    if previous.strip().endswith(">-"):
                        raise ValueError(f"line {index + 1}: comment-looking folded-block content is unsupported")
                    break
    lines = []
    for number, raw in enumerate(raw_lines, 1):
        if not raw.strip() or raw.lstrip().startswith("#"): continue
        if "\t" in raw or raw.rstrip() != raw or "#" in raw:
            raise ValueError(f"line {number}: tabs, trailing whitespace, and inline comments are unsupported")
        lines.append((len(raw) - len(raw.lstrip()), raw.strip(), number))

    def block(index, indent):
        if index >= len(lines) or lines[index][0] != indent: raise ValueError("invalid indentation")
        listed = lines[index][1].startswith("- ")
        result = [] if listed else {}
        while index < len(lines) and lines[index][0] == indent:
            _, content, number = lines[index]
            if listed:
                if not content.startswith("- "): raise ValueError(f"line {number}: mixed list and mapping")
                item = content[2:]
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*:(?:\s|$)", item):
                    result.append(scalar(item)); index += 1; continue
                key, raw = item.split(":", 1); key, raw = key.strip(), raw.strip()
                entry, index = mapping_item(key, raw, index + 1, indent + 2, number)
                result.append(entry)
            else:
                if content.startswith("- ") or ":" not in content: raise ValueError(f"line {number}: expected mapping")
                key, raw = content.split(":", 1); key, raw = key.strip(), raw.strip(); index += 1
                if key in result: raise ValueError(f"line {number}: duplicate key {key}")
                result[key], index = value(raw, index, indent, number)
        return result, index

    def mapping_item(key, raw, index, indent, number):
        entry = {}
        entry[key], index = value(raw, index, indent - 2, number)
        if index < len(lines) and lines[index][0] == indent and not lines[index][1].startswith("- "):
            rest, index = block(index, indent)
            if not isinstance(rest, dict): raise ValueError("list item must contain a mapping")
            if set(entry) & set(rest): raise ValueError(f"line {number}: duplicate key {key}")
            entry.update(rest)
        return entry, index

    def value(raw, index, parent_indent, number):
        if raw == ">-":
            if index >= len(lines) or lines[index][0] <= parent_indent:
                raise ValueError(f"line {number}: empty folded scalar")
            content_indent = lines[index][0]
            parts = []
            while index < len(lines) and lines[index][0] > parent_indent:
                if lines[index][0] != content_indent:
                    raise ValueError(f"line {lines[index][2]}: folded scalar indentation is unsupported")
                parts.append(lines[index][1]); index += 1
            return " ".join(parts), index
        if raw: return scalar(raw), index
        if index >= len(lines) or lines[index][0] <= parent_indent:
            return None, index
        return block(index, lines[index][0])

    if not lines: raise ValueError("empty YAML")
    parsed, index = block(0, 0)
    if index != len(lines): raise ValueError(f"line {lines[index][2]}: unexpected indentation")
    return parsed


def exact(mapping, keys, where):
    if not isinstance(mapping, dict) or set(mapping) != set(keys):
        actual = sorted(mapping) if isinstance(mapping, dict) else type(mapping).__name__
        raise ValueError(f"{where}: expected exactly {sorted(keys)}, got {actual}")


def required(value, where):
    if value in (None, "") or (isinstance(value, list) and not value): raise ValueError(f"{where}: required")
    return value


def choice(value, values, where):
    if value not in values: raise ValueError(f"{where}: invalid {value!r}")


def https_url(value, where):
    if not isinstance(value, str): raise ValueError(f"{where}: must be HTTPS URL")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.path:
        raise ValueError(f"{where}: invalid stable HTTPS URL")


def pointer(ref, root, where):
    if not isinstance(ref, str) or not ref: raise ValueError(f"{where}: required")
    if ref.startswith("https:"):
        https_url(ref, where); return
    path = pathlib.PurePosixPath(ref)
    if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
        raise ValueError(f"{where}: invalid repository pointer {ref}")


def validate(data, root=ROOT):
    exact(data, {"schema_version", "guardrails"}, "registry")
    if data["schema_version"] != "1": raise ValueError("registry.schema_version: must be 1")
    registry = required(data["guardrails"], "registry.guardrails")
    if not isinstance(registry, list): raise ValueError("registry.guardrails: must be a list")
    identifiers = set()
    superseded_by = []
    for record in registry:
        exact(record, {"id", "title", "family", "semantic_form", "status", "scope", "canonical_sources", "invariant_summary", "violation_patterns", "triggers", "detector", "enforcement", "required_next_action", "lifecycle", "waiver"}, "guardrail")
        identifier = required(record["id"], "guardrail.id")
        if not isinstance(identifier, str) or not re.fullmatch(r"DG-[A-Z]+-\d{3}", identifier) or identifier in identifiers: raise ValueError("guardrail.id: must be unique stable ID")
        identifiers.add(identifier)
        required(record["title"], f"{identifier}.title"); required(record["invariant_summary"], f"{identifier}.invariant_summary"); required(record["required_next_action"], f"{identifier}.required_next_action")
        choice(record["family"], FAMILIES, f"{identifier}.family"); choice(record["semantic_form"], SEMANTIC_FORMS, f"{identifier}.semantic_form"); choice(record["status"], STATUSES, f"{identifier}.status")
        exact(record["scope"], {"kind", "area"}, f"{identifier}.scope"); choice(required(record["scope"]["kind"], f"{identifier}.scope.kind"), SCOPE_KINDS, f"{identifier}.scope.kind"); required(record["scope"]["area"], f"{identifier}.scope.area")
        sources = required(record["canonical_sources"], f"{identifier}.canonical_sources")
        if not isinstance(sources, list): raise ValueError(f"{identifier}.canonical_sources: must be list")
        for source in sources:
            exact(source, {"kind", "ref"}, f"{identifier}.canonical_sources"); choice(required(source["kind"], "source.kind"), SOURCE_KINDS, "source.kind"); pointer(source["ref"], root, "source.ref")
        patterns = required(record["violation_patterns"], f"{identifier}.violation_patterns"); triggers = required(record["triggers"], f"{identifier}.triggers")
        if not isinstance(patterns, list) or not isinstance(triggers, list) or not all(isinstance(trigger, str) and trigger for trigger in triggers): raise ValueError(f"{identifier}: invalid patterns or triggers")
        for pattern in patterns: exact(pattern, {"name", "summary"}, f"{identifier}.violation_pattern"); required(pattern["name"], "pattern.name"); required(pattern["summary"], "pattern.summary")
        exact(record["detector"], {"evidence_classes"}, f"{identifier}.detector"); evidence = required(record["detector"]["evidence_classes"], f"{identifier}.detector.evidence_classes")
        if not isinstance(evidence, list): raise ValueError(f"{identifier}.detector.evidence_classes: must be list")
        for item in evidence: choice(item, EVIDENCE_CLASSES, f"{identifier}.detector.evidence_classes")
        exact(record["enforcement"], {"allowed_actions", "canonical_surfaces"}, f"{identifier}.enforcement")
        for key, values in (("allowed_actions", ACTIONS), ("canonical_surfaces", SURFACES)):
            collection = required(record["enforcement"][key], f"{identifier}.enforcement.{key}")
            if not isinstance(collection, list): raise ValueError(f"{identifier}.enforcement.{key}: must be list")
            for item in collection: choice(item, values, f"{identifier}.enforcement.{key}")
        lifecycle = record["lifecycle"]; exact(lifecycle, {"last_transition", "superseded_by"}, f"{identifier}.lifecycle")
        transition = lifecycle["last_transition"]; exact(transition, {"to", "decision"}, f"{identifier}.lifecycle.last_transition")
        if transition["to"] != record["status"]: raise ValueError(f"{identifier}.lifecycle.last_transition.to: must match status")
        https_url(transition["decision"], f"{identifier}.lifecycle.last_transition.decision")
        if record["status"] == "superseded":
            successor = required(lifecycle["superseded_by"], f"{identifier}.lifecycle.superseded_by")
            if not isinstance(successor, str) or not re.fullmatch(r"DG-[A-Z]+-\d{3}", successor) or successor == identifier:
                raise ValueError(f"{identifier}.lifecycle.superseded_by: must be another stable guardrail ID")
            superseded_by.append((identifier, successor))
        elif lifecycle["superseded_by"] is not None: raise ValueError(f"{identifier}.lifecycle.superseded_by: must be null")
        waiver = record["waiver"]; exact(waiver, {"policy", "records"}, f"{identifier}.waiver"); choice(required(waiver["policy"], f"{identifier}.waiver.policy"), WAIVER_POLICIES, f"{identifier}.waiver.policy")
        if record["semantic_form"] == "hard_prohibition" and waiver["policy"] != "forbidden": raise ValueError(f"{identifier}.waiver: hard prohibitions are forbidden to waive")
        if not isinstance(waiver["records"], list): raise ValueError(f"{identifier}.waiver.records: must be list")
        if waiver["policy"] == "forbidden" and waiver["records"]: raise ValueError(f"{identifier}.waiver: forbidden policy cannot have records")
        for item in waiver["records"]:
            exact(item, {"id", "scope", "decision", "rationale", "evidence", "expires", "remediation"}, f"{identifier}.waiver.record")
            for key in ("id", "scope", "rationale", "remediation"): required(item[key], f"{identifier}.waiver.record.{key}")
            https_url(item["decision"], f"{identifier}.waiver.record.decision")
            evidence = required(item["evidence"], f"{identifier}.waiver.record.evidence")
            if not isinstance(evidence, list): raise ValueError(f"{identifier}.waiver.record.evidence: must be list")
            for evidence_pointer in evidence: pointer(evidence_pointer, root, f"{identifier}.waiver.record.evidence")
            exact(item["expires"], {"kind", "value"}, f"{identifier}.waiver.record.expires"); choice(item["expires"]["kind"], {"date", "condition"}, f"{identifier}.waiver.record.expires.kind"); required(item["expires"]["value"], f"{identifier}.waiver.record.expires.value")
    missing_initial = INITIAL_IDS - identifiers
    if missing_initial: raise ValueError(f"registry.guardrails: missing initial IDs {sorted(missing_initial)}")
    for identifier, successor in superseded_by:
        if successor not in identifiers: raise ValueError(f"{identifier}.lifecycle.superseded_by: unknown guardrail ID {successor}")
    return data


def check_readme(actual, expected):
    if actual != expected: raise ValueError("generated README drift; run scripts/guardrail_registry.py")


def render(data):
    lines = ["<!-- GENERATED FROM registry.yaml; DO NOT EDIT. -->", "", "# Design Guardrails", "", "Read `registry.yaml` for the machine-readable canonical registry. Canonical sources own each guardrail's meaning.", ""]
    for record in data["guardrails"]:
        lines += [f"## {record['id']} — {record['title']}", "", f"- **Status:** {record['status']}", f"- **Scope:** {record['scope']['kind']} / {record['scope']['area']}", f"- **Triggers:** {', '.join(record['triggers'])}", f"- **Required next action:** {record['required_next_action']}", "- **Canonical sources:**"]
        lines += [f"  - `{source['kind']}`: {source['ref']}" for source in record["canonical_sources"]]; lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(); parser.add_argument("--check", action="store_true"); args = parser.parse_args(argv)
    try:
        data = validate(parse_yaml(REGISTRY.read_text()), ROOT); expected = render(data)
        if args.check:
            check_readme(README.read_text(), expected)
        else: README.write_text(expected)
    except (OSError, ValueError) as error:
        print(f"GUARDRAIL_REGISTRY_INVALID: {error}", file=sys.stderr); return 1
    return 0


if __name__ == "__main__": raise SystemExit(main())
