"""
Tests for feedback-align skill module.
"""

import json
import os
import sys
import tempfile
import subprocess

# Add repo root to path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

FEEDBACK_ALIGN = os.path.join(REPO_ROOT, "skills", "feedback-align", "generate.py")


def _run_skill(args_list):
    """Run feedback-align generate.py with given args."""
    result = subprocess.run(
        [sys.executable, FEEDBACK_ALIGN] + args_list,
        capture_output=True, text=True, timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


def test_record_feedback_open():
    """Test recording feedback without --apply: verify feedback file with status 'open'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize wiki
        subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "eval-wiki.py"), "init", tmpdir],
            capture_output=True, text=True, timeout=10, check=True,
        )

        # Add a task first (needed as target)
        subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "eval-wiki.py"), "add-task", tmpdir,
             "--title", "Test task",
             "--difficulty", "medium",
             "--scenario-type", "single-turn",
             "--max-turns", "1",
             "--expected-behavior", "solve task"],
            capture_output=True, text=True, timeout=10, check=True,
        )

        # Record feedback (no --apply)
        ret, stdout, stderr = _run_skill([
            "--wiki-root", tmpdir,
            "--target-type", "task",
            "--target-id", "task:test-task",
            "--from", "user",
            "--issue-type", "misalignment",
            "--description", "The task description is unclear",
            "--action", "revise_task",
            "--field", "difficulty",
            "--from-value", "medium",
            "--to-value", "easy",
        ])
        assert ret == 0, f"feedback-align failed: {stderr}"

        # Verify feedback file was created
        feedback_dir = os.path.join(tmpdir, "feedback")
        assert os.path.isdir(feedback_dir)

        fb_files = [f for f in os.listdir(feedback_dir) if f.endswith(".md")]
        assert len(fb_files) == 1, f"Expected 1 feedback file, got {len(fb_files)}: {fb_files}"

        # Read feedback file and verify status is "open"
        ew = os.path.join(REPO_ROOT, "eval-wiki.py")
        # Load frontmatter manually
        fb_path = os.path.join(feedback_dir, fb_files[0])
        with open(fb_path) as f:
            content = f.read()

        assert 'status: \"open\"' in content, f"Feedback status should be 'open', got: {content[:500]}"
        assert 'issue_type: \"misalignment\"' in content
        assert 'description: \"The task description is unclear\"' in content

        # Verify task file was NOT modified
        task_path = os.path.join(tmpdir, "tasks", "test-task.md")
        with open(task_path) as f:
            task_content = f.read()
        assert 'difficulty: \"medium\"' in task_content, "Task difficulty should still be 'medium'"

        print("test_record_feedback_open PASSED")


def test_apply_feedback():
    """Test applying feedback: verify target entity modified, feedback status 'applied'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize wiki
        subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "eval-wiki.py"), "init", tmpdir],
            capture_output=True, text=True, timeout=10, check=True,
        )

        # Add a task
        subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "eval-wiki.py"), "add-task", tmpdir,
             "--title", "Test task apply",
             "--difficulty", "hard",
             "--scenario-type", "multi-turn",
             "--max-turns", "5",
             "--expected-behavior", "complete multi-turn task"],
            capture_output=True, text=True, timeout=10, check=True,
        )

        # Apply feedback with --apply flag
        ret, stdout, stderr = _run_skill([
            "--wiki-root", tmpdir,
            "--target-type", "task",
            "--target-id", "task:test-task-apply",
            "--from", "user",
            "--issue-type", "difficulty_mismatch",
            "--description", "Difficulty is too high, should be medium",
            "--action", "revise_task",
            "--field", "difficulty",
            "--from-value", "hard",
            "--to-value", "medium",
            "--apply",
        ])
        assert ret == 0, f"feedback-align --apply failed: {stderr}"

        # Verify task file was modified
        task_path = os.path.join(tmpdir, "tasks", "test-task-apply.md")
        with open(task_path) as f:
            task_content = f.read()

        assert 'difficulty: \"medium\"' in task_content, (
            f"Task difficulty should be updated to 'medium'. Content: {task_content[:500]}"
        )

        # Verify feedback status is "applied"
        feedback_dir = os.path.join(tmpdir, "feedback")
        fb_files = [f for f in os.listdir(feedback_dir) if f.endswith(".md")]
        assert len(fb_files) == 1, f"Expected 1 feedback file, got {len(fb_files)}"

        fb_path = os.path.join(feedback_dir, fb_files[0])
        with open(fb_path) as f:
            fb_content = f.read()

        assert 'status: \"applied\"' in fb_content, (
            f"Feedback status should be 'applied'. Content: {fb_content[:500]}"
        )
        assert 'applied_at:' in fb_content, "Feedback should have applied_at timestamp"

        print("test_apply_feedback PASSED")


if __name__ == "__main__":
    test_record_feedback_open()
    test_apply_feedback()
    print("\nAll feedback-align tests passed!")