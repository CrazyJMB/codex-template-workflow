#!/usr/bin/env python3
"""Validate the template's scripts and run its dependency-free regression tests."""

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def find_bash() -> str:
    """Prefer Git Bash over the unrelated Windows WSL launcher."""
    if os.name == "nt":
        git = shutil.which("git")
        candidates = [Path(git).parent.parent / "bin/bash.exe"] if git else []
        candidates.append(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe")
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
    bash = shutil.which("bash")
    if not bash:
        raise RuntimeError("Bash is required; install Git Bash on Windows.")
    return bash


def main() -> int:
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 or newer is required.")
    python_files = sorted((ROOT / "scripts").glob("*.py"))
    python_files.extend(sorted((ROOT / "tests/template").rglob("*.py")))
    for path in python_files:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    print(f"Validated Python syntax in {len(python_files)} files.", flush=True)

    bash = find_bash()
    shell_files = sorted((ROOT / "scripts").glob("*.sh"))
    shell_files.extend(sorted((ROOT / "scripts").glob("*.sh.example")))
    for path in shell_files:
        subprocess.run([bash, "-n", path.as_posix()], check=True)
    print(f"Validated Bash syntax in {len(shell_files)} files.", flush=True)

    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests/template"))
    if not suite.countTestCases():
        raise RuntimeError("No template regression tests found.")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error
