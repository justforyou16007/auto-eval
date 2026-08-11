"""
Tests for the per-stage ACQUIT audit role redesign (issue #5).

Verifies that each of the 5 pipeline stages is a DRIVE worker with a
companion ACQUIT audit skill that audits whether the worker honestly
completed its task. Historically rubric-gen was mis-tagged ACQUIT and
feedback-align was DRIVE_ACQUIT; both must now be DRIVE, with dedicated
ACQUIT audit skills taking over the verification responsibilities.
"""

import os
import unittest

import yaml


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")
SHARED_DIR = os.path.join(REPO_ROOT, "shared-references")


def _load_frontmatter(path):
    """Load YAML frontmatter from a Markdown file."""
    with open(path) as f:
        content = f.read()
    if not content.startswith("---"):
        return {}
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return {}
    try:
        return yaml.safe_load(content[3:end_idx]) or {}
    except yaml.YAMLError:
        return {}


# The 5 pipeline stages and the worker skill that owns each stage.
# rubric-gen and feedback-align used to be ACQUIT / DRIVE_ACQUIT — after
# the fix they are plain DRIVE workers, audited by a dedicated ACQUIT skill.
STAGES = [
    {
        "stage": 1,
        "worker": "task-gen",
        "audit": "task-audit",
        "produces": ["scenario", "task"],
    },
    {
        "stage": 2,
        "worker": "env-gen",
        "audit": "env-audit",
        "produces": ["environment"],
    },
    {
        "stage": 3,
        "worker": "rubric-gen",
        "audit": "rubric-audit",
        "produces": ["rubric"],
    },
    {
        "stage": 4,
        "worker": "report-gen",
        "audit": "report-audit",
        "produces": ["report"],
    },
    {
        "stage": 5,
        "worker": "feedback-align",
        "audit": "feedback-audit",
        "produces": ["feedback"],
    },
]


class TestAcquitRoleRedesign(unittest.TestCase):
    """Each pipeline stage is a DRIVE worker with a companion ACQUIT audit."""

    # --- Stage workers must be DRIVE (not ACQUIT / DRIVE_ACQUIT) -----------

    def test_workers_are_drive_role(self):
        """rubric-gen & feedback-align are no longer ACQUIT/DRIVE_ACQUIT."""
        for stage in STAGES:
            with self.subTest(stage=stage["stage"], worker=stage["worker"]):
                fm = _load_frontmatter(
                    os.path.join(SKILLS_DIR, stage["worker"], "SKILL.md"))
                self.assertEqual(
                    fm.get("role"), "DRIVE",
                    f"{stage['worker']}/SKILL.md role must be DRIVE, got "
                    f"{fm.get('role')!r}")

    # --- Five ACQUIT audit skills exist with correct frontmatter -----------

    def test_audit_skills_exist(self):
        """A companion ACQUIT audit skill exists for each of the 5 stages."""
        for stage in STAGES:
            with self.subTest(stage=stage["stage"], audit=stage["audit"]):
                path = os.path.join(SKILLS_DIR, stage["audit"], "SKILL.md")
                self.assertTrue(os.path.isfile(path),
                                f"Missing audit skill: {path}")

    def test_audit_skills_have_acquit_role(self):
        """Each audit skill is tagged role: ACQUIT."""
        for stage in STAGES:
            with self.subTest(stage=stage["stage"], audit=stage["audit"]):
                fm = _load_frontmatter(
                    os.path.join(SKILLS_DIR, stage["audit"], "SKILL.md"))
                self.assertEqual(fm.get("role"), "ACQUIT",
                                 f"{stage['audit']}/SKILL.md role must be "
                                 f"ACQUIT, got {fm.get('role')!r}")

    def test_audit_skills_declare_worker(self):
        """Each audit skill frontmatter declares which worker it audits."""
        for stage in STAGES:
            with self.subTest(stage=stage["stage"], audit=stage["audit"]):
                fm = _load_frontmatter(
                    os.path.join(SKILLS_DIR, stage["audit"], "SKILL.md"))
                # Accept either `audits` (single) or `audits` list.
                audits = fm.get("audits")
                self.assertTrue(
                    audits,
                    f"{stage['audit']}/SKILL.md must declare `audits` field "
                    f"naming the worker it audits")
                audits_list = (
                    [audits] if isinstance(audits, str)
                    else list(audits))
                self.assertIn(
                    stage["worker"], audits_list,
                    f"{stage['audit']}/SKILL.md `audits` must reference "
                    f"{stage['worker']}, got {audits}")

    def test_audit_skills_require_cross_model(self):
        """ACQUIT audit skills must require cross-model verification."""
        for stage in STAGES:
            with self.subTest(stage=stage["stage"], audit=stage["audit"]):
                fm = _load_frontmatter(
                    os.path.join(SKILLS_DIR, stage["audit"], "SKILL.md"))
                self.assertEqual(
                    fm.get("cross-model-required"), True,
                    f"{stage['audit']}/SKILL.md must set "
                    f"cross-model-required: true")

    def test_audit_skills_depends_on_worker(self):
        """Each audit skill depends-on its worker skill."""
        for stage in STAGES:
            with self.subTest(stage=stage["stage"], audit=stage["audit"]):
                fm = _load_frontmatter(
                    os.path.join(SKILLS_DIR, stage["audit"], "SKILL.md"))
                depends = fm.get("depends-on", [])
                if isinstance(depends, str):
                    depends = [depends]
                self.assertIn(
                    stage["worker"], depends,
                    f"{stage['audit']}/SKILL.md depends-on must include "
                    f"{stage['worker']}, got {depends}")

    def test_audit_skills_have_audits_section(self):
        """Each audit SKILL.md documents the 3-part audit checklist."""
        required_headings = [
            "Audit Checklist",      # the 3-part procedure
            "Read Worker Output",   # step 1: read worker produce
            "Completeness",         # step 2a: honestly completed
            "Usability",            # step 2b: real & usable (run/verify)
        ]
        for stage in STAGES:
            with self.subTest(stage=stage["stage"], audit=stage["audit"]):
                with open(os.path.join(
                        SKILLS_DIR, stage["audit"], "SKILL.md")) as f:
                    content = f.read()
                for heading in required_headings:
                    self.assertIn(
                        heading, content,
                        f"{stage['audit']}/SKILL.md missing heading "
                        f"'{heading}'")

    def test_task_audit_checks_alignment(self):
        """task-audit checks task-to-reality alignment (issue requirement c)."""
        path = os.path.join(SKILLS_DIR, "task-audit", "SKILL.md")
        with open(path) as f:
            content = f.read()
        self.assertIn("Alignment", content,
                      "task-audit must check task ↔ real-world alignment")

    # --- Worker skills no longer claim ACQUIT responsibilities -------------

    def test_rubric_gen_no_longer_acquit_frontmatter(self):
        """rubric-gen frontmatter is DRIVE, not ACQUIT, and cross-model is
        the audit skill's job, not rubric-gen's."""
        fm = _load_frontmatter(
            os.path.join(SKILLS_DIR, "rubric-gen", "SKILL.md"))
        self.assertEqual(fm.get("role"), "DRIVE")

    def test_feedback_align_is_pure_drive(self):
        """feedback-align is DRIVE, not DRIVE_ACQUIT."""
        fm = _load_frontmatter(
            os.path.join(SKILLS_DIR, "feedback-align", "SKILL.md"))
        self.assertEqual(fm.get("role"), "DRIVE")

    # --- Shared references & installer updated ----------------------------

    def test_acceptance_gate_documents_per_stage_audit(self):
        """acceptance-gate.md documents one ACQUIT audit per pipeline stage."""
        path = os.path.join(SHARED_DIR, "acceptance-gate.md")
        with open(path) as f:
            content = f.read()
        for audit in ["task-audit", "env-audit", "rubric-audit",
                      "report-audit", "feedback-audit"]:
            self.assertIn(audit, content,
                          f"acceptance-gate.md must mention {audit}")
        # The principle that workers are DRIVE is now stated.
        self.assertIn("All 5 pipeline stages are DRIVE", content)

    def test_skill_governance_documents_audit_skills(self):
        """skill-governance.md lists the 5 ACQUIT audit skills."""
        path = os.path.join(SHARED_DIR, "skill-governance.md")
        with open(path) as f:
            content = f.read()
        for audit in ["task-audit", "env-audit", "rubric-audit",
                      "report-audit", "feedback-audit"]:
            self.assertIn(audit, content,
                          f"skill-governance.md must mention {audit}")

    def test_install_script_includes_audit_skills(self):
        """install_eval_wiki.sh installs the 5 audit skills."""
        path = os.path.join(REPO_ROOT, "tools", "install_eval_wiki.sh")
        with open(path) as f:
            content = f.read()
        for audit in ["task-audit", "env-audit", "rubric-audit",
                      "report-audit", "feedback-audit"]:
            self.assertIn(audit, content,
                          f"install_eval_wiki.sh must install {audit}")

    def test_pipeline_references_audit_skills(self):
        """auto-eval-pipeline delegates to each stage's audit skill."""
        path = os.path.join(SKILLS_DIR, "auto-eval-pipeline", "SKILL.md")
        with open(path) as f:
            content = f.read()
        for audit in ["task-audit", "env-audit", "rubric-audit",
                      "report-audit", "feedback-audit"]:
            self.assertIn(audit, content,
                          f"auto-eval-pipeline must reference {audit}")


if __name__ == "__main__":
    unittest.main()
