#!/usr/bin/env python3
"""
watchdog.py — Monitors Docker containers for timeout/abnormal exit.

CLI: python3 watchdog.py <container_name> [--timeout <seconds>]

Checks:
- Container exists (docker inspect)
- Container is running (docker inspect -f '{{.State.Status}}')
- If timeout reached, docker stop the container and report

Exit 0 if healthy, 1 if timeout/stopped.
"""

import argparse
import subprocess
import sys
import time


def run_docker_cmd(args: list) -> subprocess.CompletedProcess:
    """Run a docker command and return the result."""
    try:
        return subprocess.run(
            ["docker"] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=["docker"] + args,
            returncode=1,
            stdout="",
            stderr="Timeout running docker command",
        )
    except FileNotFoundError:
        print("Error: docker command not found", file=sys.stderr)
        sys.exit(1)


def check_container(container_name: str, timeout: int) -> dict:
    """Check container health and enforce timeout."""
    # Check container exists
    result = run_docker_cmd(["inspect", container_name])
    if result.returncode != 0:
        return {
            "healthy": False,
            "status": "not_found",
            "message": f"Container '{container_name}' does not exist",
        }

    # Check container status
    result = run_docker_cmd(["inspect", "-f", "{{.State.Status}}", container_name])
    if result.returncode != 0:
        return {
            "healthy": False,
            "status": "inspect_failed",
            "message": f"Failed to inspect container '{container_name}'",
        }

    status = result.stdout.strip()

    if status == "running":
        # Container is running — check if timeout reached
        result = run_docker_cmd(["inspect", "-f", "{{.State.StartedAt}}", container_name])
        started_at = result.stdout.strip()

        if timeout > 0 and started_at:
            try:
                # Parse the started_at timestamp (RFC 3339)
                import datetime as dt
                # Docker returns format like: 2024-01-01T00:00:00.000000000Z
                started_at = started_at.replace("Z", "+00:00")
                started = dt.datetime.fromisoformat(started_at)
                now = dt.datetime.now(dt.timezone.utc)
                elapsed = (now - started).total_seconds()

                if elapsed > timeout:
                    # Timeout reached — stop the container
                    run_docker_cmd(["stop", container_name])
                    return {
                        "healthy": False,
                        "status": "timed_out",
                        "message": f"Container '{container_name}' timed out after {elapsed:.0f}s (limit: {timeout}s)",
                        "elapsed_seconds": elapsed,
                        "timeout_seconds": timeout,
                    }
            except (ValueError, TypeError):
                pass

        return {
            "healthy": True,
            "status": "running",
            "message": f"Container '{container_name}' is running",
        }
    else:
        return {
            "healthy": False,
            "status": status,
            "message": f"Container '{container_name}' is in state: {status}",
        }


def main():
    parser = argparse.ArgumentParser(
        description="Monitor Docker containers for timeout/abnormal exit"
    )
    parser.add_argument("container_name", help="Docker container name")
    parser.add_argument("--timeout", type=int, default=0, help="Timeout in seconds")
    args = parser.parse_args()

    result = check_container(args.container_name, args.timeout)
    print(result["message"])

    if result["healthy"]:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()