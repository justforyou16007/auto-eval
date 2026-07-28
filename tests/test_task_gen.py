"""
Tests for the task-gen skill (generate.py).

Verifies that:
1. Tasks are generated and written to the wiki
2. Each task file has correct YAML frontmatter
3. Tasks are not duplicated on second run
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest


class TestTaskGen(unittest.TestCase):
    """Integration tests for task-gen generate.py."""

    @classmethod
    def setUpClass(cls):
        """Set up a temporary eval-wiki for all tests."""
        cls.tmpdir = tempfile.mkdtemp()
        cls.wiki_root = os.path.join(cls.tmpdir, "eval-wiki")
        # Find repo root
        cls.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.eval_wiki_py = os.path.join(cls.repo_root, "eval-wiki.py")
        cls.generate_py = os.path.join(cls.repo_root, "skills", "task-gen", "generate.py")

        # Import eval-wiki module for load_yaml_frontmatter
        spec = importlib.util.spec_from_file_location(
            "eval_wiki_module", cls.eval_wiki_py,
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            cls.eval_wiki_mod = mod
        else:
            raise RuntimeError("Could not import eval-wiki.py")

        # Initialize the wiki
        result = subprocess.run(
            [sys.executable, cls.eval_wiki_py, "init", cls.wiki_root],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to init wiki: {result.stderr}")

    def _run_generate(self, extra_args: list = None) -> subprocess.CompletedProcess:
        """Run generate.py with standard args."""
        args = [
            sys.executable, self.generate_py,
            "--wiki-root", self.wiki_root,
            "--difficulty", "easy",
            "--count", "2",
            "--cost", "0.5",
        ]
        if extra_args:
            args.extend(extra_args)
        return subprocess.run(args, capture_output=True, text=True, timeout=30)

    def test_tasks_are_created(self):
        """Running generate.py with --count 2 --difficulty easy creates 2 task files."""
        result = self._run_generate()
        self.assertEqual(
            result.returncode, 0,
            f"generate.py failed with exit code {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )

        # Check that task files were created
        tasks_dir = os.path.join(self.wiki_root, "tasks")
        task_files = [f for f in os.listdir(tasks_dir) if f.endswith(".md")]
        self.assertGreaterEqual(
            len(task_files), 2,
            f"Expected at least 2 task files, found {len(task_files)}: {task_files}",
        )

    def test_task_files_have_valid_frontmatter(self):
        """Each task file has correct YAML frontmatter with required fields."""
        tasks_dir = os.path.join(self.wiki_root, "tasks")
        task_files = [f for f in os.listdir(tasks_dir) if f.endswith(".md")]

        self.assertGreaterEqual(len(task_files), 2, "Need at least 2 task files from previous test")

        for fname in task_files:
            fpath = os.path.join(tasks_dir, fname)
            fm = self.eval_wiki_mod.load_yaml_frontmatter(fpath)

            # Required fields
            self.assertIn("type", fm, f"{fname}: missing 'type'")
            self.assertEqual(fm["type"], "task", f"{fname}: type should be 'task'")
            self.assertIn("node_id", fm, f"{fname}: missing 'node_id'")
            self.assertIn("title", fm, f"{fname}: missing 'title'")
            self.assertIn("difficulty", fm, f"{fname}: missing 'difficulty'")
            self.assertIn("scenario_type", fm, f"{fname}: missing 'scenario_type'")
            self.assertIn("status", fm, f"{fname}: missing 'status'")

            # Verify node_id prefix
            node_id = fm["node_id"]
            self.assertTrue(
                node_id.startswith("task:"),
                f"{fname}: node_id should start with 'task:', got {node_id}",
            )

            # Verify difficulty is one of the valid values
            self.assertIn(
                fm["difficulty"],
                {"lite", "easy", "medium", "hard", "beast"},
                f"{fname}: invalid difficulty '{fm['difficulty']}'",
            )

    def test_no_duplicates_when_all_templates_exhausted(self):
        """When all templates are already used, generate.py produces no new tasks."""
        # First, exhaust all easy templates by generating with --count=5
        # (There are 5 easy templates total)
        result = self._run_generate(["--count", "5"])
        self.assertEqual(
            result.returncode, 0,
            f"generate.py --count=5 failed\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )

        tasks_dir = os.path.join(self.wiki_root, "tasks")
        before_files = set(os.listdir(tasks_dir))

        # Now try to generate more - should say "all templates already used"
        result = self._run_generate(["--count", "2"])
        self.assertEqual(
            result.returncode, 0,
            f"Second generate.py run failed\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )

        after_files = set(os.listdir(tasks_dir))
        new_files = after_files - before_files

        # No new files should be created
        self.assertEqual(
            len(new_files), 0,
            f"Expected no new task files, but got: {new_files}\n"
            f"stdout: {result.stdout}",
        )

        # The output should indicate no new tasks were generated
        self.assertIn(
            "no new tasks",
            result.stdout.lower(),
            f"Expected 'no new tasks' in output.\nstdout: {result.stdout}",
        )


if __name__ == "__main__":
    unittest.main()