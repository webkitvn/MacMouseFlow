#!/usr/bin/env python3

import json
import os
import pathlib
import stat
import subprocess
import tempfile
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "next_work.py"


class NextWorkContractTests(unittest.TestCase):
    def run_command(self, command, responses):
        with tempfile.TemporaryDirectory() as tmp:
            fake_gh = pathlib.Path(tmp) / "gh"
            fake_gh.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import json
                    import os
                    import sys

                    responses = json.loads(os.environ["FAKE_GH_RESPONSES"])
                    key = " ".join(sys.argv[1:])
                    if key not in responses:
                        print(f"unexpected gh call: {key}", file=sys.stderr)
                        raise SystemExit(97)
                    value = responses[key]
                    if isinstance(value, (dict, list)):
                        print(json.dumps(value))
                    else:
                        print(value)
                    """
                )
            )
            fake_gh.chmod(fake_gh.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env["GH_BIN"] = str(fake_gh)
            env["FAKE_GH_RESPONSES"] = json.dumps(responses)
            return subprocess.run(
                ["python3", str(SCRIPT), command],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

    @staticmethod
    def base_responses(current):
        return {
            "repo view --json nameWithOwner -q .nameWithOwner": "owner/repo",
            "issue list -R owner/repo --label work:current --state open --json number,title,labels,url": current,
        }

    @staticmethod
    def current_epic():
        return [
            {
                "number": 49,
                "title": "M0",
                "labels": [{"name": "work:current"}, {"name": "execution:epic"}],
                "url": "u49",
            }
        ]

    def test_frontier_reports_missing_gh_executable_without_traceback(self):
        env = os.environ.copy()
        env["GH_BIN"] = str(ROOT / "definitely-missing-gh")

        result = subprocess.run(
            ["python3", str(SCRIPT), "frontier"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GH_NOT_FOUND", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_frontier_fails_when_no_current_context_exists(self):
        result = self.run_command("frontier", self.base_responses([]))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("NO_CURRENT_CONTEXT", result.stderr)

    def test_frontier_fails_when_current_context_is_ambiguous(self):
        current = [
            {"number": 49, "title": "M0", "labels": [], "url": "u49"},
            {"number": 50, "title": "v0.1", "labels": [], "url": "u50"},
        ]
        result = self.run_command("frontier", self.base_responses(current))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AMBIGUOUS_CURRENT_CONTEXT", result.stderr)

    def test_next_stops_when_tracker_declares_relationship_compatibility_fallback(self):
        responses = self.base_responses(self.current_epic())
        responses[
            "issue view 49 -R owner/repo --json number,title,body,state,labels,assignees,blockedBy,subIssues,url"
        ] = {
            "number": 49,
            "title": "M0",
            "body": "## Hierarchy compatibility note\n\nNative relationships are canonical. Current edges use compatibility fallback until native mutation is available.",
            "state": "OPEN",
            "labels": [{"name": "work:current"}, {"name": "execution:epic"}],
            "assignees": [],
            "blockedBy": [],
            "subIssues": [{"number": 47}],
            "url": "u49",
        }

        result = self.run_command("next", responses)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RELATIONSHIP_COMPATIBILITY_MODE", result.stderr)

    def test_next_reports_fully_claimed_when_all_unblocked_work_is_claimed(self):
        responses = self.base_responses(self.current_epic())
        responses.update(
            {
                "issue view 49 -R owner/repo --json number,title,body,state,labels,assignees,blockedBy,subIssues,url": {
                    "number": 49,
                    "title": "M0",
                    "body": "",
                    "state": "OPEN",
                    "labels": [{"name": "work:current"}, {"name": "execution:epic"}],
                    "assignees": [],
                    "blockedBy": [],
                    "subIssues": [{"number": 63}, {"number": 64}],
                    "url": "u49",
                },
                "issue view 63 -R owner/repo --json number,title,body,state,labels,assignees,blockedBy,subIssues,url": {
                    "number": 63,
                    "title": "Blocked P0",
                    "body": "",
                    "state": "OPEN",
                    "labels": [{"name": "execution:task"}, {"name": "priority:P0"}],
                    "assignees": [],
                    "blockedBy": [{"number": 47, "state": "OPEN"}],
                    "subIssues": [],
                    "url": "u63",
                },
                "issue view 64 -R owner/repo --json number,title,body,state,labels,assignees,blockedBy,subIssues,url": {
                    "number": 64,
                    "title": "Claimed P0",
                    "body": "",
                    "state": "OPEN",
                    "labels": [{"name": "execution:task"}, {"name": "priority:P0"}],
                    "assignees": [{"login": "agent"}],
                    "blockedBy": [],
                    "subIssues": [],
                    "url": "u64",
                },
            }
        )

        result = self.run_command("next", responses)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FRONTIER_FULLY_CLAIMED", result.stderr)

    def test_next_normalizes_native_relationship_connections(self):
        responses = self.base_responses(self.current_epic())
        responses.update(
            {
                "issue view 49 -R owner/repo --json number,title,body,state,labels,assignees,blockedBy,subIssues,url": {
                    "number": 49,
                    "title": "M0",
                    "body": "",
                    "state": "OPEN",
                    "labels": [{"name": "work:current"}, {"name": "execution:epic"}],
                    "assignees": [],
                    "blockedBy": {"nodes": [], "totalCount": 0},
                    "subIssues": {"nodes": [{"number": 79}, {"number": 53}], "totalCount": 2},
                    "url": "u49",
                },
                "issue view 79 -R owner/repo --json number,title,body,state,labels,assignees,blockedBy,subIssues,url": {
                    "number": 79,
                    "title": "Available P0",
                    "body": "",
                    "state": "OPEN",
                    "labels": [{"name": "execution:task"}, {"name": "priority:P0"}],
                    "assignees": [],
                    "blockedBy": {"nodes": [], "totalCount": 0},
                    "subIssues": {"nodes": [], "totalCount": 0},
                    "url": "u79",
                },
                "issue view 53 -R owner/repo --json number,title,body,state,labels,assignees,blockedBy,subIssues,url": {
                    "number": 53,
                    "title": "Blocked P0",
                    "body": "",
                    "state": "OPEN",
                    "labels": [{"name": "execution:task"}, {"name": "priority:P0"}],
                    "assignees": [],
                    "blockedBy": {"nodes": [{"number": 79, "state": "OPEN"}], "totalCount": 1},
                    "subIssues": {"nodes": [], "totalCount": 0},
                    "url": "u53",
                },
            }
        )

        result = self.run_command("next", responses)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("#79", result.stdout)
        self.assertNotIn("#53", result.stdout)

        responses[
            "issue view 79 -R owner/repo --json number,title,body,state,labels,assignees,blockedBy,subIssues,url"
        ]["state"] = "CLOSED"
        responses[
            "issue view 53 -R owner/repo --json number,title,body,state,labels,assignees,blockedBy,subIssues,url"
        ]["blockedBy"]["nodes"][0]["state"] = "CLOSED"
        result = self.run_command("next", responses)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("#53", result.stdout)

    def test_next_rejects_native_relationship_connection_without_list_nodes(self):
        responses = self.base_responses(self.current_epic())
        responses[
            "issue view 49 -R owner/repo --json number,title,body,state,labels,assignees,blockedBy,subIssues,url"
        ] = {
            "number": 49,
            "title": "M0",
            "body": "",
            "state": "OPEN",
            "labels": [{"name": "work:current"}, {"name": "execution:epic"}],
            "assignees": [],
            "blockedBy": {"nodes": [], "totalCount": 0},
            "subIssues": {"totalCount": 1},
            "url": "u49",
        }

        result = self.run_command("next", responses)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("INVALID_TRACKER_RESPONSE", result.stderr)

    def test_next_selects_lowest_number_from_highest_priority_unblocked_unclaimed_tasks(self):
        responses = self.base_responses(self.current_epic())
        responses.update(
            {
                "issue view 49 -R owner/repo --json number,title,body,state,labels,assignees,blockedBy,subIssues,url": {
                    "number": 49,
                    "title": "M0",
                    "body": "",
                    "state": "OPEN",
                    "labels": [{"name": "work:current"}, {"name": "execution:epic"}],
                    "assignees": [],
                    "blockedBy": [],
                    "subIssues": [{"number": 47}, {"number": 62}, {"number": 70}],
                    "url": "u49",
                },
                "issue view 47 -R owner/repo --json number,title,body,state,labels,assignees,blockedBy,subIssues,url": {
                    "number": 47,
                    "title": "First P0",
                    "body": "",
                    "state": "OPEN",
                    "labels": [{"name": "execution:task"}, {"name": "priority:P0"}],
                    "assignees": [],
                    "blockedBy": [],
                    "subIssues": [],
                    "url": "u47",
                },
                "issue view 62 -R owner/repo --json number,title,body,state,labels,assignees,blockedBy,subIssues,url": {
                    "number": 62,
                    "title": "WP",
                    "body": "",
                    "state": "OPEN",
                    "labels": [{"name": "execution:wp"}],
                    "assignees": [],
                    "blockedBy": [],
                    "subIssues": [{"number": 63}, {"number": 64}],
                    "url": "u62",
                },
                "issue view 63 -R owner/repo --json number,title,body,state,labels,assignees,blockedBy,subIssues,url": {
                    "number": 63,
                    "title": "Blocked P0",
                    "body": "",
                    "state": "OPEN",
                    "labels": [{"name": "execution:task"}, {"name": "priority:P0"}],
                    "assignees": [],
                    "blockedBy": [{"number": 47, "state": "OPEN"}],
                    "subIssues": [],
                    "url": "u63",
                },
                "issue view 64 -R owner/repo --json number,title,body,state,labels,assignees,blockedBy,subIssues,url": {
                    "number": 64,
                    "title": "Claimed P0",
                    "body": "",
                    "state": "OPEN",
                    "labels": [{"name": "execution:task"}, {"name": "priority:P0"}],
                    "assignees": [{"login": "agent"}],
                    "blockedBy": [],
                    "subIssues": [],
                    "url": "u64",
                },
                "issue view 70 -R owner/repo --json number,title,body,state,labels,assignees,blockedBy,subIssues,url": {
                    "number": 70,
                    "title": "P1",
                    "body": "",
                    "state": "OPEN",
                    "labels": [{"name": "execution:task"}, {"name": "priority:P1"}],
                    "assignees": [],
                    "blockedBy": [],
                    "subIssues": [],
                    "url": "u70",
                },
            }
        )

        result = self.run_command("next", responses)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("#47", result.stdout)
        self.assertNotIn("#70", result.stdout)


if __name__ == "__main__":
    unittest.main()
