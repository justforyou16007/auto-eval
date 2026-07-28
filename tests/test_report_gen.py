"""
Tests for report-gen skill module.
"""

import json
import os
import sys
import tempfile
import subprocess

# Add repo root to path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

REPORT_GEN = os.path.join(REPO_ROOT, "skills", "report-gen", "generate.py")
CRITERIA_JSON = os.path.join(REPO_ROOT, "criteria.json")


def _setup_test_wiki(tmpdir):
    """Create a wiki with test data: tasks, env, rubric, runs, feedback."""
    ew = os.path.join(REPO_ROOT, "eval-wiki.py")

    # Init
    subprocess.run([sys.executable, ew, "init", tmpdir], capture_output=True, text=True, timeout=10, check=True)

    # Add task 1: single-turn
    subprocess.run([
        sys.executable, ew, "add-task", tmpdir,
        "--title", "Math problem",
        "--difficulty", "easy",
        "--scenario-type", "single-turn",
        "--max-turns", "1",
        "--allowed-tools", "read,write",
        "--expected-behavior", "solve the math problem correctly",
    ], capture_output=True, text=True, timeout=10, check=True)

    # Add task 2: multi-turn
    subprocess.run([
        sys.executable, ew, "add-task", tmpdir,
        "--title", "Debug challenge",
        "--difficulty", "hard",
        "--scenario-type", "multi-turn",
        "--max-turns", "5",
        "--allowed-tools", "read,write,execute,edit",
        "--expected-behavior", "debug and fix the code",
    ], capture_output=True, text=True, timeout=10, check=True)

    # Add env for task 1
    subprocess.run([
        sys.executable, ew, "add-env", tmpdir,
        "--task-id", "math-problem",
        "--image", "python:3.11",
        "--network", "bridge",
        "--memory", "2g",
        "--cpus", "2",
        "--agent-endpoint", "http://localhost:3000",
    ], capture_output=True, text=True, timeout=10, check=True)

    # Add rubric for task 1
    subprocess.run([
        sys.executable, ew, "add-rubric", tmpdir,
        "--task-id", "math-problem",
        "--criteria-json", CRITERIA_JSON,
    ], capture_output=True, text=True, timeout=10, check=True)

    # Add runs for task 1
    scores_pass = os.path.join(tmpdir, "scores_pass.json")
    with open(scores_pass, "w") as f:
        json.dump({"C1": "PASS", "C2": 4, "C3": 85}, f)

    subprocess.run([
        sys.executable, ew, "add-run", tmpdir,
        "--task-id", "math-problem",
        "--env-id", "math-problem-env",
        "--rubric-id", "math-problem-rubric",
        "--model", "gpt-4",
        "--verdict", "yes",
        "--confidence", "high",
        "--scores-json", scores_pass,
    ], capture_output=True, text=True, timeout=10, check=True)

    scores_fail = os.path.join(tmpdir, "scores_fail.json")
    with open(scores_fail, "w") as f:
        json.dump({"C1": "FAIL", "C2": 2, "C3": 40}, f)

    subprocess.run([
        sys.executable, ew, "add-run", tmpdir,
        "--task-id", "math-problem",
        "--env-id", "math-problem-env",
        "--rubric-id", "math-problem-rubric",
        "--model", "claude-3",
        "--verdict", "no",
        "--confidence", "medium",
        "--scores-json", scores_fail,
    ], capture_output=True, text=True, timeout=10, check=True)

    # Add feedback for task 1
    subprocess.run([
        sys.executable, ew, "add-feedback", tmpdir,
        "--target-type", "task",
        "--target-id", "task:math-problem",
        "--from", "user",
        "--issue-type", "misalignment",
        "--description", "Expected behavior is too vague",
        "--action", "revise_task",
    ], capture_output=True, text=True, timeout=10, check=True)


def test_report_generated():
    """Test that report is generated with overview, task sections, score tables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _setup_test_wiki(tmpdir)

        output_path = os.path.join(tmpdir, "report.html")
        ret, stdout, stderr = _run_report([
            "--wiki-root", tmpdir,
            "--output", output_path,
        ])
        assert ret == 0, f"report-gen failed: {stderr}"

        assert os.path.isfile(output_path), f"Report not found at {output_path}"

        with open(output_path) as f:
            html = f.read()

        # Check overview section
        assert "Agent Verification Report" in html
        assert "Overview" in html
        assert "Total Tasks" in html
        assert "Total Runs" in html
        assert "Pass Rate" in html

        # Check task sections
        assert "Math problem" in html
        assert "Debug challenge" in html

        # Check score tables
        assert "Run Results" in html
        assert "Score Details" in html

        # Check navigation
        assert "Navigation" in html
        assert "task-math-problem" in html
        assert "task-debug-challenge" in html

        # Check color coding
        assert "score-pass" in html
        assert "score-fail" in html

        # Check feedback
        assert "Expected behavior is too vague" in html

        # Check CSS is inline
        assert "font-family" in html
        assert "background" in html

        print("test_report_generated PASSED")


def test_report_empty_wiki():
    """Test report generation with empty wiki (no crashes)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "eval-wiki.py"), "init", tmpdir],
            capture_output=True, text=True, timeout=10, check=True,
        )

        output_path = os.path.join(tmpdir, "report.html")
        ret, stdout, stderr = _run_report([
            "--wiki-root", tmpdir,
            "--output", output_path,
        ])
        assert ret == 0, f"report-gen with empty wiki failed: {stderr}"
        assert os.path.isfile(output_path)

        with open(output_path) as f:
            html = f.read()

        assert "Agent Verification Report" in html
        assert "Overview" in html
        assert "Total Tasks" in html

        print("test_report_empty_wiki PASSED")


def _run_report(args_list):
    """Run report-gen with given args."""
    result = subprocess.run(
        [sys.executable, REPORT_GEN] + args_list,
        capture_output=True, text=True, timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


if __name__ == "__main__":
    test_report_generated()
    test_report_empty_wiki()
    print("\nAll report-gen tests passed!")