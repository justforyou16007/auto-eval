"""
Tests for the ARIS-style install_eval_wiki.sh script.

Verifies that:
1. The install script exists and is executable
2. The install script installs skills into .claude/skills/ in the target project
3. The install script installs tools into .eval/dist/tools/ in the target project
4. The install script creates a manifest at .eval/installed-skills.txt
5. --dry-run makes no changes
6. --uninstall removes all symlinks
7. --reconcile reports missing/extra symlinks
8. Safety: refuses to overwrite non-symlinks without --force
9. Resolution chain docs reference the project-level .eval/dist/tools/ path
10. Setup SKILL.md resolution chain checks .claude/skills/ for skill discovery
"""

import os
import stat
import subprocess
import tempfile
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL_SCRIPT = os.path.join(REPO_ROOT, "tools", "install_eval_wiki.sh")


class TestInstallScriptExists(unittest.TestCase):
    """Basic sanity checks for the install script."""

    def test_01_script_exists_and_executable(self):
        """tools/install_eval_wiki.sh exists and is executable."""
        self.assertTrue(os.path.isfile(INSTALL_SCRIPT),
                        f"Missing: {INSTALL_SCRIPT}")
        st = os.stat(INSTALL_SCRIPT)
        self.assertTrue(st.st_mode & stat.S_IXUSR,
                        f"Not executable: {INSTALL_SCRIPT}")

    def test_02_script_has_help_flag(self):
        """Script responds to --help."""
        result = subprocess.run(
            ["bash", INSTALL_SCRIPT, "--help"],
            capture_output=True, text=True, timeout=30
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)


class TestInstallScriptInstall(unittest.TestCase):
    """Test the install script creates proper symlinks."""

    def setUp(self):
        self.target_dir = tempfile.mkdtemp(prefix="eval-wiki-test-")
        # Ensure target has a .git directory so git rev-parse works
        subprocess.run(
            ["git", "init", "-q"],
            cwd=self.target_dir,
            capture_output=True,
            timeout=30,
        )

    def tearDown(self):
        subprocess.run(["rm", "-rf", self.target_dir], timeout=30)

    def _run_install(self, *args):
        cmd = ["bash", INSTALL_SCRIPT, self.target_dir] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=30
        )
        return result

    def test_03_install_creates_skill_symlinks(self):
        """Install creates .claude/skills/ symlinks for each skill."""
        result = self._run_install()
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        # Check that skill symlinks exist
        for skill in ["setup", "eval-wiki", "task-gen", "env-gen",
                       "rubric-gen", "report-gen", "feedback-align",
                       "auto-eval-pipeline"]:
            link_path = os.path.join(self.target_dir, ".claude", "skills", skill)
            self.assertTrue(
                os.path.islink(link_path),
                f"Missing symlink: {link_path}\n{result.stdout}\n{result.stderr}"
            )
            self.assertTrue(
                os.path.exists(link_path),
                f"Broken symlink: {link_path} -> {os.readlink(link_path)}"
            )

    def test_04_install_creates_tool_symlinks(self):
        """Install creates .eval/dist/tools/ symlinks for all 7 tools."""
        result = self._run_install()
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        for tool in ["eval-wiki.py", "capture-filter.py", "evidence-check.py",
                      "iteration-log.py", "provenance.py", "run-state.py",
                      "watchdog.py"]:
            link_path = os.path.join(self.target_dir, ".eval", "dist", "tools", tool)
            self.assertTrue(
                os.path.islink(link_path),
                f"Missing symlink: {link_path}\n{result.stdout}\n{result.stderr}"
            )
            self.assertTrue(
                os.path.exists(link_path),
                f"Broken symlink: {link_path} -> {os.readlink(link_path)}"
            )

    def test_05_install_creates_manifest(self):
        """Install creates .eval/installed-skills.txt manifest."""
        result = self._run_install()
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        manifest_path = os.path.join(self.target_dir, ".eval", "installed-skills.txt")
        self.assertTrue(os.path.isfile(manifest_path),
                        f"Missing manifest: {manifest_path}")
        with open(manifest_path) as f:
            content = f.read()
        self.assertIn("AUTOEVAL_REPO", content,
                      "Manifest should contain AUTOEVAL_REPO")
        self.assertIn(".claude/skills/", content,
                      "Manifest should list skill symlinks")
        self.assertIn(".eval/dist/tools/", content,
                      "Manifest should list tool symlinks")

    def test_06_dry_run_makes_no_changes(self):
        """--dry-run reports what would be done without creating files."""
        result = self._run_install("--dry-run")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("+", result.stdout,
                      "Dry-run should show planned actions")

        # Verify no files were created
        self.assertFalse(
            os.path.exists(os.path.join(self.target_dir, ".claude")),
            "Dry-run should not create .claude/"
        )
        self.assertFalse(
            os.path.exists(os.path.join(self.target_dir, ".eval")),
            "Dry-run should not create .eval/"
        )

    def test_07_uninstall_removes_symlinks(self):
        """--uninstall removes all symlinks created by install."""
        # First install
        self._run_install()
        self.assertTrue(
            os.path.islink(os.path.join(self.target_dir, ".claude", "skills", "setup"))
        )

        # Then uninstall
        result = self._run_install("--uninstall")
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        # Verify symlinks are removed
        self.assertFalse(
            os.path.exists(os.path.join(self.target_dir, ".claude")),
            "Uninstall should remove .claude/"
        )
        self.assertFalse(
            os.path.isfile(os.path.join(self.target_dir, ".eval", "installed-skills.txt")),
            "Uninstall should remove manifest"
        )

    def test_08_uninstall_dry_run_makes_no_changes(self):
        """--uninstall --dry-run shows what would be removed without removing."""
        # First install
        self._run_install()
        setup_link = os.path.join(self.target_dir, ".claude", "skills", "setup")
        self.assertTrue(os.path.islink(setup_link))

        # Dry-run uninstall
        result = self._run_install("--uninstall", "--dry-run")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("-", result.stdout,
                      "Dry-run uninstall should show planned removals")

        # Verify nothing was removed
        self.assertTrue(
            os.path.islink(setup_link),
            "Dry-run uninstall should not remove symlinks"
        )

    def test_09_safety_no_overwrite_without_force(self):
        """Script refuses to overwrite non-symlink files without --force."""
        # Create a non-symlink file at a path the install script would use
        fake_file = os.path.join(self.target_dir, ".eval", "dist", "tools", "eval-wiki.py")
        os.makedirs(os.path.dirname(fake_file))
        with open(fake_file, "w") as f:
            f.write("# fake file")

        # Install should fail without --force
        result = self._run_install()
        self.assertNotEqual(result.returncode, 0,
                            "Should fail without --force when file exists")

        # Install should succeed with --force
        result2 = self._run_install("--force")
        self.assertEqual(result2.returncode, 0, msg=result2.stderr)
        self.assertTrue(
            os.path.islink(fake_file),
            "With --force, should replace file with symlink"
        )

    def test_10_reconcile_reports_extra_links(self):
        """--reconcile reports missing or extra symlinks."""
        # First install
        self._run_install()

        # Add an extra symlink that shouldn't be there
        extra_link = os.path.join(self.target_dir, ".claude", "skills", "extra-skill")
        # Use a relative path target that doesn't exist (dangling symlink)
        os.symlink("nonexistent-target", extra_link)

        # Remove one legitimate symlink to simulate missing
        os.unlink(os.path.join(self.target_dir, ".claude", "skills", "setup"))

        # Reconcile
        result = self._run_install("--reconcile")
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        # Check that missing was restored
        self.assertTrue(
            os.path.islink(os.path.join(self.target_dir, ".claude", "skills", "setup")),
            "Reconcile should restore missing symlinks"
        )

        # Check that extra was reported
        self.assertIn("extra", result.stdout.lower() or result.stderr.lower(),
                      "Reconcile should report extra symlinks")

    def test_11_default_install_in_current_dir(self):
        """Running without arguments installs into current directory."""
        # Run from a temp dir
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init", "-q"], cwd=tmpdir, capture_output=True, timeout=30)
            result = subprocess.run(
                ["bash", INSTALL_SCRIPT],
                cwd=tmpdir,
                capture_output=True, text=True, timeout=30
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(
                os.path.islink(os.path.join(tmpdir, ".claude", "skills", "setup")),
                f"Default install should work in cwd\n{result.stdout}\n{result.stderr}"
            )


class TestResolutionChainDocs(unittest.TestCase):
    """Test that the resolution chain documentation is updated."""

    def test_12_resolution_chain_mentions_project_level_path(self):
        """eval-wiki-helper-resolution.md mentions the project-level .eval/dist/tools/ path."""
        path = os.path.join(REPO_ROOT, "shared-references", "eval-wiki-helper-resolution.md")
        self.assertTrue(os.path.isfile(path), f"Missing: {path}")
        with open(path) as f:
            content = f.read()

        # The resolution chain should mention .eval/dist/tools/eval-wiki.py
        # as the primary path (project-level path created by install)
        self.assertIn(".eval/dist/tools/eval-wiki.py", content,
                      "Resolution chain should reference project-level path")

    def test_13_setup_skill_md_checks_claude_skills(self):
        """setup SKILL.md resolution chain checks .claude/skills/ for skill discovery."""
        path = os.path.join(REPO_ROOT, "skills", "setup", "SKILL.md")
        self.assertTrue(os.path.isfile(path), f"Missing: {path}")
        with open(path) as f:
            content = f.read()

        # The setup SKILL.md should mention checking .claude/skills/
        # for skill discovery
        self.assertIn(".claude/skills/", content,
                      "Setup SKILL.md should check .claude/skills/ for skill discovery")


if __name__ == "__main__":
    unittest.main()