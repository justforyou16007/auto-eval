"""
Tests for rubric-gen skill module.
"""

import json
import os
import sys
import tempfile
import subprocess

# Add repo root to path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

# Path to the rubric-gen script
RUBRIC_GEN = os.path.join(REPO_ROOT, "skills", "rubric-gen", "generate.py")


def _run_skill(args_list):
    """Run the rubric-gen generate.py with given args. Returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, RUBRIC_GEN] + args_list,
        capture_output=True, text=True, timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


def test_rubric_gen_single_turn():
    """Test generating rubric for a single-turn task (should have 3 criteria)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize wiki
        subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "eval-wiki.py"), "init", tmpdir],
            capture_output=True, text=True, timeout=10,
        )
        # Add a single-turn task
        subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "eval-wiki.py"), "add-task", tmpdir,
             "--title", "Simple task",
             "--difficulty", "medium",
             "--scenario-type", "single-turn",
             "--max-turns", "1",
             "--allowed-tools", "read,write",
             "--expected-behavior", "solve task correctly"],
            capture_output=True, text=True, timeout=10,
        )

        # Run rubric-gen
        output_dir = os.path.join(tmpdir, "evaluators")
        ret, stdout, stderr = _run_skill([
            "--wiki-root", tmpdir,
            "--task-id", "simple-task",
            "--assurance", "draft",
            "--output-dir", output_dir,
        ])
        assert ret == 0, f"rubric-gen failed: {stderr}"

        # Verify criteria count (single-turn should have C1, C2, C3 = 3)
        criteria_path = os.path.join(output_dir, "criteria.json")
        assert os.path.isfile(criteria_path), f"criteria.json not found at {criteria_path}"

        with open(criteria_path) as f:
            criteria = json.load(f)

        assert len(criteria) == 3, f"Expected 3 criteria, got {len(criteria)}"
        cids = [c["id"] for c in criteria]
        assert "C1" in cids
        assert "C2" in cids
        assert "C3" in cids

        # Verify evaluator scripts exist
        for c in criteria:
            if c.get("evaluator") == "script":
                script_path = os.path.join(output_dir, c["script_path"])
                assert os.path.isfile(script_path), f"Script not found: {script_path}"

        # Verify scripts are valid Python
        for c in criteria:
            if c.get("evaluator") == "script":
                script_path = os.path.join(output_dir, c["script_path"])
                result = subprocess.run(
                    [sys.executable, "-c", f"import ast; ast.parse(open('{script_path}').read())"],
                    capture_output=True, text=True, timeout=10,
                )
                assert result.returncode == 0, f"Invalid Python in {script_path}: {result.stderr}"

        # Verify rubric was ingested
        rubric_path = os.path.join(tmpdir, "rubrics", "simple-task-rubric.md")
        assert os.path.isfile(rubric_path), f"Rubric file not found at {rubric_path}"

        print("test_rubric_gen_single_turn PASSED")


def test_rubric_gen_multi_turn():
    """Test generating rubric for a multi-turn task (should have C4 as well)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "eval-wiki.py"), "init", tmpdir],
            capture_output=True, text=True, timeout=10,
        )
        subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "eval-wiki.py"), "add-task", tmpdir,
             "--title", "Multi-turn task",
             "--difficulty", "hard",
             "--scenario-type", "multi-turn",
             "--max-turns", "5",
             "--allowed-tools", "read,write,execute",
             "--expected-behavior", "complete multi-turn interaction"],
            capture_output=True, text=True, timeout=10,
        )

        output_dir = os.path.join(tmpdir, "evaluators")
        ret, stdout, stderr = _run_skill([
            "--wiki-root", tmpdir,
            "--task-id", "multi-turn-task",
            "--output-dir", output_dir,
        ])
        assert ret == 0, f"rubric-gen failed: {stderr}"

        criteria_path = os.path.join(output_dir, "criteria.json")
        with open(criteria_path) as f:
            criteria = json.load(f)

        # Multi-turn should have C1, C2, C3, C4 (error recovery) = 4
        assert len(criteria) == 4, f"Expected 4 criteria, got {len(criteria)}"
        cids = [c["id"] for c in criteria]
        assert "C4" in cids, "Multi-turn should have C4 (Error recovery)"

        print("test_rubric_gen_multi_turn PASSED")


def test_rubric_gen_error_recovery():
    """Test generating rubric for an error-recovery task (should have C5)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "eval-wiki.py"), "init", tmpdir],
            capture_output=True, text=True, timeout=10,
        )
        subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "eval-wiki.py"), "add-task", tmpdir,
             "--title", "Error recovery task",
             "--difficulty", "beast",
             "--scenario-type", "error-recovery",
             "--max-turns", "10",
             "--allowed-tools", "read,write,execute,edit",
             "--expected-behavior", "recover from errors"],
            capture_output=True, text=True, timeout=10,
        )

        output_dir = os.path.join(tmpdir, "evaluators")
        ret, stdout, stderr = _run_skill([
            "--wiki-root", tmpdir,
            "--task-id", "error-recovery-task",
            "--output-dir", output_dir,
        ])
        assert ret == 0, f"rubric-gen failed: {stderr}"

        criteria_path = os.path.join(output_dir, "criteria.json")
        with open(criteria_path) as f:
            criteria = json.load(f)

        # Error-recovery should have C1, C2, C3, C5 (adversarial robustness) = 4
        # (C4 is for multi-turn, C5 is for error-recovery)
        assert len(criteria) == 4, f"Expected 4 criteria, got {len(criteria)}: {[c['id'] for c in criteria]}"
        cids = [c["id"] for c in criteria]
        assert "C5" in cids, "Error-recovery should have C5 (Adversarial robustness)"

        print("test_rubric_gen_error_recovery PASSED")


if __name__ == "__main__":
    test_rubric_gen_single_turn()
    test_rubric_gen_multi_turn()
    test_rubric_gen_error_recovery()
    print("\nAll rubric-gen tests passed!")