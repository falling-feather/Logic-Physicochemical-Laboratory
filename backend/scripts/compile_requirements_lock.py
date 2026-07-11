"""Generate or verify the reproducible Python dependency lock file."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from datetime import date
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS_INPUT = Path("backend/requirements.txt")
REQUIREMENTS_LOCK = Path("backend/requirements.lock")
PYTHON_TARGET = "3.12"
UV_VERSION = "0.10.6"
LOCK_COMMAND_PATTERN = re.compile(
    r"compile_requirements_lock\.py --exclude-newer (?P<cutoff>\d{4}-\d{2}-\d{2})"
)


def _valid_cutoff(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an ISO date such as 2026-07-11") from exc
    return value


def _cutoff_from_existing_lock() -> str:
    lock_path = REPOSITORY_ROOT / REQUIREMENTS_LOCK
    if not lock_path.exists():
        raise RuntimeError(
            "requirements.lock does not exist; pass --exclude-newer to generate it first"
        )
    match = LOCK_COMMAND_PATTERN.search(lock_path.read_text(encoding="utf-8"))
    if not match:
        raise RuntimeError(
            "requirements.lock does not contain the managed generation command; "
            "regenerate it with --exclude-newer"
        )
    return match.group("cutoff")


def _require_expected_uv() -> None:
    try:
        result = subprocess.run(
            ["uv", "--version"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"uv {UV_VERSION} is required; install it with "
            f"`python -m pip install uv=={UV_VERSION}`"
        ) from exc
    installed = result.stdout.strip().split()
    installed_version = installed[1] if len(installed) >= 2 else "unknown"
    if installed_version != UV_VERSION:
        raise RuntimeError(
            f"uv {UV_VERSION} is required, but {installed_version} is active; "
            "change UV_VERSION only in a dedicated dependency update"
        )


def _compile(output_path: Path, cutoff: str, cache_dir: Path | None) -> None:
    command = [
        "uv",
        "pip",
        "compile",
        REQUIREMENTS_INPUT.as_posix(),
        "--universal",
        "--python-version",
        PYTHON_TARGET,
        "--generate-hashes",
        "--exclude-newer",
        cutoff,
        "--output-file",
        str(output_path),
        "--custom-compile-command",
        (
            "python backend/scripts/compile_requirements_lock.py "
            f"--exclude-newer {cutoff}"
        ),
        "--quiet",
    ]
    if cache_dir is not None:
        command.extend(["--cache-dir", str(cache_dir)])
    subprocess.run(command, cwd=REPOSITORY_ROOT, check=True)


def _normalized_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify backend/requirements.lock with a pinned uv resolver."
    )
    parser.add_argument(
        "--exclude-newer",
        type=_valid_cutoff,
        help="ignore packages uploaded after this ISO date",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="resolve into a temporary file and fail when the committed lock differs",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="optional uv cache directory (does not affect generated lock content)",
    )
    args = parser.parse_args()

    if not args.check and args.exclude_newer is None:
        parser.error("--exclude-newer is required when updating the lock")

    cutoff = args.exclude_newer or _cutoff_from_existing_lock()
    _require_expected_uv()

    lock_path = REPOSITORY_ROOT / REQUIREMENTS_LOCK
    cache_dir = args.cache_dir
    if cache_dir is not None and not cache_dir.is_absolute():
        cache_dir = REPOSITORY_ROOT / cache_dir

    if not args.check:
        _compile(lock_path, cutoff, cache_dir)
        print(f"updated {REQUIREMENTS_LOCK.as_posix()} with cutoff {cutoff}")
        return 0

    candidate = lock_path.with_name(f".requirements.lock.check-{os.getpid()}")
    try:
        _compile(candidate, cutoff, cache_dir)
        if _normalized_lines(candidate) != _normalized_lines(lock_path):
            print(
                "backend/requirements.lock is stale; regenerate it with "
                f"`python backend/scripts/compile_requirements_lock.py "
                f"--exclude-newer {cutoff}`"
            )
            return 1
    finally:
        candidate.unlink(missing_ok=True)

    print(
        "backend/requirements.lock matches backend/requirements.txt "
        f"(uv {UV_VERSION}, Python {PYTHON_TARGET}, cutoff {cutoff})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
