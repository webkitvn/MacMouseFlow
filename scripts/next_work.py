#!/usr/bin/env python3

import json
import os
import subprocess
import sys


ISSUE_FIELDS = "number,title,body,state,labels,assignees,blockedBy,subIssues,url"
PRIORITY_RANK = {"priority:P0": 0, "priority:P1": 1, "priority:P2": 2}


def fail(code: str, message: str) -> "NoReturn":
    print(f"{code}: {message}", file=sys.stderr)
    raise SystemExit(2)


def gh_text(*args: str) -> str:
    gh = os.environ.get("GH_BIN", "gh")
    try:
        result = subprocess.run(
            [gh, *args],
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        fail(
            "GH_NOT_FOUND",
            f"GitHub CLI executable not found: {gh}; install gh or set GH_BIN to a valid executable",
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


def label_names(issue) -> set[str]:
    names = set()
    for label in issue.get("labels") or []:
        if isinstance(label, dict) and label.get("name"):
            names.add(label["name"])
        elif isinstance(label, str):
            names.add(label)
    return names


def issue_view(repo: str, number: int):
    issue = gh_json(
        "issue",
        "view",
        str(number),
        "-R",
        repo,
        "--json",
        ISSUE_FIELDS,
    )
    if not isinstance(issue, dict):
        fail("INVALID_TRACKER_RESPONSE", f"issue #{number} did not return an object")
    return issue


def is_open(item) -> bool:
    return str(item.get("state", "")).lower() == "open"


def collect_descendants(repo: str, root) -> list[dict]:
    descendants = []
    seen = set()

    def visit(parent):
        for child_ref in parent.get("subIssues") or []:
            number = child_ref.get("number") if isinstance(child_ref, dict) else None
            if not isinstance(number, int) or number in seen:
                continue
            seen.add(number)
            child = issue_view(repo, number)
            descendants.append(child)
            visit(child)

    visit(root)
    return descendants


def task_priority(task):
    priorities = sorted(label_names(task) & PRIORITY_RANK.keys())
    if len(priorities) != 1:
        fail(
            "INVALID_PRIORITY_METADATA",
            f"execution task #{task.get('number')} must have exactly one priority:P0/P1/P2 label",
        )
    return priorities[0]


def assert_native_relationship_mode(current):
    body = str(current.get("body") or "").lower()
    if "hierarchy compatibility note" in body or "compatibility fallback" in body:
        fail(
            "RELATIONSHIP_COMPATIBILITY_MODE",
            "current execution context declares temporary relationship fallback; native hierarchy/dependencies must be wired before automatic frontier selection",
        )


def frontier(repo: str, current_summary) -> list[tuple[str, dict]]:
    current = issue_view(repo, current_summary["number"])
    if "execution:epic" not in label_names(current):
        fail(
            "INVALID_CURRENT_CONTEXT",
            f"open work:current issue #{current.get('number')} is not an execution:epic",
        )

    assert_native_relationship_mode(current)

    open_tasks = []
    for issue in collect_descendants(repo, current):
        if "execution:task" in label_names(issue) and is_open(issue):
            priority = task_priority(issue)
            open_tasks.append((priority, issue))

    if not open_tasks:
        fail("NO_OPEN_LEAF_WORK", "current execution context has no open execution:task descendants")

    eligible = []
    blocked_count = 0
    claimed_count = 0
    for priority, task in open_tasks:
        blockers = [blocker for blocker in (task.get("blockedBy") or []) if is_open(blocker)]
        if blockers:
            blocked_count += 1
            continue
        if task.get("assignees"):
            claimed_count += 1
            continue
        eligible.append((priority, task))

    if not eligible:
        if blocked_count == len(open_tasks):
            fail("BLOCKED_FRONTIER", "all open execution tasks are blocked")
        unblocked_count = len(open_tasks) - blocked_count
        if unblocked_count > 0 and claimed_count == unblocked_count:
            fail("FRONTIER_FULLY_CLAIMED", "all unblocked execution tasks are claimed")
        fail("NO_FRONTIER", "all open execution tasks are blocked or claimed")

    eligible.sort(key=lambda item: (PRIORITY_RANK[item[0]], item[1]["number"]))
    return eligible


def render(priority: str, task: dict) -> str:
    url = task.get("url") or ""
    return f"{priority.removeprefix('priority:')} #{task['number']} {task.get('title', '')} {url}".rstrip()


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"frontier", "next"}:
        print("usage: next_work.py {frontier|next}", file=sys.stderr)
        return 64

    repo = repository()
    current = current_context(repo)
    items = frontier(repo, current)

    if sys.argv[1] == "next":
        print(render(*items[0]))
    else:
        for item in items:
            print(render(*item))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
