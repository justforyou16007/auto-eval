"""
Acceptance tests for GitHub issue #3:

    task generation中生成的task全部是todo，说明没有根据场景实际生成有效task

The `add-task` subcommand hard-coded `_TODO` placeholders in every task
body section (测试目标 / 输入规格 / 预期输出 / 前置条件 / 边界条件)
regardless of the content the caller supplied. Even `--expected-behavior`
only reached the YAML frontmatter; the human-readable body remained an
unfilled stub. As a result task-gen always produced tasks that were
"all TODO" — no effective task content was written.

These tests invoke the real CLI via subprocess and assert that:
  * content supplied via the new `--goal`, `--input-spec`,
    `--expected-behavior`, `--preconditions`, `--constraints` flags
    is rendered into the corresponding body sections (NOT left as TODO);
  * `--expected-behavior` content reaches the 预期输出 body section
    (previously it only lived in frontmatter);
  * backward compatibility: when content is omitted, the TODO stub
    is preserved so existing callers keep working.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_WIKI = os.path.join(REPO_ROOT, "src", "tools", "eval-wiki.py")


def _run(*cli_args):
    """Run eval-wiki.py with the given args; return CompletedProcess."""
    return subprocess.run(
        [sys.executable, EVAL_WIKI, *cli_args],
        capture_output=True,
        text=True,
    )


class TestTaskBodyContent(unittest.TestCase):
    """Task body sections must be populated from CLI-supplied content."""

    def setUp(self):
        self.wiki = tempfile.mkdtemp(prefix="ew_taskbody_")
        _run("init", self.wiki)

    def tearDown(self):
        shutil.rmtree(self.wiki, ignore_errors=True)

    def _task_file(self, slug):
        return os.path.join(self.wiki, "tasks", f"{slug}.md")

    def test_expected_behavior_reaches_body_not_todo(self):
        """--expected-behavior must populate the 预期输出 body section.

        This is the core regression for issue #3: before the fix the
        behavior string only landed in frontmatter and the body section
        stayed `_TODO`.
        """
        r = _run(
            "add-task", self.wiki,
            "--title", "Query Product Stock",
            "--expected-behavior", "Returns stock count, handles missing product gracefully",
        )
        self.assertEqual(r.returncode, 0, f"add-task failed:\n{r.stderr}")
        with open(self._task_file("query-product-stock"), encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Returns stock count", content)
        # The 预期输出 section must NOT still be the TODO stub.
        self.assertIn("## 预期输出", content)
        body_after = content.split("## 预期输出", 1)[1]
        self.assertNotIn("_TODO", body_after.split("##", 1)[0])

    def test_all_body_sections_populated_from_flags(self):
        """--goal/--input-spec/--preconditions/--constraints fill body sections."""
        r = _run(
            "add-task", self.wiki,
            "--title", "Create Order",
            "--goal", "Verify the Agent can create an e-commerce order via API",
            "--input-spec", "POST /orders with JSON {product_id, quantity}",
            "--expected-behavior", "Order is created, returns 201 with order id",
            "--preconditions", "Product catalog service is up with at least one SKU",
            "--constraints", "Must not create duplicate orders for the same payload",
        )
        self.assertEqual(r.returncode, 0, f"add-task failed:\n{r.stderr}")
        with open(self._task_file("create-order"), encoding="utf-8") as f:
            content = f.read()

        # Each supplied value must appear in the body, and its section must
        # not retain the TODO stub.
        checks = [
            ("## 测试目标", "Verify the Agent can create an e-commerce order via API"),
            ("## 输入规格", "POST /orders with JSON"),
            ("## 预期输出", "Order is created; returns 201 with order id"),
            ("## 前置条件", "Product catalog service is up with at least one SKU"),
            ("## 边界条件", "Must not create duplicate orders for the same payload"),
        ]
        for section_header, expected_text in checks:
            self.assertIn(section_header, content, f"missing section {section_header}")
            section = content.split(section_header, 1)[1].split("##", 1)[0]
            self.assertNotIn("_TODO", section,
                             f"{section_header} still has TODO stub")
            self.assertIn(expected_text, section,
                          f"{section_header} did not contain supplied content")

    def test_omitted_content_keeps_todo_backward_compat(self):
        """When no body-content flags are given, TODO stubs remain (backward compat)."""
        r = _run(
            "add-task", self.wiki,
            "--title", "Minimal Task",
        )
        self.assertEqual(r.returncode, 0, f"add-task failed:\n{r.stderr}")
        with open(self._task_file("minimal-task"), encoding="utf-8") as f:
            content = f.read()
        self.assertIn("_TODO", content,
                      "omitted content should keep the TODO stub for callers that fill it later")


if __name__ == "__main__":
    unittest.main()
