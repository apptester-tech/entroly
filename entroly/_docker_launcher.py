"""
entroly launcher — Docker-first MCP server entry point.

For Mac and Windows developers, Docker Desktop is the intended runtime.
The Rust engine runs inside the container — no local compilation needed.

Fallback chain:
  1. If already inside Docker (/.dockerenv) → run native Python server
  2. If ENTROLY_NO_DOCKER=1 and entroly-core installed → run native
  3. If Docker is available → pull + run container (mounts project CWD)
  4. Otherwise → show clear install instructions and exit
"""

from __future__ import annotations

import os
import subprocess
import sys

DOCKER_IMAGE = "ghcr.io/juyterman1000/entroly:latest"


def _docker_available() -> bool:
    """Check if Docker daemon is reachable."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode == 0:
            return True
        # Fallback: client exists but daemon needs permissions
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Client.Version}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return bool(result.stdout.strip())
    except FileNotFoundError:
        return False


def _pull_image() -> None:
    """Pull the latest entroly image silently (uses cache if offline)."""
    subprocess.run(
        ["docker", "pull", DOCKER_IMAGE],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )


def _run_native() -> None:
    """Run the MCP server in-process (inside Docker or with local engine)."""
    from entroly.server import main  # noqa: PLC0415
    main()


def _env_passthrough() -> list[str]:
    """Forward ENTROLY_* environment variables into the Docker container."""
    args: list[str] = []
    for key, value in os.environ.items():
        if key.startswith("ENTROLY_"):
            args += ["-e", f"{key}={value}"]
    return args


def launch() -> None:
    """Main entry point."""

    # Already inside Docker → go native directly
    if os.path.exists("/.dockerenv"):
        _run_native()
        return

    # Explicit override → go native (requires entroly-core installed)
    if os.environ.get("ENTROLY_NO_DOCKER"):
        _run_native()
        return

    # Docker path — the primary experience for Mac/Windows
    if _docker_available():
        _pull_image()

        cwd = os.getcwd()
        cmd = [
            "docker", "run", "--rm", "-i",
            "-v", f"{cwd}:/workspace",   # mount project files
            "-w", "/workspace",
            "-e", "ENTROLY_PROJECT_DIR=/workspace",
            *_env_passthrough(),
            DOCKER_IMAGE,
        ]

        try:
            result = subprocess.run(cmd, check=False)
            sys.exit(result.returncode)
        except KeyboardInterrupt:
            sys.exit(0)
        return

    # No Docker — clear, actionable message
    R  = "\033[0m"
    B  = "\033[1m"
    RED = "\033[91m"
    CYN = "\033[96m"
    GRY = "\033[90m"
    YLW = "\033[93m"

    print(f"""
  {RED}{B}✗ entroly cannot start — Docker is not running{R}

  {B}Quick fix (Mac / Windows):{R}
  {YLW}1.{R} Open Docker Desktop (or install from {CYN}https://docker.com/products/docker-desktop{R})
  {YLW}2.{R} Wait for the Docker icon to show "Running"
  {YLW}3.{R} Run: {CYN}entroly serve{R}
     {GRY}Entroly auto-detects Docker — no build required.{R}

  {GRY}Linux users:{R} {CYN}pip install entroly-core{R}  {GRY}# prebuilt Rust wheel{R}
""", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    launch()
