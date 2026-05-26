from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_command(command: list[str], description: str) -> None:
    print(f"\n[{description}] {' '.join(command)}")
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def resolve_command(candidates: list[str], help_text: str) -> str:
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    names = ", ".join(candidates)
    raise SystemExit(f"Missing required command: {names}. {help_text}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the frontend and run the app from the FastAPI server."
    )
    parser.add_argument("--skip-build", action="store_true", help="Skip rebuilding the frontend.")
    parser.add_argument(
        "--force-install",
        action="store_true",
        help="Force frontend dependency installation before startup.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force rebuilding the frontend before startup.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for the FastAPI server.")
    parser.add_argument("--port", default="8000", help="Port for the FastAPI server.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    node_modules_dir = PROJECT_ROOT / "node_modules"
    frontend_dist = PROJECT_ROOT / "apps" / "portal" / "dist" / "index.html"
    should_install = args.force_install or not node_modules_dir.exists()
    should_build = args.rebuild or (not args.skip_build and not frontend_dist.exists())

    if should_install or should_build:
        corepack_command = resolve_command(
            ["corepack.cmd", "corepack.exe", "corepack"],
            "Install Node.js with Corepack enabled.",
        )

        if should_install:
            run_command([corepack_command, "pnpm", "install"], "Installing frontend dependencies")

        if should_build:
            run_command(
                [corepack_command, "pnpm", "--filter", "tr-seo-portal", "build"],
                "Building frontend",
            )

    run_command(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tr_seo_api.main:app",
            "--reload",
            "--host",
            args.host,
            "--port",
            args.port,
        ],
        "Starting single local server",
    )


if __name__ == "__main__":
    main()
