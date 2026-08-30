#!/usr/bin/env python3

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
    def test_frontier_fails_when_no_current_context_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_gh = pathlib.Path(tmp) / "gh"
            fake_gh.write_text(
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    case "$*" in
                      "repo view --json nameWithOwner -q .nameWithOwner")
                        printf '%s\\n' 'owner/repo'
                        ;;
                      "issue list -R owner/repo --label work:current --state open --json number,title,labels,url")
                        printf '%s\\n' '[]'
                        ;;
                      *)
                        printf '%s\\n' "unexpected gh call: $*" >&2
                        exit 97
                        ;;
                    esac
                    """
                )
            )
            fake_gh.chmod(fake_gh.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env["GH_BIN"] = str(fake_gh)
            result = subprocess.run(
                ["python3", str(SCRIPT), "frontier"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("NO_CURRENT_CONTEXT", result.stderr)


if __name__ == "__main__":
    unittest.main()
