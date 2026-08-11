"""
Acceptance tests for GitHub issue #1:

    eval-wiki.py 中的 add-env 和 add-rubric 无 --scenario-id 参数

The `add-env` and `add-rubric` subcommands referenced `args.scenario_id` in
the dispatch block of main() but their argparse subparsers never declared a
`--scenario-id` argument. As a result:

  * running `add-env` / `add-rubric` *without* `--scenario-id` crashed with
    `'Namespace' object has no attribute 'scenario_id'`;
  * running them *with* `--scenario-id` failed with
    `unrecognized arguments: --scenario-id`.

These tests invoke the real CLI via subprocess (exercising argparse + the
dispatch path that was broken) and assert both invocations succeed and that
the supplied scenario id is actually recorded.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_WIKI = os.path.join(REPO_ROOT, "src", "tools", "eval-wiki.py")
CRITERIA = os.path.join(REPO_ROOT, "criteria.json")


def _run(*cli_args):
    """Run eval-wiki.py with the given args; return CompletedProcess."""
    return subprocess.run(
        [sys.executable, EVAL_WIKI, *cli_args],
        capture_output=True,
        text=True,
    )


class TestAddEnvScenarioId(unittest.TestCase):
    def setUp(self):
        self.wiki = tempfile.mkdtemp(prefix="ew_scenario_")
        _run("init", self.wiki)
        _run("add-task", self.wiki, "--title", "T1")
        # add-env creates a file named "<task-slug>-env.md"; make a second env
        # to a different task so we can also test the --scenario-id path
        # without colliding with the no-scenario case.
        _run("add-task", self.wiki, "--title", "T2")

    def tearDown(self):
        shutil.rmtree(self.wiki, ignore_errors=True)

    def test_add_env_without_scenario_id_succeeds(self):
        """add-env must not crash when --scenario-id is omitted (issue #1)."""
        r = _run("add-env", self.wiki, "--task-id", "task:t2")
        self.assertEqual(
            r.returncode, 0,
            f"add-env without --scenario-id failed:\nstdout:\n{r.stdout}\n"
            f"stderr:\n{r.stderr}",
        )
        self.assertNotIn("scenario_id", r.stderr)

    def test_add_env_with_scenario_id_succeeds(self):
        """add-env must accept --scenario-id and record it."""
        r = _run(
            "add-env", self.wiki,
            "--task-id", "task:t1",
            "--scenario-id", "scenario:foo",
        )
        self.assertEqual(
            r.returncode, 0,
            f"add-env with --scenario-id failed:\nstdout:\n{r.stdout}\n"
            f"stderr:\n{r.stderr}",
        )
        # The scenario id must be recorded in the environment frontmatter.
        env_path = os.path.join(self.wiki, "environments", "t1-env.md")
        self.assertTrue(os.path.isfile(env_path), f"missing {env_path}")
        with open(env_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("scenario:foo", content)


class TestAddRubricScenarioId(unittest.TestCase):
    def setUp(self):
        self.wiki = tempfile.mkdtemp(prefix="ew_scenario_")
        _run("init", self.wiki)
        _run("add-task", self.wiki, "--title", "T1")
        _run("add-task", self.wiki, "--title", "T2")

    def tearDown(self):
        shutil.rmtree(self.wiki, ignore_errors=True)

    def test_add_rubric_without_scenario_id_succeeds(self):
        """add-rubric must not crash when --scenario-id is omitted."""
        r = _run(
            "add-rubric", self.wiki,
            "--task-id", "task:t2",
            "--criteria-json", CRITERIA,
        )
        self.assertEqual(
            r.returncode, 0,
            f"add-rubric without --scenario-id failed:\nstdout:\n{r.stdout}\n"
            f"stderr:\n{r.stderr}",
        )
        self.assertNotIn("scenario_id", r.stderr)

    def test_add_rubric_with_scenario_id_succeeds(self):
        """add-rubric must accept --scenario-id and record it."""
        r = _run(
            "add-rubric", self.wiki,
            "--task-id", "task:t1",
            "--criteria-json", CRITERIA,
            "--scenario-id", "scenario:foo",
        )
        self.assertEqual(
            r.returncode, 0,
            f"add-rubric with --scenario-id failed:\nstdout:\n{r.stdout}\n"
            f"stderr:\n{r.stderr}",
        )
        rubric_path = os.path.join(self.wiki, "rubrics", "t1-rubric.md")
        self.assertTrue(os.path.isfile(rubric_path), f"missing {rubric_path}")
        with open(rubric_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("scenario:foo", content)


if __name__ == "__main__":
    unittest.main()
