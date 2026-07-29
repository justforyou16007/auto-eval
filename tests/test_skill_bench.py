"""Tests for the skill-bench skill."""

import os
import unittest
import yaml


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestSkillBench(unittest.TestCase):
    """Verify skill-bench structure and content."""

    def _load_frontmatter(self, path):
        with open(path) as f:
            content = f.read()
        if not content.startswith("---"):
            return {}
        end_idx = content.find("---", 3)
        if end_idx == -1:
            return {}
        return yaml.safe_load(content[3:end_idx]) or {}

    def test_01_skill_md_exists(self):
        path = os.path.join(REPO_ROOT, "skills", "skill-bench", "SKILL.md")
        self.assertTrue(os.path.isfile(path), f"Missing: {path}")

    def test_02_frontmatter(self):
        path = os.path.join(REPO_ROOT, "skills", "skill-bench", "SKILL.md")
        self.assertTrue(os.path.isfile(path), f"Missing: {path}")
        fm = self._load_frontmatter(path)
        self.assertEqual(fm.get("name"), "skill-bench")
        self.assertEqual(fm.get("role"), "DRIVE")
        depends_on = fm.get("depends-on", [])
        self.assertIn("eval-wiki", depends_on)

    def test_03_phases_mentioned(self):
        path = os.path.join(REPO_ROOT, "skills", "skill-bench", "SKILL.md")
        self.assertTrue(os.path.isfile(path), f"Missing: {path}")
        with open(path) as f:
            content = f.read()
        for phase in ("Collect", "Batch", "Generate", "Summary"):
            self.assertIn(phase, content, f"SKILL.md missing phase mention: {phase}")

    def test_04_references_eval_wiki_script(self):
        path = os.path.join(REPO_ROOT, "skills", "skill-bench", "SKILL.md")
        self.assertTrue(os.path.isfile(path), f"Missing: {path}")
        with open(path) as f:
            content = f.read()
        self.assertIn("$EVAL_WIKI_SCRIPT", content)

    def test_05_mentions_benchmark_html_report(self):
        path = os.path.join(REPO_ROOT, "skills", "skill-bench", "SKILL.md")
        self.assertTrue(os.path.isfile(path), f"Missing: {path}")
        with open(path) as f:
            content = f.read()
        self.assertIn("benchmark", content.lower())
        self.assertIn("HTML", content)
        self.assertIn("reports/benchmark-", content)


if __name__ == "__main__":
    unittest.main()
