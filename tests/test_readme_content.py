"""
Tests for README.md content accuracy.

Verifies that:
1. Quick Start section describes skill-based (not direct CLI) usage
2. Quick Start mentions setup skill and auto-eval-pipeline skill
3. Project Structure section includes skills/setup/ and skills/auto-eval-pipeline/
4. Architecture diagram includes setup and auto-eval-pipeline
5. Layer 3 description lists 9 modules
6. No direct CLI usage examples remain in Quick Start
"""

import os
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README_PATH = os.path.join(REPO_ROOT, "README.md")


class TestReadmeContent(unittest.TestCase):
    """Verify the README accurately reflects the repo's skill-based architecture."""

    @classmethod
    def setUpClass(cls):
        with open(README_PATH) as f:
            cls.content = f.read()

    def test_01_quick_start_mentions_agent_harness(self):
        """Quick Start mentions agent harness (Claude Code, Codex CLI, etc.)."""
        self.assertIn("agent harness", self.content,
                      "Quick Start should mention agent harness")
        self.assertIn("Claude Code", self.content,
                      "Quick Start should mention Claude Code as an example harness")
        self.assertIn("Codex CLI", self.content,
                      "Quick Start should mention Codex CLI as an example harness")

    def test_02_quick_start_mentions_setup_skill(self):
        """Quick Start describes the setup skill invocation."""
        self.assertIn("**`setup`**", self.content,
                      "Quick Start should describe the setup skill")

    def test_03_quick_start_mentions_auto_eval_pipeline_skill(self):
        """Quick Start describes the auto-eval-pipeline skill invocation."""
        self.assertIn("**`auto-eval-pipeline`**", self.content,
                      "Quick Start should describe the auto-eval-pipeline skill")

    def test_04_quick_start_has_no_direct_cli_usage(self):
        """Quick Start should NOT contain direct eval-wiki.py CLI usage examples."""
        # These were the old direct CLI commands that should be removed
        cli_indicators = [
            "python3 eval-wiki.py init",
            "python3 eval-wiki.py add-task",
            "python3 eval-wiki.py add-env",
            "python3 eval-wiki.py add-rubric",
            "python3 eval-wiki.py add-feedback",
            "python3 eval-wiki.py add-edge",
            "python3 eval-wiki.py query",
            "python3 eval-wiki.py stats",
            "python3 eval-wiki.py log",
        ]
        # Find the Quick Start section boundaries
        quick_start_start = self.content.find("## 🚀 Quick Start")
        next_section = self.content.find("## ", quick_start_start + 5)
        if next_section == -1:
            next_section = quick_start_start + 5000
        quick_start_section = self.content[quick_start_start:next_section]

        for indicator in cli_indicators:
            self.assertNotIn(indicator, quick_start_section,
                             f"Quick Start should not contain CLI usage: '{indicator}'")

    def test_05_project_structure_includes_setup(self):
        """Project Structure includes setup/ under skills/."""
        self.assertIn("├── setup/", self.content,
                      "Project Structure should include setup/ under skills/")

    def test_06_project_structure_includes_auto_eval_pipeline(self):
        """Project Structure includes auto-eval-pipeline/ under skills/."""
        self.assertIn("├── auto-eval-pipeline/", self.content,
                      "Project Structure should include auto-eval-pipeline/ under skills/")

    def test_07_project_structure_says_14_modules(self):
        """Project Structure says '14 modules' for skills (9 original + 5 audit)."""
        self.assertIn("14 modules", self.content,
                      "Project Structure should say 14 modules")

    def test_08_architecture_diagram_includes_setup(self):
        """Architecture diagram includes setup and auto-eval-pipeline skills."""
        self.assertIn("setup", self.content,
                      "Architecture diagram should include setup")
        self.assertIn("auto-eval-pipeline", self.content,
                      "Architecture diagram should include auto-eval-pipeline")

    def test_09_layer_3_says_14_skill_modules(self):
        """Layer 3 description says '14 skill modules' (9 original + 5 audit)."""
        self.assertIn("14 skill modules", self.content,
                      "Layer 3 description should say 14 skill modules")

    def test_10_quick_start_mentions_bilingual_setup(self):
        """Quick Start mentions bilingual setup wizard."""
        self.assertIn("bilingual", self.content,
                      "Quick Start should mention bilingual setup wizard")
        self.assertIn("初始化", self.content,
                      "Quick Start should mention Chinese trigger phrase")
        self.assertIn("开始验证", self.content,
                      "Quick Start should mention Chinese pipeline trigger phrase")

    def test_11_quick_start_mentions_run_state_resumability(self):
        """Quick Start mentions run-state.py for orchestration and resumability."""
        self.assertIn("run-state.py", self.content,
                      "Quick Start should mention run-state.py")
        self.assertIn("resumability", self.content,
                      "Quick Start should mention resumability")


if __name__ == "__main__":
    unittest.main()