"""
Tests for the benchmark-compare sub-agent dispatch architecture (issue #9).

The previous implementation used generic shell commands (grep, file-existence
checks, 3/5 neutral defaults) that could not distinguish between different
benchmarks. After the refactor, benchmark-compare is a DRIVE orchestrator
that delegates actual evaluation to dedicated ACQUIT sub-skills
(scorecard-evaluator, benchmark2-evaluator) and a DRIVE search sub-skill
(benchmark-search). The orchestrator never judges directly.

These tests verify:
  1. Sub-agent dispatch mode: benchmark-compare dispatches scorecard-evaluator
     and benchmark2-evaluator as sub-agents, not running inline shell scoring.
  2. Mode A (comparison): SKILL.md has a section for comparison mode with
     the --baseline flag.
  3. Mode B (standalone): SKILL.md has a section for standalone evaluation
     that dispatches benchmark-search -> top-3 -> dispatch.
  4. Each of the 3 sub-skills has valid frontmatter.
  5. scorecard-evaluator: ACQUIT, cross-model-required: true, audits
     [benchmark-compare].
  6. benchmark2-evaluator: ACQUIT, cross-model-required: true, audits
     [benchmark-compare].
  7. benchmark-search: DRIVE, depends-on: [eval-wiki].
  8. scorecard-evaluator mentions all 6 dimensions with paper reference
     (arxiv 2411.12990).
  9. benchmark2-evaluator mentions all 3 metrics with paper reference
     (arxiv 2601.03986) and includes Kendall tau, DS formula, CAD model
     family hierarchy.
  10. benchmark-search references web search for similar-benchmark discovery.
  11. No hardcoded shell scoring in benchmark-compare (no grep-based scoring
      of tasks).
  12. HTML report generation in benchmark-compare aggregator phase.
  13. install script includes all 3 new sub-skills.
  14. skill-governance.md updated to describe the sub-agent dispatch pattern.
"""

import os
import unittest

import yaml


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")
SHARED_DIR = os.path.join(REPO_ROOT, "shared-references")
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")


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


def _read(path):
    with open(path) as f:
        return f.read()


# --------------------------------------------------------------------------- #
# Shared file paths
# --------------------------------------------------------------------------- #
BENCHMARK_COMPARE = os.path.join(SKILLS_DIR, "benchmark-compare", "SKILL.md")
SCORECARD_EVAL = os.path.join(SKILLS_DIR, "scorecard-evaluator", "SKILL.md")
BENCHMARK2_EVAL = os.path.join(SKILLS_DIR, "benchmark2-evaluator", "SKILL.md")
BENCHMARK_SEARCH = os.path.join(SKILLS_DIR, "benchmark-search", "SKILL.md")
INSTALL_SCRIPT = os.path.join(TOOLS_DIR, "install_eval_wiki.sh")
GOVERNANCE = os.path.join(SHARED_DIR, "skill-governance.md")


class TestSubSkillFilesExist(unittest.TestCase):
    """The orchestrator and its 3 sub-skills must all exist on disk."""

    def test_01_benchmark_compare_skill_md_exists(self):
        self.assertTrue(os.path.isfile(BENCHMARK_COMPARE),
                        f"Missing orchestrator skill: {BENCHMARK_COMPARE}")

    def test_02_scorecard_evaluator_skill_md_exists(self):
        self.assertTrue(os.path.isfile(SCORECARD_EVAL),
                        f"Missing sub-skill: {SCORECARD_EVAL}")

    def test_03_benchmark2_evaluator_skill_md_exists(self):
        self.assertTrue(os.path.isfile(BENCHMARK2_EVAL),
                        f"Missing sub-skill: {BENCHMARK2_EVAL}")

    def test_04_benchmark_search_skill_md_exists(self):
        self.assertTrue(os.path.isfile(BENCHMARK_SEARCH),
                        f"Missing sub-skill: {BENCHMARK_SEARCH}")


class TestSubSkillFrontmatter(unittest.TestCase):
    """Each of the 3 sub-skills has valid frontmatter with required fields."""

    def test_05_scorecard_evaluator_frontmatter(self):
        fm = _load_frontmatter(SCORECARD_EVAL)
        self.assertEqual(fm.get("name"), "scorecard-evaluator")
        self.assertEqual(fm.get("role"), "ACQUIT")
        self.assertEqual(fm.get("cross-model-required"), True)
        audits = fm.get("audits")
        audits_list = ([audits] if isinstance(audits, str)
                       else list(audits or []))
        self.assertIn("benchmark-compare", audits_list)
        produces = fm.get("produces", [])
        if isinstance(produces, str):
            produces = [produces]
        self.assertTrue(produces, "scorecard-evaluator must declare produces")

    def test_06_benchmark2_evaluator_frontmatter(self):
        fm = _load_frontmatter(BENCHMARK2_EVAL)
        self.assertEqual(fm.get("name"), "benchmark2-evaluator")
        self.assertEqual(fm.get("role"), "ACQUIT")
        self.assertEqual(fm.get("cross-model-required"), True)
        audits = fm.get("audits")
        audits_list = ([audits] if isinstance(audits, str)
                       else list(audits or []))
        self.assertIn("benchmark-compare", audits_list)
        produces = fm.get("produces", [])
        if isinstance(produces, str):
            produces = [produces]
        self.assertTrue(produces, "benchmark2-evaluator must declare produces")

    def test_07_benchmark_search_frontmatter(self):
        fm = _load_frontmatter(BENCHMARK_SEARCH)
        self.assertEqual(fm.get("name"), "benchmark-search")
        self.assertEqual(fm.get("role"), "DRIVE")
        depends = fm.get("depends-on", [])
        if isinstance(depends, str):
            depends = [depends]
        self.assertIn("eval-wiki", depends,
                      "benchmark-search must depend-on eval-wiki")

    def test_08_scorecard_depends_on_eval_wiki(self):
        fm = _load_frontmatter(SCORECARD_EVAL)
        depends = fm.get("depends-on", [])
        if isinstance(depends, str):
            depends = [depends]
        self.assertIn("eval-wiki", depends,
                      "scorecard-evaluator must depend-on eval-wiki")

    def test_09_benchmark2_depends_on_eval_wiki(self):
        fm = _load_frontmatter(BENCHMARK2_EVAL)
        depends = fm.get("depends-on", [])
        if isinstance(depends, str):
            depends = [depends]
        self.assertIn("eval-wiki", depends,
                      "benchmark2-evaluator must depend-on eval-wiki")


class TestBenchmarkCompareOrchestrator(unittest.TestCase):
    """benchmark-compare is a DRIVE orchestrator that dispatches, never judges."""

    @classmethod
    def setUpClass(cls):
        cls.content = _read(BENCHMARK_COMPARE)
        cls.fm = _load_frontmatter(BENCHMARK_COMPARE)

    def test_10_orchestrator_frontmatter(self):
        fm = self.fm
        self.assertEqual(fm.get("name"), "benchmark-compare")
        self.assertEqual(fm.get("role"), "DRIVE")
        depends = fm.get("depends-on", [])
        if isinstance(depends, str):
            depends = [depends]
        for skill in ("scorecard-evaluator", "benchmark2-evaluator",
                      "benchmark-search"):
            self.assertIn(skill, depends,
                          f"benchmark-compare must depend-on {skill}")
        produces = fm.get("produces", [])
        if isinstance(produces, str):
            produces = [produces]
        self.assertTrue(produces,
                        "benchmark-compare must declare a produces artifact")

    def test_11_dispatches_scorecard_evaluator(self):
        """SKILL.md must describe dispatching scorecard-evaluator as a sub-agent."""
        low = self.content.lower()
        self.assertTrue(
            _dispatches_to(low, "scorecard-evaluator"),
            "benchmark-compare must dispatch the scorecard-evaluator "
            "sub-agent (not judge inline).")

    def test_12_dispatches_benchmark2_evaluator(self):
        """SKILL.md must describe dispatching benchmark2-evaluator as a sub-agent."""
        low = self.content.lower()
        self.assertTrue(
            _dispatches_to(low, "benchmark2-evaluator"),
            "benchmark-compare must dispatch the benchmark2-evaluator "
            "sub-agent (not judge inline).")

    def test_13_dispatches_benchmark_search(self):
        """SKILL.md must describe dispatching benchmark-search in Mode B."""
        low = self.content.lower()
        self.assertTrue(
            _dispatches_to(low, "benchmark-search"),
            "benchmark-compare must dispatch the benchmark-search "
            "sub-agent in standalone mode.")

    def test_14_mode_a_comparison_with_baseline(self):
        """Mode A section exists and references the --baseline flag."""
        self.assertIn("--baseline", self.content,
                      "benchmark-compare must support the --baseline flag for "
                      "comparison mode (Mode A).")
        low = self.content.lower()
        self.assertIn("mode a", low,
                      "benchmark-compare must document Mode A (comparison).")
        self.assertIn("comparison", low)

    def test_15_mode_b_standalone_search_dispatch(self):
        """Mode B section describes standalone evaluation -> benchmark-search."""
        low = self.content.lower()
        self.assertIn("mode b", low,
                      "benchmark-compare must document Mode B (standalone).")
        self.assertIn("standalone", low)
        self.assertIn("top-3", low)
        self.assertIn("benchmark-search", low)

    def test_16_no_grep_based_scoring_of_tasks(self):
        """The orchestrator must not contain grep-based inline task scoring."""
        self.assertNotIn(
            "grep -c \"pass\" | awk", self.content,
            "benchmark-compare must not use grep-based scoring of tasks.")
        self.assertNotIn(
            "grep -l \"PASS\" | wc -l", self.content,
            "benchmark-compare must not count PASS lines via grep as a "
            "scoring mechanism.")
        # The 3/5 neutral default is a signature of the old hardcoded scorer.
        self.assertNotIn(
            "default_score=3", self.content,
            "benchmark-compare must not hardcode a neutral 3/5 default score.")
        self.assertNotIn(
            "neutral_score=3", self.content,
            "benchmark-compare must not hardcode a neutral 3/5 default score.")

    def test_17_html_report_generation_in_aggregator(self):
        """The aggregator phase generates an HTML report."""
        low = self.content.lower()
        self.assertIn("aggregate", low,
                       "benchmark-compare must have an aggregation phase.")
        self.assertIn("html", low,
                      "benchmark-compare must generate an HTML report.")
        # Must mention report output path or report file
        self.assertTrue("report" in low,
                        "benchmark-compare must reference a report artifact.")

    def test_18_eval_wiki_write_phase(self):
        """The write phase records results to eval-wiki (add-feedback)."""
        low = self.content.lower()
        self.assertIn("add-feedback", low,
                       "benchmark-compare must record results to eval-wiki via "
                       "add-feedback.")

    def test_19_degrade_graceful_on_sub_agent_failure(self):
        """If a sub-agent or top-3 candidate fails, record N/A and continue."""
        low = self.content.lower()
        self.assertTrue(
            "n/a" in low or "degrade" in low or "graceful" in low,
            "benchmark-compare must handle sub-agent failure with graceful "
            "degradation (record N/A and continue).")

    def test_20_orchestrator_does_not_define_scoring_dimensions(self):
        """The orchestrator must not define its own scoring dimensions.

        The six scorecard dimensions belong to scorecard-evaluator, and the
        three quantitative metrics belong to benchmark2-evaluator. The
        orchestrator must only dispatch and aggregate.
        """
        # The orchestrator may reference the dimension NAMES when describing
        # what it dispatches, but it must not define the 0-5 scale inline.
        self.assertNotIn(
            "0-5 scale", self.content,
            "benchmark-compare must not define its own 0-5 scoring scale "
            "inline — that is the scorecard-evaluator's job.")


class TestScorecardEvaluatorContent(unittest.TestCase):
    """scorecard-evaluator covers all 6 BetterBench dimensions."""

    @classmethod
    def setUpClass(cls):
        cls.content = _read(SCORECARD_EVAL)

    def test_21_references_betterbench_paper(self):
        self.assertIn("2411.12990", self.content,
                      "scorecard-evaluator must reference arxiv 2411.12990 "
                      "(BetterBench).")

    def test_22_mentions_all_six_dimensions(self):
        dimensions = [
            "Properties",
            "Grounding Levels",
            "Metric Assumptions",
            "Validation Evidence",
            "Gaming Risks",
            "Known Failure Cases",
        ]
        for dim in dimensions:
            self.assertIn(dim, self.content,
                          f"scorecard-evaluator must mention dimension: {dim}")

    def test_23_references_lifecycle_stages(self):
        """Each dimension must reference which lifecycle stage it belongs to."""
        # The paper defines stages J.1-J.4
        self.assertIn("J.1", self.content)
        self.assertIn("J.2", self.content)
        self.assertIn("J.3", self.content)
        self.assertIn("J.4", self.content)

    def test_24_normative_assumptions_mentioned(self):
        """The paper requires documenting normative assumptions + limitations."""
        low = self.content.lower()
        self.assertIn("normative assumption", low)
        self.assertIn("limitation", low)

    def test_25_receives_raw_benchmark_data(self):
        """ACQUIT sub-agent must receive RAW benchmark data, not self-assessment."""
        low = self.content.lower()
        self.assertIn("raw benchmark data", low)

    def test_26_cross_model_required_stated(self):
        """The skill body states cross-model review is required."""
        low = self.content.lower()
        self.assertIn("cross-model", low)

    def test_27_evidence_backed_justifications(self):
        """Scores must be evidence-backed."""
        low = self.content.lower()
        self.assertIn("evidence", low)


class TestBenchmark2EvaluatorContent(unittest.TestCase):
    """benchmark2-evaluator covers all 3 Benchmark2 metrics."""

    @classmethod
    def setUpClass(cls):
        cls.content = _read(BENCHMARK2_EVAL)

    def test_28_references_benchmark2_paper(self):
        self.assertIn("2601.03986", self.content,
                      "benchmark2-evaluator must reference arxiv 2601.03986 "
                      "(Benchmark2).")

    def test_29_mentions_all_three_metrics(self):
        metrics = [
            "Cross-Benchmark Ranking Consistency",
            "Discriminability Score",
            "Capability Alignment Deviation",
        ]
        for metric in metrics:
            self.assertIn(metric, self.content,
                          f"benchmark2-evaluator must mention metric: {metric}")

    def test_30_cbrc_kendall_tau(self):
        """CBRC metric uses Kendall's tau correlation."""
        low = self.content.lower()
        self.assertIn("kendall", low)
        self.assertIn("tau", low)
        self.assertIn("cbrc", low)

    def test_31_ds_formula_present(self):
        """The DS formula (normalized score spread * proportion) is present."""
        low = self.content.lower()
        self.assertIn("discriminability", low)
        self.assertIn("sigma", low)
        self.assertIn("normalized", low)

    def test_32_cad_model_family_hierarchy(self):
        """CAD uses a Model Family Hierarchy for comparison."""
        low = self.content.lower()
        self.assertIn("cad", low)
        self.assertIn("model family", low)
        self.assertIn("hierarchy", low)
        self.assertIn("problematic instance", low)

    def test_33_cbrc_thresholds_present(self):
        """CBRC interpretation thresholds (>0.7, 0.4-0.7, <0.4)."""
        self.assertIn("0.7", self.content)
        self.assertIn("0.4", self.content)

    def test_34_receives_raw_benchmark_data(self):
        """ACQUIT sub-agent must receive RAW benchmark data."""
        low = self.content.lower()
        self.assertIn("raw benchmark data", low)

    def test_35_cross_model_required_stated(self):
        low = self.content.lower()
        self.assertIn("cross-model", low)


class TestBenchmarkSearchContent(unittest.TestCase):
    """benchmark-search uses web search to find similar benchmarks."""

    @classmethod
    def setUpClass(cls):
        cls.content = _read(BENCHMARK_SEARCH)

    def test_36_references_web_search(self):
        low = self.content.lower()
        self.assertIn("web search", low)

    def test_37_capability_domain_mentioned(self):
        low = self.content.lower()
        self.assertIn("capability", low)
        self.assertIn("domain", low)

    def test_38_top_3_ranking(self):
        """benchmark-search must rank candidates and return top-3."""
        low = self.content.lower()
        self.assertIn("top-3", low)
        self.assertIn("similarity", low)

    def test_39_metadata_extraction(self):
        """Each candidate must extract metadata (name, year, task count)."""
        low = self.content.lower()
        self.assertIn("name", low)
        self.assertIn("year", low)


class TestInstallScriptAndGovernance(unittest.TestCase):
    """Install script and governance doc include the new sub-skills."""

    def test_40_install_script_includes_new_sub_skills(self):
        content = _read(INSTALL_SCRIPT)
        for skill in ("scorecard-evaluator", "benchmark2-evaluator",
                      "benchmark-search"):
            self.assertIn(skill, content,
                          f"install_eval_wiki.sh must install {skill}")

    def test_41_install_script_includes_benchmark_compare(self):
        content = _read(INSTALL_SCRIPT)
        self.assertIn("benchmark-compare", content,
                      "install_eval_wiki.sh must install benchmark-compare")

    def test_42_governance_describes_sub_agent_dispatch(self):
        content = _read(GOVERNANCE)
        low = content.lower()
        self.assertIn("dispatch", low,
                      "skill-governance.md must describe sub-agent dispatch.")
        self.assertIn("acquit", low)
        # The orchestrator (DRIVE) does NOT perform evaluation itself.
        self.assertIn("delegate", low)
        self.assertIn("aggregate", low)

    def test_43_governance_mentions_new_sub_skills(self):
        content = _read(GOVERNANCE)
        for skill in ("scorecard-evaluator", "benchmark2-evaluator",
                      "benchmark-search", "benchmark-compare"):
            self.assertIn(skill, content,
                          f"skill-governance.md must mention {skill}")


def _dispatches_to(low_content, skill_name):
    """Return True if content (already lowercased) describes dispatching
    a sub-agent by name.

    Accepted forms (case-insensitive):
      - `dispatch scorecard-evaluator`
      - `dispatch the scorecard-evaluator`
      - `delegate to scorecard-evaluator`
      - `dispatch scorecard-evaluator sub-agent`
      - `/scorecard-evaluator`
      - `invoke scorecard-evaluator`
    """
    name = skill_name.lower()
    forms = (
        f"dispatch {name}",
        f"dispatch the {name}",
        f"dispatches {name}",
        f"dispatches the {name}",
        f"delegate to {name}",
        f"delegate to the {name}",
        f"delegates {name}",
        f"delegates to {name}",
        f"delegates to the {name}",
        f"invoke {name}",
        f"invoke the {name}",
        f"invoke the `{name}`",
        f"hand off to {name}",
        f"hand off to the {name}",
        f"call {name}",
        f"call the {name}",
        f"call the `{name}`",
        f"run the {name}",
        f"run the `{name}`",
        f"load the {name}",
        f"load the `{name}`",
        f"/{name}",
        f"sub-agent: {name}",
        f"sub-agent {name}",
    )
    return any(form in low_content for form in forms)


if __name__ == "__main__":
    unittest.main()
