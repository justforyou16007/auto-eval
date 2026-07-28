"""
Tests for env-gen skill module.
"""

import json
import os
import sys
import tempfile
import subprocess

# Add repo root to path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

# Path to the env-gen script
ENV_GEN = os.path.join(REPO_ROOT, "skills", "env-gen", "generate.py")


def _run_skill(args_list):
    """Run the env-gen generate.py with given args. Returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, ENV_GEN] + args_list,
        capture_output=True, text=True, timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


def test_dry_run_generates_config():
    """Test that --dry-run generates environment markdown and docker-compose config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize wiki
        result = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "eval-wiki.py"), "init", tmpdir],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, f"init failed: {result.stderr}"

        # Add a task first
        result = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "eval-wiki.py"), "add-task", tmpdir,
             "--title", "Test task for env",
             "--difficulty", "medium",
             "--scenario-type", "single-turn",
             "--max-turns", "5",
             "--allowed-tools", "read,write",
             "--expected-behavior", "solve task correctly"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, f"add-task failed: {result.stderr}"

        # Run env-gen with --dry-run
        ret, stdout, stderr = _run_skill([
            "--wiki-root", tmpdir,
            "--task-id", "test-task-for-env",
            "--image", "python:3.12",
            "--network", "bridge",
            "--memory", "4g",
            "--cpus", "4",
            "--agent-endpoint", "http://localhost:4000",
            "--dry-run",
        ])
        assert ret == 0, f"env-gen failed: {stderr}"

        # Verify docker-compose file was generated
        compose_path = os.path.join(tmpdir, "docker-compose-test-task-for-env.yml")
        assert os.path.isfile(compose_path), f"docker-compose file not found at {compose_path}"

        with open(compose_path) as f:
            compose = json.loads(f.read())
        assert "services" in compose
        service_name = "agent-test-task-for-env"
        assert service_name in compose["services"]
        assert compose["services"][service_name]["image"] == "python:3.12"

        # Verify environment was ingested
        env_path = os.path.join(tmpdir, "environments", "test-task-for-env-env.md")
        assert os.path.isfile(env_path), f"env file not found at {env_path}"

        # Verify dry-run output mentions Docker commands
        assert "[Dry-run]" in stdout, "Dry-run marker not found in output"

        print("test_dry_run_generates_config PASSED")


def test_dry_run_without_docker():
    """Test that --dry-run works without Docker installed (graceful)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize wiki
        subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "eval-wiki.py"), "init", tmpdir],
            capture_output=True, text=True, timeout=10,
        )
        # Add a task
        subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "eval-wiki.py"), "add-task", tmpdir,
             "--title", "Another task",
             "--difficulty", "easy",
             "--scenario-type", "multi-turn",
             "--max-turns", "10",
             "--allowed-tools", "read",
             "--expected-behavior", "complete all turns"],
            capture_output=True, text=True, timeout=10,
        )

        # Run env-gen with --dry-run (should succeed without Docker)
        ret, stdout, stderr = _run_skill([
            "--wiki-root", tmpdir,
            "--task-id", "another-task",
            "--dry-run",
        ])
        assert ret == 0, f"env-gen --dry-run failed: {stderr}"

        # Should still generate docker-compose
        compose_path = os.path.join(tmpdir, "docker-compose-another-task.yml")
        assert os.path.isfile(compose_path)

        # Verify env file was created
        env_path = os.path.join(tmpdir, "environments", "another-task-env.md")
        assert os.path.isfile(env_path)

        print("test_dry_run_without_docker PASSED")


if __name__ == "__main__":
    test_dry_run_generates_config()
    test_dry_run_without_docker()
    print("\nAll env-gen tests passed!")