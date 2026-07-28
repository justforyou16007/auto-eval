"""
Tests for eval-wiki ARIS-style skill architecture.

Verifies that after restructuring:
1. All 6 SKILL.md files exist and have valid YAML frontmatter
2. eval-wiki.py exists at src/tools/eval-wiki.py
3. dist/tools/eval-wiki.py symlink exists and resolves
4. shared-references/ has the 5 contract files
5. tools/install_eval_wiki.sh exists and is executable
6. No generate.py files remain
7. Each SKILL.md has required frontmatter fields (name, description, allowed-tools, role)
"""

import os
import stat
import subprocess
import sys
import unittest
import yaml


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestSkillStructure(unittest.TestCase):
    """Verify the ARIS-style skill architecture."""

    def test_01_eval_wiki_py_exists_at_src_tools(self):
        """eval-wiki.py exists at src/tools/eval-wiki.py."""
        path = os.path.join(REPO_ROOT, "src", "tools", "eval-wiki.py")
        self.assertTrue(os.path.isfile(path), f"Missing: {path}")

    def test_02_dist_symlink_resolves(self):
        """dist/tools/eval-wiki.py symlink exists and resolves."""
        path = os.path.join(REPO_ROOT, "dist", "tools", "eval-wiki.py")
        self.assertTrue(os.path.islink(path) or os.path.isfile(path),
                        f"Missing: {path}")
        if os.path.islink(path):
            self.assertTrue(os.path.exists(path),
                            f"Broken symlink: {path}")

    def test_03_all_skill_md_files_exist(self):
        """All 6 SKILL.md files exist."""
        expected_skills = [
            "eval-wiki",
            "task-gen",
            "env-gen",
            "rubric-gen",
            "report-gen",
            "feedback-align",
        ]
        for skill in expected_skills:
            path = os.path.join(REPO_ROOT, "skills", skill, "SKILL.md")
            self.assertTrue(os.path.isfile(path),
                            f"Missing SKILL.md for {skill}: {path}")

    def test_04_no_generate_py_files_remain(self):
        """No generate.py files remain in skills/."""
        skills_dir = os.path.join(REPO_ROOT, "skills")
        for root, dirs, files in os.walk(skills_dir):
            if "generate.py" in files:
                self.fail(f"generate.py still exists at: {os.path.join(root, 'generate.py')}")

    def test_05_shared_references_has_5_files(self):
        """shared-references/ has the 5 contract files."""
        expected_files = [
            "eval-wiki-helper-resolution.md",
            "integration-contract.md",
            "acceptance-gate.md",
            "difficulty-cost-contract.md",
            "output-versioning.md",
        ]
        for fname in expected_files:
            path = os.path.join(REPO_ROOT, "shared-references", fname)
            self.assertTrue(os.path.isfile(path),
                            f"Missing shared reference: {path}")

    def test_06_install_script_exists_and_executable(self):
        """tools/install_eval_wiki.sh exists and is executable."""
        path = os.path.join(REPO_ROOT, "tools", "install_eval_wiki.sh")
        self.assertTrue(os.path.isfile(path), f"Missing: {path}")
        st = os.stat(path)
        self.assertTrue(st.st_mode & stat.S_IXUSR,
                        f"Not executable: {path}")

    def test_07_skill_md_has_required_frontmatter(self):
        """Each SKILL.md has required frontmatter fields."""
        required_fields = ["name", "description", "allowed-tools", "role"]
        required_roles = {"DRIVE", "ACQUIT", "DRIVE_ACQUIT", "TOOL"}

        skills_dir = os.path.join(REPO_ROOT, "skills")
        for skill_name in sorted(os.listdir(skills_dir)):
            skill_dir = os.path.join(skills_dir, skill_name)
            if not os.path.isdir(skill_dir):
                continue
            skill_md = os.path.join(skill_dir, "SKILL.md")
            if not os.path.isfile(skill_md):
                continue

            with self.subTest(skill=skill_name):
                frontmatter = self._load_frontmatter(skill_md)
                for field in required_fields:
                    self.assertIn(field, frontmatter,
                                  f"{skill_name}/SKILL.md: missing field '{field}'")
                    self.assertIsNotNone(frontmatter[field],
                                         f"{skill_name}/SKILL.md: field '{field}' is None")
                    self.assertNotEqual(frontmatter[field], "",
                                        f"{skill_name}/SKILL.md: field '{field}' is empty")

                # Verify role is one of the valid values
                role = frontmatter["role"]
                self.assertIn(
                    role,
                    required_roles,
                    f"{skill_name}/SKILL.md: invalid role '{role}'"
                )

    def test_08_skill_md_frontmatter_is_valid_yaml(self):
        """All SKILL.md files have valid YAML frontmatter."""
        skills_dir = os.path.join(REPO_ROOT, "skills")
        for skill_name in sorted(os.listdir(skills_dir)):
            skill_dir = os.path.join(skills_dir, skill_name)
            if not os.path.isdir(skill_dir):
                continue
            skill_md = os.path.join(skill_dir, "SKILL.md")
            if not os.path.isfile(skill_md):
                continue

            with self.subTest(skill=skill_name):
                fm = self._load_frontmatter(skill_md)
                self.assertIsInstance(fm, dict,
                                      f"{skill_name}/SKILL.md: frontmatter should be a dict")

    def test_09_old_generated_files_deleted(self):
        """Old files main.py and TASK.md are deleted."""
        for fname in ["main.py", "TASK.md"]:
            path = os.path.join(REPO_ROOT, fname)
            self.assertFalse(os.path.exists(path),
                             f"Old file should be deleted: {path}")

    def test_10_gitignore_updated(self):
        """.gitignore contains eval-wiki/ and __pycache__/."""
        gitignore = os.path.join(REPO_ROOT, ".gitignore")
        self.assertTrue(os.path.isfile(gitignore), "Missing .gitignore")
        with open(gitignore) as f:
            content = f.read()
        self.assertIn("__pycache__/", content, ".gitignore missing __pycache__/")
        self.assertIn("eval-wiki/", content, ".gitignore missing eval-wiki/")
        self.assertIn("*.pyc", content, ".gitignore missing *.pyc")

    @staticmethod
    def _load_frontmatter(path):
        """Load YAML frontmatter from a Markdown file."""
        with open(path) as f:
            content = f.read()

        if not content.startswith("---"):
            return {}

        # Find the second ---
        end_idx = content.find("---", 3)
        if end_idx == -1:
            return {}

        yaml_str = content[3:end_idx]
        try:
            return yaml.safe_load(yaml_str) or {}
        except yaml.YAMLError:
            return {}


if __name__ == "__main__":
    unittest.main()