"""
Tests that auto-eval-pipeline actually delegates to its sub-skills.

Issue: auto-eval-pipeline does not actually call the downstream process skills
(task-gen, env-gen, rubric-gen, report-gen, feedback-align). Instead each phase
inlined stub logic (a `for` loop calling `add-task`, a `cat > docker-compose.yml`,
a hardcoded `criteria` dict, inline HTML, a bare run-state `set-status` for
feedback-align), bypassing the named sub-skills.

These tests verify that, after the fix:
  1. Each pipeline phase explicitly delegates to its named sub-skill.
  2. The inline stubs that bypassed the sub-skills are gone.
"""

import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE_SKILL = os.path.join(
    REPO_ROOT, "skills", "auto-eval-pipeline", "SKILL.md"
)


class TestPipelineDelegatesToSubSkills(unittest.TestCase):
    """The pipeline must actually invoke task-gen/env-gen/rubric-gen/report-gen/feedback-align."""

    @classmethod
    def setUpClass(cls):
        with open(PIPELINE_SKILL) as f:
            cls.content = f.read()

    # --- Each phase must delegate to its named sub-skill ---

    def test_phase1_delegates_to_task_gen(self):
        """Phase 1 must explicitly delegate to the task-gen skill."""
        self.assertIn("### Phase 1", self.content)
        # A delegation/invocation of the task-gen skill must appear.
        self.assertTrue(
            _delegates_to(self.content, "task-gen"),
            "Phase 1 must explicitly invoke/delegate to the task-gen skill "
            "(e.g. '/task-gen' or 'delegate to task-gen').",
        )

    def test_phase2_delegates_to_env_gen(self):
        """Phase 2 must explicitly delegate to the env-gen skill."""
        self.assertIn("### Phase 2", self.content)
        self.assertTrue(
            _delegates_to(self.content, "env-gen"),
            "Phase 2 must explicitly invoke/delegate to the env-gen skill.",
        )

    def test_phase3_delegates_to_rubric_gen(self):
        """Phase 3 must explicitly delegate to the rubric-gen skill."""
        self.assertIn("### Phase 3", self.content)
        self.assertTrue(
            _delegates_to(self.content, "rubric-gen"),
            "Phase 3 must explicitly invoke/delegate to the rubric-gen skill.",
        )

    def test_phase4_delegates_to_report_gen(self):
        """Phase 4 must explicitly delegate to the report-gen skill."""
        self.assertIn("### Phase 4", self.content)
        self.assertTrue(
            _delegates_to(self.content, "report-gen"),
            "Phase 4 must explicitly invoke/delegate to the report-gen skill.",
        )

    def test_phase5_delegates_to_feedback_align(self):
        """Phase 5 must explicitly delegate to the feedback-align skill."""
        self.assertIn("### Phase 5", self.content)
        self.assertTrue(
            _delegates_to(self.content, "feedback-align"),
            "Phase 5 must explicitly invoke/delegate to the feedback-align skill.",
        )

    # --- The inline stubs that bypassed the sub-skills must be gone ---

    def test_no_inline_task_generation_loop(self):
        """Phase 1 must not inline a `for i in seq` task-generation stub."""
        self.assertNotIn(
            'for i in $(seq 1 "$COUNT")',
            self.content,
            "Phase 1 must delegate to task-gen instead of an inline "
            "`for i in $(seq ...)` generation loop.",
        )
        self.assertNotIn(
            "# Generate tasks (stub",
            self.content,
            "Phase 1 must not contain the old task-gen stub comment.",
        )

    def test_no_inline_docker_compose_cat(self):
        """Phase 2 must not inline a `cat > docker-compose.yml` stub."""
        self.assertNotIn(
            "cat > docker-compose.yml",
            self.content,
            "Phase 2 must delegate to env-gen instead of inlining "
            "`cat > docker-compose.yml`.",
        )
        self.assertNotIn(
            "# Generate docker-compose.yml configuration (stub)",
            self.content,
            "Phase 2 must not contain the old env-gen stub comment.",
        )

    def test_no_inline_criteria_dict(self):
        """Phase 3 must not inline a hardcoded `criteria` dict."""
        self.assertNotIn(
            "'criteria': [",
            self.content,
            "Phase 3 must delegate to rubric-gen instead of inlining a "
            "hardcoded `criteria` dict.",
        )
        self.assertNotIn(
            "cat > \"evaluators/${TASK_ID}_correctness.py\"",
            self.content,
            "Phase 3 must delegate to rubric-gen instead of inlining "
            "evaluator-script scaffolding.",
        )

    def test_no_inline_html_report(self):
        """Phase 4 must not inline the HTML report body."""
        self.assertNotIn(
            "<!DOCTYPE html>",
            self.content,
            "Phase 4 must delegate to report-gen instead of inlining the "
            "HTML report.",
        )
        self.assertNotIn(
            "TASK_COUNT_PLACEHOLDER",
            self.content,
            "Phase 4 must not contain the old inline-HTML placeholders.",
        )

    def test_feedback_align_delegation_precedes_runstate_mark(self):
        """Phase 5 must invoke feedback-align BEFORE marking it done.

        The old code marked `feedback-align done` via run-state without ever
        invoking the skill. The fix must actually delegate to feedback-align,
        and the run-state mark (if present) must come AFTER that delegation,
        not stand alone as the only mention of feedback-align in the phase.
        """
        low = self.content.lower()
        mark = 'set-status "$run_id" feedback-align done'
        # A delegation marker (Read the skill / "delegate to feedback-align")
        # must exist in the content.
        self.assertTrue(
            _delegates_to(self.content, "feedback-align"),
            "Phase 5 must delegate to the feedback-align skill.",
        )
        # If the bare run-state mark is still present, a delegation marker
        # must appear before it (delegation, then bookkeeping — not the
        # reverse and not delegation-free).
        if mark in low:
            idx_mark = low.index(mark)
            # Find the earliest delegation marker for feedback-align.
            delegate_markers = [
                f"/feedback-align",
                f"delegate to feedback-align",
                f"delegate to the feedback-align",
                f"invoke feedback-align",
                f"invoke the feedback-align",
                f"invoke the `feedback-align`",
                f"load the feedback-align",
                f"load the `feedback-align`",
                f"run the feedback-align",
                f"run the `feedback-align`",
                f"call the feedback-align",
                f"call the `feedback-align`",
                f"hand off to feedback-align",
                f"hand off to the feedback-align",
                f"dispatch feedback-align",
                f"dispatch the feedback-align",
            ]
            earliest = min(
                (low.index(m) for m in delegate_markers if m in low)
            )
            self.assertLess(
                earliest,
                idx_mark,
                "Phase 5 must delegate to feedback-align BEFORE marking it "
                "done via run-state (not the reverse, and not delegation-free).",
            )


def _delegates_to(content, skill_name):
    """Return True if the content contains an explicit delegation to skill_name.

    Accepted forms (case-insensitive):
      - `/task-gen`               (slash-command invocation)
      - `delegate to task-gen`    (prose delegation)
      - `invoke task-gen`         (prose invocation)
      - `invoke the task-gen`     (prose invocation)
      - `load ... task-gen ... skill`
      - `task-gen skill` near an invocation verb
    """
    low = content.lower()
    name = skill_name.lower()
    forms = (
        f"/{name}",                # /task-gen
        f"delegate to {name}",     # delegate to task-gen
        f"delegate to the {name}",  # delegate to the task-gen
        f"invoke {name}",          # invoke task-gen
        f"invoke the {name}",      # invoke the task-gen
        f"invoke the `{name}`",    # invoke the `task-gen`
        f"load the {name}",        # load the task-gen
        f"load the `{name}`",
        f"run the {name}",         # run the task-gen
        f"run the `{name}`",
        f"call the {name}",
        f"call the `{name}`",
        f"hand off to {name}",
        f"hand off to the {name}",
        f"dispatch {name}",
        f"dispatch the {name}",
    )
    return any(form in low for form in forms)


if __name__ == "__main__":
    unittest.main()
