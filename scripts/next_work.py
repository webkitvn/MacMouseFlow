#!/usr/bin/env python3

import json
import os
import subprocess
import sys


def fail(code: str, message: str) -> "NoReturn":
    print(f"{code}: {message}", file=sys.stderr)
    raise SystemExit(2)


def gh_text(*args: str) -> str:
    gh = os.environ.get("GH_BIN", "gh")
    result = subprocess.run(
        [gh, *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "gh command failed"
        fail("GH_ERROR", detail)
    return result.stdout.strip()


def gh_json(*args: str):
    raw = gh_text(*args)
    try:
        return json.loads(raw or "null")
    except json.JSONDecodeError as exc:
        fail("GH_INVALID_JSON", str(exc))


def repository() -> str:
    repo = os.environ.get("GH_REPO")
    if repo:
        return repo
    repo = gh_text("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner")
    if not repo:
        fail("REPOSITORY_NOT_FOUND", "unable to resolve OWNER/REPO")
    return repo


def current_context(repo: str):
    issues = gh_json(
        "issue",
        "list",
        "-R",
        repo,
        "--label",
        "work:current",
        "--state",
        "open",
        "--json",
        "number,title,labels,url",
    )
    if not isinstance(issues, list):
        fail("INVALID_TRACKER_RESPONSE", "current-context query did not return a list")
    if len(issues) == 0:
        fail("NO_CURRENT_CONTEXT", "expected exactly one open issue labeled work:current")
    if len(issues) > 1:
        fail(
            "AMBIGUOUS_CURRENT_CONTEXT",
            f"expected exactly one open issue labeled work:current; found {len(issues)}",
        )
    return issues[0]


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"frontier", "next"}:
        print("usage: next_work.py {frontier|next}", file=sys.stderr)
        return 64

    repo = repository()
    current_context(repo)
    fail("NOT_READY", "frontier traversal is not implemented yet")


if __name__ == "__main__":
    raise SystemExit(main())
